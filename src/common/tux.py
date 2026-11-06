"""The Tux profile: flat 2D regions, one per colour, parametric by height.

A simplified Tux, seen from the front, built from smooth closed splines and ellipses.
All shapes are in the XY plane: x to the right, y up, feet on y=0, centre line on x=0.
The numbers below are fractions of the height H; `tux_profile(H)` scales them.

Colours are stacked in Z when the part prints on its back (see the model packages):
black body, then white (belly, eyes, and pads under the beak and feet), then orange
(beak, feet). So every white region lies inside the black body and every orange region
lies inside a white region.
"""

from dataclasses import dataclass
from functools import cache, cached_property

from build123d import (
    Edge,
    Ellipse,
    Face,
    Kind,
    Plane,
    Pos,
    Sketch,
    Vector,
    Wire,
    mirror,
    offset,
)

# right half of the outline (x >= 0), from the bottom centre up to the top of the head;
# fractions of H. The body is a pear: wide hips, a soft neck, a round head.
BODY_HALF = [(0.00, 0.035), (0.16, 0.045), (0.26, 0.10), (0.305, 0.20), (0.305, 0.31),
             (0.28, 0.42), (0.235, 0.52), (0.205, 0.60), (0.205, 0.69), (0.20, 0.79),
             (0.165, 0.90), (0.09, 0.97), (0.00, 0.99)]
BELLY_HALF = [(0.00, 0.075), (0.13, 0.085), (0.205, 0.15), (0.225, 0.26), (0.21, 0.38),
              (0.165, 0.50), (0.12, 0.60), (0.075, 0.665), (0.00, 0.685)]
EYE = (0.062, 0.80, 0.052, 0.078)  # centre x, centre y, half width, half height (right eye)
PUPIL = (0.068, 0.79, 0.024, 0.030)  # looking slightly inwards
BEAK = (0.0, 0.695, 0.115, 0.048)  # centre x, centre y, half width, half height
BEAK_TIP = (0.0, 0.668, 0.07, 0.03)  # lower beak, a smaller ellipse under the upper one
FOOT = (0.15, 0.045, 0.13, 0.045)  # right foot: centre x, centre y, half width, half height
CREVICE_R = 0.3  # mm: notches narrower than 2 x this are filled (see close_crevices)


def spline_face(points: list[tuple[float, float]]) -> Face:
    """A smooth closed face through the points (a periodic spline)."""
    edge = Edge.make_spline([Vector(x, y, 0) for x, y in points], periodic=True)
    return Face(Wire([edge]))


def symmetric_face(half: list[tuple[float, float]], scale: float) -> Face:
    """Closed face from the right half of an outline (both ends on x=0), mirrored."""
    right = [(x * scale, y * scale) for x, y in half]
    left = [(-x, y) for x, y in reversed(right[1:-1])]
    return spline_face(right + left)


def _ellipse(spec, scale: float, mirror_x: bool = False) -> Sketch:
    cx, cy, rx, ry = (v * scale for v in spec)
    return Pos(-cx if mirror_x else cx, cy) * Ellipse(rx, ry)


def _pair(spec, scale: float) -> Sketch:
    return _ellipse(spec, scale) + _ellipse(spec, scale, mirror_x=True)


@dataclass(frozen=True)
class TuxProfile:
    """The 2D regions of Tux for one height. All are build123d Sketches."""

    height: float
    body: Sketch  # black: head, body and the area under the feet (no flippers)
    belly: Sketch  # white
    eyes: Sketch  # white
    pupils: Sketch  # holes in the white (the black body shows through)
    beak: Sketch  # orange (on a white pad of the same shape)
    feet: Sketch  # orange (on a white pad of the same shape)

    @cached_property
    def white(self) -> Sketch:
        """Everything printed white: belly, eyes, and the pads under the beak and feet."""
        return close_crevices(self.belly + self.eyes + self.beak + self.feet) - self.pupils

    @cached_property
    def orange(self) -> Sketch:
        return close_crevices(self.beak + self.feet)


@cache
def tux_profile(height: float) -> TuxProfile:
    """Tux scaled to `height` (mm), feet on y=0."""
    h = height
    body = Sketch() + symmetric_face(BODY_HALF, h) + _pair(FOOT, h)
    beak = Sketch() + _ellipse(BEAK, h) + _ellipse(BEAK_TIP, h)
    return TuxProfile(
        height=h,
        body=body,
        belly=Sketch() + symmetric_face(BELLY_HALF, h),
        eyes=_pair(EYE, h),
        pupils=_pair(PUPIL, h),
        beak=beak,
        feet=_pair(FOOT, h),
    )


def close_crevices(sketch: Sketch, radius: float = CREVICE_R) -> Sketch:
    """Fill the sharp notches where two shapes meet (morphological closing).

    Where the belly meets a foot, or the upper beak meets the lower beak, the outlines
    cross at a sharp angle and leave a notch narrower than one line. The slicer cannot
    print into it. Growing by `radius` and shrinking back rounds those notches off; gaps
    wider than 2 x radius (like the one between the eyes) stay open.
    """
    return offset(offset(sketch, radius, kind=Kind.ARC), -radius, kind=Kind.ARC)


def mirror_x(sketch: Sketch) -> Sketch:
    """Mirror a sketch across the centre line (x -> -x)."""
    return mirror(sketch, Plane.YZ)
