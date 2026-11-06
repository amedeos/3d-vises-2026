"""The knob of the three screws: a stylised gnu head, seen from the front.

The gnu turns the screw that moves Tux: GNU/Linux. It is our own drawing of a gnu, not
the GNU logo (a trademark of the GNU Project, and its fine hair would be thinner than two
lines at this size).

The knob prints flat under the screw, so the face on the bed is the one you see from
outside. Its details are holes through the whole knob (eyes, nostrils) and the outline:
horns, ears, a lock of hair and a beard. The horns are the wings you turn it with.

The outline is built with shapely, not with build123d: the 2D offsets of OCCT fail on it.
shapely's buffers give an exact morphological closing (notches narrower than a line are
filled) and opening (every tip is at least two lines wide), the same operations the width
tests use, so the outline passes them by construction.
"""

from functools import cache
from math import hypot

from build123d import Circle, Pos, Sketch
from shapely import Point, Polygon, unary_union
from shapely.affinity import scale, translate

from common.shapes import polygon
from common.tux import symmetric_face

from . import params as P

# The drawing, in "head units", horns up (+y). The head and the beard are symmetric
# about x = 0; the horns and the ears are given for the right side and mirrored.
HEAD = [(0.0, 0.40), (0.34, 0.38), (0.58, 0.22), (0.62, 0.0), (0.54, -0.3),
        (0.42, -0.6), (0.38, -0.9), (0.28, -1.05), (0.0, -1.09)]  # right half, top to chin
BEARD = [(0.26, -0.98), (0.28, -1.2), (0.21, -1.44), (0.12, -1.32), (0.0, -1.68),
         (-0.12, -1.32), (-0.21, -1.44), (-0.28, -1.2), (-0.26, -0.98)]
# Strokes: points of the centre line, each with the width there.
HORN = [((0.34, 0.30), 0.27), ((0.62, 0.25), 0.22), ((0.86, 0.29), 0.19),
        ((1.0, 0.41), 0.16), ((1.04, 0.57), 0.13), ((0.98, 0.72), 0.09)]
EAR = [((0.52, 0.05), 0.18), ((0.72, -0.03), 0.14), ((0.9, -0.14), 0.07)]
TUFT = [((0.0, 0.3), 0.24), ((0.02, 0.48), 0.18), ((0.1, 0.6), 0.12),
        ((0.2, 0.64), 0.07)]  # one lock that curls to the side: not mirrored
# Holes, (centre, radius) on the right side, mirrored.
EYE = ((0.42, 0.16), 0.075)
NOSTRIL = ((0.15, -0.96), 0.045)
AXIS_Y = -0.42  # the screw axis, between the eyes and the nostrils

CLOSE_R = P.LINE_W / 2 + 0.1  # closing: fills notches narrower than about a line
OPEN_R = P.lines(2) / 2 + 0.05  # opening: rounds every tip to at least two lines


def _smooth(points: list, n: int = 12) -> list:
    """A Catmull-Rom curve through the (point, width) list, n samples per segment."""
    pts = [points[0], *points, points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        (p0, _), (p1, w1), (p2, w2), (p3, _) = pts[i - 1:i + 3]
        for k in range(n):
            t = k / n
            xy = tuple(0.5 * (2 * p1[j] + (p2[j] - p0[j]) * t
                              + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t
                              + (3 * p1[j] - p0[j] - 3 * p2[j] + p3[j]) * t ** 3)
                       for j in (0, 1))
            out.append((xy, w1 + (w2 - w1) * t))
    out.append(points[-1])
    return out


def _stroke(points: list):
    """A tapering stroke: the hull of each pair of consecutive discs along the line."""
    discs = [Point(x, y).buffer(w / 2, quad_segs=32) for (x, y), w in _smooth(points)]
    return unary_union([a.union(b).convex_hull for a, b in zip(discs, discs[1:])])


def _mirror(geom):
    return scale(geom, -1, 1, origin=(0, 0))


@cache
def _drawing():
    """The whole outline in head units, with the screw axis at the origin."""
    wire = symmetric_face(HEAD, 1.0).outer_wire()
    head = Polygon([(p.X, p.Y) for p in (wire.position_at(k / 400) for k in range(400))])
    sides = [_stroke(HORN), _stroke(EAR)]
    parts = [head, Polygon(BEARD), _stroke(TUFT), *sides, *map(_mirror, sides)]
    return translate(unary_union(parts), 0, -AXIS_Y)


def gnu_scale(radius: float) -> float:
    """mm per head unit, so that the gnu turns within `radius` of the axis."""
    return radius / max(hypot(x, y) for x, y in _drawing().exterior.coords)


def holes(radius: float) -> list[tuple[float, float, float]]:
    """The eyes and the nostrils as (x, y, radius) in mm, around the axis."""
    s = gnu_scale(radius)
    out = []
    for (x, y), r in (EYE, NOSTRIL):
        for side in (1, -1):
            out.append((side * x * s, (y - AXIS_Y) * s, max(P.lines(4) / 2, r * s)))
    return out


@cache
def gnu_sketch(radius: float) -> Sketch:
    """The gnu knob, horns towards +y, turning within `radius` around the origin (the
    screw axis). It carries the screw's plain shank (SHANK_R) on its middle."""
    s = gnu_scale(radius)
    shape = scale(_drawing(), s, s, origin=(0, 0))
    shape = shape.union(Point(0, 0).buffer(P.SHANK_R + P.LINE_W, quad_segs=64))
    shape = shape.buffer(CLOSE_R, quad_segs=32).buffer(-CLOSE_R, quad_segs=32)
    shape = shape.buffer(-OPEN_R, quad_segs=32).buffer(OPEN_R, quad_segs=32)
    shape = shape.simplify(0.01)
    if shape.geom_type != "Polygon" or shape.interiors:
        raise ValueError("the gnu outline is not one simple shape")
    knob = polygon(*shape.exterior.coords[:-1])
    for x, y, r in holes(radius):
        # a hole under the shank would leave the shank's bottom face hanging in the air
        if hypot(x, y) - r < P.SHANK_R + P.LINE_W:
            raise ValueError(f"knob radius {radius}: a hole runs under the screw's shank")
        # and it keeps a wall of at least two lines to the outline
        if not shape.contains(Point(x, y).buffer(r + P.lines(2), quad_segs=32)):
            raise ValueError(f"knob radius {radius}: a hole has less than two lines of wall")
        knob -= Pos(x, y) * Circle(r)
    return knob
