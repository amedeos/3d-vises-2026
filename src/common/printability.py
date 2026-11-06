"""Printability analysis used by the tests: layer grid, islands, overhangs, line widths.

All functions look at a part in its print position (bed at z=0).
"""

from math import cos, degrees, acos, radians

import numpy as np
from build123d import GeomType, Part

from .grid import LAYER, on_grid


def off_grid_faces(part: Part) -> list[float]:
    """Heights of flat horizontal faces that do not sit on a layer boundary."""
    heights = []
    for face in part.faces():
        if face.geom_type == GeomType.PLANE and abs(abs(face.normal_at().Z) - 1) < 1e-6:
            z = face.center().Z
            if not on_grid(z):
                heights.append(round(z, 3))
    return sorted(set(heights))


def _mesh(part: Part, tolerance: float = 0.02):
    import trimesh

    verts, tris = part.tessellate(tolerance, 0.2)
    return trimesh.Trimesh([[v.X, v.Y, v.Z] for v in verts], tris)


def layer_sections(part: Part, heights=None):
    """Cross-sections (lists of shapely polygons) at the middle of every layer, or at the
    given heights."""
    mesh = _mesh(part)
    if heights is None:
        heights = np.arange(LAYER / 2, part.bounding_box().max.Z, LAYER)
    paths = mesh.section_multiplane([0, 0, 0], [0, 0, 1], list(heights))
    return [list(p.polygons_full) if p is not None else [] for p in paths]


def islands(part: Part) -> list[str]:
    """Every island of every layer must rest on the layer below (nothing starts in mid-air)."""
    from shapely.ops import unary_union

    layers = layer_sections(part)
    problems = []
    for k in range(1, len(layers)):
        below = unary_union(layers[k - 1]) if layers[k - 1] else None
        for poly in layers[k]:
            if poly.area < 0.05:  # tessellation crumbs
                continue
            if below is None or poly.intersection(below).area <= 0.01:
                problems.append(f"island of {poly.area:.2f} mm2 at z={(k + 0.5) * LAYER:.1f}")
    return problems


def overhangs(part: Part, min_angle: float = 45.0, samples: int = 7) -> list[tuple[float, float]]:
    """Downward faces flatter than `min_angle` from horizontal that do not lie on the bed.

    Uses the exact CAD normals (sampled over every face), not a mesh: a mesh of a curved
    vertical wall can contain thin tilted triangles that are not real overhangs.
    Returns (z, angle from horizontal) of the offending faces.
    """
    limit = -cos(radians(min_angle)) - 1e-6  # a normal more downwards than this is too flat
    found: dict[float, float] = {}
    params = [(k + 0.5) / samples for k in range(samples)]
    for face in part.faces():
        bb = face.bounding_box()
        if bb.max.Z < 1e-3:  # on the bed
            continue
        for u in params:
            for v in params:
                n = face.normal_at(u, v)
                if n.Z < limit:
                    z = round(face.position_at(u, v).Z, 2)
                    found[z] = min(found.get(z, 90.0), degrees(acos(min(1.0, -n.Z))))
    return sorted(found.items())


def _raster(polys, bounds, px_per_mm: float) -> np.ndarray:
    """Rasterise shapely polygons (with holes) into a boolean mask over `bounds`."""
    from PIL import Image, ImageDraw

    x0, y0, x1, y1 = bounds
    w, h = int((x1 - x0) * px_per_mm) + 1, int((y1 - y0) * px_per_mm) + 1
    img = Image.new("1", (w, h), 0)
    draw = ImageDraw.Draw(img)

    def pts(ring):
        return [((x - x0) * px_per_mm, (y - y0) * px_per_mm) for x, y in ring.coords]

    for poly in sorted(polys, key=lambda p: -p.area):
        draw.polygon(pts(poly.exterior), fill=1)
        for ring in poly.interiors:
            draw.polygon(pts(ring), fill=0)
    return np.array(img, dtype=bool)


def _disk(diameter: float, px_per_mm: float) -> np.ndarray:
    r = max(1, int((diameter * px_per_mm - 1) / 2))  # the disk spans 2r+1 <= diameter px
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return xx**2 + yy**2 <= r * r


def _thin_blobs(mask: np.ndarray, diameter: float, px_per_mm: float,
                min_area: float) -> list[float]:
    """Areas (mm2) of the connected pieces of `mask` that a disk of `diameter` cannot reach
    (morphological opening), ignoring pieces smaller than `min_area` (corners)."""
    from scipy import ndimage

    opened = ndimage.binary_opening(mask, structure=_disk(diameter, px_per_mm))
    labels, n = ndimage.label(mask & ~opened)
    if not n:
        return []
    areas = ndimage.sum(np.ones_like(mask, dtype=float), labels, range(1, n + 1))
    areas = areas / px_per_mm**2
    return sorted(round(float(a), 3) for a in areas if a > min_area)


def thin_material(polys, min_width: float, px_per_mm: float = 40.0,
                  min_area: float = 0.25) -> list[float]:
    """Pieces of material narrower than `min_width` (areas in mm2; empty = fine)."""
    from shapely.ops import unary_union

    if not polys:
        return []
    b = unary_union(polys).bounds
    bounds = (b[0] - 2, b[1] - 2, b[2] + 2, b[3] + 2)
    return _thin_blobs(_raster(polys, bounds, px_per_mm), min_width, px_per_mm, min_area)


def narrow_gaps(polys, min_gap: float, px_per_mm: float = 40.0,
                min_area: float = 0.1) -> list[float]:
    """Pieces of empty space (slots, holes, notches) narrower than `min_gap`."""
    from shapely.ops import unary_union

    if not polys:
        return []
    b = unary_union(polys).bounds
    bounds = (b[0] - 2, b[1] - 2, b[2] + 2, b[3] + 2)
    empty = ~_raster(polys, bounds, px_per_mm)
    return _thin_blobs(empty, min_gap, px_per_mm, min_area)


def colour_bands(coloured: list[tuple[Part, str]]) -> list[tuple[str, float, float]]:
    """(colour, z_min, z_max) of each colour region, from the bottom up."""
    bands = []
    for part, colour in coloured:
        bb = part.bounding_box()
        bands.append((colour, round(bb.min.Z, 4), round(bb.max.Z, 4)))
    return sorted(bands, key=lambda b: b[1])
