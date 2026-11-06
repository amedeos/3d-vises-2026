"""Small geometry helpers shared by the part modules."""

from build123d import Box, Part, Pos, Rot, Sphere, scale


def box_between(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> Part:
    """Axis-aligned box from its min and max corners."""
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def ellipsoid(cx: float, cy: float, cz: float, a: float, b: float, c: float) -> Part:
    """Ellipsoid with semi-axes a, b, c along x, y, z and its two poles on the x axis.

    Where a pole lands on a visible surface, the STL gets a hole or a non-manifold edge.
    Put the centre so that both poles end up outside the final part (inside other
    material, below a cut-off plane, or above the surface of a cut).
    """
    return Pos(cx, cy, cz) * scale(Rot(0, 90, 0) * Sphere(1.0), (a, b, c))
