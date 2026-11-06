"""Tux Clip: the parts per colour, the desk version, the flexure coupon and the mechanics.

All parts print on their back. `params.py` explains the mechanism and the frames.

The flexure is a leaf of length L. Its top end is fixed to the body, its bottom end
carries the flipper. A force on the flipper bends the leaf with a curvature that changes
linearly along it (the bending moment of a force grows with the distance from it), so
the leaf is not a circular arc. Two loads matter:

- "squeeze": the fingers press the top of the shoulder pad, and at full swing the stop
  pushes back at the same place (local a = a_pt, above the leaf). This load sets the
  stop and the opening.
- "jaw": an object in the jaw pushes the flipper tip open (local a = a_tip, below the
  leaf). This load sets the clamping force, and it can also push the flipper to the stop.

`leaf_point` integrates the bent shape, `pose(m, theta, load)` moves the flipper with the
end of the leaf, and `leaf_local` draws the bent leaf. The same geometry gives the print
model (theta = 0), the GIF frames and the collision checks.
"""

from dataclasses import dataclass
from functools import cache
from math import cos, degrees, radians, sin

import numpy as np
from build123d import (
    Box,
    Circle,
    Kind,
    Location,
    Part,
    Plane,
    Pos,
    Rectangle,
    Rot,
    Sketch,
    Vector,
    extrude,
    offset,
)

from common.shapes import polygon
from common.tux import mirror_x, spline_face, tux_profile

from . import params as P

LOADS = ("squeeze", "jaw")
_GAUSS = np.polynomial.legendre.leggauss(16)


def jaw_direction() -> Vector:
    """Unit vector along the jaw line of the right flipper: down and out."""
    return Vector(sin(P.FLIPPER_ANGLE), -cos(P.FLIPPER_ANGLE), 0)


@dataclass(frozen=True)
class Mechanism:
    """The flexure and jaw of the right flipper for one size (the left one is mirrored)."""

    size: str
    height: float
    opening: float  # jaw opening at the flipper tip at full squeeze (mm)
    t: float  # leaf thickness
    L: float  # leaf length
    a_pt: float  # top of the shoulder pad (local a; negative = above the pivot)
    a_tip: float  # tip of the flipper (local a)
    theta_stop: float  # the swing where the pad meets the body when squeezed (rad)
    theta_stop_jaw: float  # the same stop when an object pushes the jaw open (rad)
    g_top: float  # slot between pad and shoulder at the top of the pad
    pivot: tuple[float, float]  # virtual pivot (middle of the leaf), global x, y

    @property
    def d(self) -> Vector:
        return jaw_direction()

    @property
    def plane(self) -> Plane:
        """Local frame of the right mechanism: x = a (down the jaw line), y = b (outwards)."""
        return Plane(origin=(*self.pivot, 0), x_dir=self.d, z_dir=(0, 0, 1))

    def load_line(self, load: str) -> float:
        """Local a where the load acts: the pad top ("squeeze") or the flipper tip ("jaw")."""
        return {"squeeze": self.a_pt, "jaw": self.a_tip}[load]

    def stop(self, load: str) -> float:
        return {"squeeze": self.theta_stop, "jaw": self.theta_stop_jaw}[load]

    def strain(self, theta: float, load: str = "squeeze") -> float:
        """Peak bending strain in the leaf for a swing of theta."""
        return peak_strain(self.t, self.L, theta, self.load_line(load))

    @property
    def stiffness(self) -> float:
        """Rotational stiffness of the leaf (N mm / rad). The swing is the integral of the
        curvature, so a force F at distance a_tip turns the flipper by F a_tip / stiffness,
        whatever the shape of the bend."""
        return P.PETG_E_FLEX * P.T_BODY * self.t**3 / (12 * self.L)

    def opening_at(self, theta: float, load: str = "squeeze") -> float:
        return opening_at(self.L, self.a_tip, theta, self.load_line(load))

    @property
    def max_gap(self) -> float:
        """The thickest object the jaw takes: pushed open up to the stop."""
        return self.opening_at(self.theta_stop_jaw, "jaw")

    def theta_for(self, gap: float) -> float:
        """Swing of a flipper held open to `gap` at the tip by an object in the jaw."""
        if gap > self.max_gap + 1e-9:
            raise ValueError(f"{gap} mm does not fit a jaw that opens {self.max_gap:.2f} mm")
        return _bisect(lambda th: self.opening_at(th, "jaw"), gap, hi=self.theta_stop_jaw)

    def force(self, thickness: float) -> float:
        """Clamping force (N) on a flat, stiff object held at the flipper tip."""
        return self.stiffness * self.theta_for(thickness) / self.a_tip


def leaf_angle(L: float, theta: float, a_load: float, a):
    """Slope of the leaf at local a (rad) when its end has turned by theta.

    The curvature is theta / L * (1 - a / a_load): linear along the leaf, zero on the load
    line, and its integral over the leaf is theta. Works on numpy arrays too.
    """
    return theta / L * ((a + L / 2) - (a * a - L * L / 4) / (2 * a_load))


def leaf_point(L: float, theta: float, a_load: float, a: float) -> tuple[float, float]:
    """Local (a, b) of the point of the leaf centre line that is at (a, 0) at rest."""
    x, w = _GAUSS
    half = (a + L / 2) / 2
    s = -L / 2 + (x + 1) * half
    phi = leaf_angle(L, theta, a_load, s)
    return -L / 2 + half * float(np.dot(w, np.cos(phi))), half * float(np.dot(w, np.sin(phi)))


def leaf_end(L: float, theta: float, a_load: float) -> tuple[float, float]:
    """Local (a, b) of the lower end of the leaf (the top end is fixed)."""
    return leaf_point(L, theta, a_load, L / 2)


def peak_strain(t: float, L: float, theta: float, a_load: float) -> float:
    """Largest bending strain in the leaf: at the end farther from the load line."""
    return t * theta / (2 * L) * (1 + L / (2 * abs(a_load)))


def pose_point(L: float, theta: float, a_load: float, a: float, b: float) -> tuple[float, float]:
    """Where a point of the flipper (local a, b at rest) goes when the flipper swings."""
    ea, eb = leaf_end(L, theta, a_load)
    da = a - L / 2
    return ea + da * cos(theta) - b * sin(theta), eb + da * sin(theta) + b * cos(theta)


def opening_at(L: float, a_tip: float, theta: float, a_load: float) -> float:
    """Gap between the tooth tips at the flipper tip (negative = teeth still overlap)."""
    tip_b = pose_point(L, theta, a_load, a_tip, P.JAW_W / 2 - P.TOOTH_D)[1]
    return tip_b - (P.TOOTH_D - P.JAW_W / 2)


def _bisect(f, target: float, lo: float = 0.0, hi: float = 1.5, steps: int = 50) -> float:
    """Where the increasing function f reaches target, between lo and hi."""
    for _ in range(steps):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < target else (lo, mid)
    return (lo + hi) / 2


def _g_top(L: float, a_pt: float, t: float, theta: float) -> float:
    """Pad-to-shoulder slot that closes exactly at the squeeze swing theta (the pad's top
    inner corner lands on the shoulder face b = t/2)."""
    ea, eb = leaf_end(L, theta, a_pt)
    # pose_point(...)[1] == t/2 for the corner (a_pt, t/2 + g): a linear equation in g
    return (t / 2 - eb - (a_pt - L / 2) * sin(theta)) / cos(theta) - t / 2


def _stops(L: float, a_tip: float, t: float, theta: float) -> tuple[float, float, float]:
    """For a squeeze stop at theta: (g_top, jaw stop, peak strain at the worse stop)."""
    a_pt = -L / 2 - P.PAD_TOP
    g = _g_top(L, a_pt, t, theta)
    corner = (a_pt, t / 2 + g)
    theta_jaw = _bisect(lambda th: -pose_point(L, th, a_tip, *corner)[1], -t / 2)
    strain = max(peak_strain(t, L, theta, a_pt), peak_strain(t, L, theta_jaw, a_tip))
    return g, theta_jaw, strain


def _max_swing(L: float, a_tip: float, t: float) -> float:
    """The largest squeeze stop that keeps the leaf within PETG_SAFE_STRAIN under both
    loads. The strain grows almost linearly with the stop angle, so a few rescaling steps
    are enough."""
    a_pt = -L / 2 - P.PAD_TOP
    theta = 2 * P.PETG_SAFE_STRAIN * L / (t * (1 + L / (2 * abs(a_pt))))
    for _ in range(20):
        strain = _stops(L, a_tip, t, theta)[2]
        if strain <= P.PETG_SAFE_STRAIN:
            break
        theta *= P.PETG_SAFE_STRAIN / strain * (1 - 1e-9)
    return theta


def _teeth(L: float, a_tip: float) -> list[float]:
    """Centres (local a) of the jaw teeth from the bridge down: body, flipper, body..."""
    a = L / 2 + P.BRIDGE + P.TOOTH_GAP + P.TOOTH_W / 2
    centres = []
    while a + P.TOOTH_W / 2 <= a_tip - 0.4:
        centres.append(a)
        a += P.TOOTH_W + P.TOOTH_GAP
    return centres


def _solve(height: float, opening: float, t: float) -> tuple[float, float, float, float]:
    """Leaf length for the target opening, with the leaf within PETG_SAFE_STRAIN at both
    stops.

    The flipper has a fixed length, so a longer leaf leaves a shorter jaw (the pivot sits in
    the middle of the leaf). Every leaf keeps at least MIN_TEETH teeth on the jaw. Returns
    (L, a_tip, theta_stop, opening): the shortest leaf that reaches the target opening, or,
    if none does (thick leaves), the leaf that gives the largest opening.
    """
    length = P.FLIPPER_LEN * height
    best = None
    for step in range(20, 4000):
        L = step * 0.05
        a_tip = length - L / 2 - P.PAD_TOP
        if len(_teeth(L, a_tip)) < P.MIN_TEETH:
            break
        a_pt = -L / 2 - P.PAD_TOP
        theta_max = _max_swing(L, a_tip, t)
        reach = opening_at(L, a_tip, theta_max, a_pt)
        if reach >= opening:
            theta = _bisect(lambda th: opening_at(L, a_tip, th, a_pt), opening, hi=theta_max)
            return L, a_tip, theta, opening
        if best is None or reach > best[3]:
            best = (L, a_tip, theta_max, reach)
    if best is None or best[3] <= 0:
        raise ValueError(f"no leaf fits a {height} mm Tux")
    return best


@cache
def mechanism(size: str, flex_lines: int = P.FLEX_LINES) -> Mechanism:
    """The mechanism of one size. Thicker leaves are stiffer but open less."""
    spec = P.SIZES[size]
    h = spec["height"]
    t = P.lines(flex_lines)
    L, a_tip, theta, opening = _solve(h, spec["opening"], t)
    return _mechanism(size, h, opening, t, L, a_tip, theta)


def _mechanism(size, h, opening, t, L, a_tip, theta) -> Mechanism:
    g, theta_jaw, _ = _stops(L, a_tip, t, theta)
    shoulder = Vector(P.SHOULDER[0] * h, P.SHOULDER[1] * h, 0)
    pivot = shoulder + jaw_direction() * (L / 2 + P.PAD_TOP)
    return Mechanism(size=size, height=h, opening=opening, t=t, L=L, a_pt=-L / 2 - P.PAD_TOP,
                     a_tip=a_tip, theta_stop=theta, theta_stop_jaw=theta_jaw, g_top=g,
                     pivot=(pivot.X, pivot.Y))


@cache
def coupon_mechanism(flex_lines: int) -> Mechanism:
    """A coupon lever: the COUPON_SIZE flipper and leaf length, with a leaf of `flex_lines`
    lines. Its stop keeps the strain within PETG_SAFE_STRAIN, so thicker leaves open less."""
    base = mechanism(P.COUPON_SIZE)
    t = P.lines(flex_lines)
    theta = min(base.theta_stop, _max_swing(base.L, base.a_tip, t))
    return _mechanism(f"coupon_{flex_lines}", base.height,
                      opening_at(base.L, base.a_tip, theta, base.a_pt), t, base.L, base.a_tip,
                      theta)


# --- 2D geometry of one mechanism, in its local frame (a, b) ---------------------------

def _box(a0: float, a1: float, b0: float, b1: float) -> Sketch:
    return Pos((a0 + a1) / 2, (b0 + b1) / 2) * Rectangle(a1 - a0, b1 - b0)


def wedge_b(m: Mechanism, a: float) -> float:
    """Inner edge of the shoulder pad: a straight slot that widens towards the top."""
    b0, b1 = m.t / 2 + P.SLOT_MIN, m.t / 2 + m.g_top
    return b0 + (b1 - b0) * (m.L / 2 - a) / (m.L / 2 - m.a_pt)


def teeth_positions(m: Mechanism) -> tuple[list[float], list[float]]:
    """Centres (local a) of the body teeth and of the flipper teeth, alternating."""
    teeth = _teeth(m.L, m.a_tip)
    return teeth[0::2], teeth[1::2]


def flipper_envelope(m: Mechanism) -> Sketch:
    """Outer shape of the flipper (a Tux flipper: wide at the shoulder, round tip).

    The inner side reaches past the jaw line; `flipper_local` trims it to the slots.
    """
    h, W = m.height, P.JAW_W
    top_out = m.t / 2 + m.g_top + max(P.lines(5), 0.05 * h)  # pad: room to press on
    widest = top_out + 0.02 * h
    tip_w = W / 2 + 0.05 * h
    span = m.a_tip - m.a_pt
    pts = [(m.a_pt - 2.0, -3.0), (m.a_pt - 2.0, top_out - 2.0), (m.a_pt + 0.3, top_out),
           (m.a_pt + 0.30 * span, widest), (m.a_pt + 0.68 * span, (widest + tip_w) / 2),
           (m.a_tip - 0.02 * h, tip_w), (m.a_tip + 0.012 * h, W / 2 + 0.3 * (tip_w - W / 2)),
           (m.a_tip + 0.5, -3.0), (0.0, -3.5)]
    return Sketch() + spline_face(pts)


@cache
def flipper_local(m: Mechanism) -> Sketch:
    """The flipper (shoulder pad, jaw and its teeth) at rest, without the leaf."""
    t, W = m.t, P.JAW_W
    far = m.a_tip + 20
    allowed = polygon((m.a_pt, wedge_b(m, m.a_pt)), (m.L / 2, m.t / 2 + P.SLOT_MIN),
                    (m.L / 2, -t / 2), (m.L / 2 + P.BRIDGE, -t / 2),
                    (m.L / 2 + P.BRIDGE, W / 2), (far, W / 2), (far, 60), (m.a_pt, 60))
    flipper = flipper_envelope(m) & allowed
    for a in teeth_positions(m)[1]:
        flipper += _box(a - P.TOOTH_W / 2, a + P.TOOTH_W / 2, W / 2 - P.TOOTH_D, W / 2 + 0.05)
    return flipper


def leaf_local(m: Mechanism, theta: float = 0.0, load: str = "squeeze",
               overlap: float = 0.05) -> Sketch:
    """The leaf, straight at rest or bent by theta under `load`. Both ends reach `overlap`
    into the body and the flipper, so the joints are solid."""
    t, L = m.t, m.L
    if abs(theta) < 1e-6:
        return _box(-L / 2 - overlap, L / 2 + overlap, -t / 2, t / 2)
    a_load = m.load_line(load)
    n = max(12, 2 * int(degrees(theta)))
    outer, inner = [], []  # outer: the side at b = -t/2 at rest
    for a in np.linspace(-L / 2, L / 2, n + 1):
        x, y = leaf_point(L, theta, a_load, float(a))
        phi = float(leaf_angle(L, theta, a_load, a))
        outer.append(Vector(x + sin(phi) * t / 2, y - cos(phi) * t / 2))
        inner.append(Vector(x - sin(phi) * t / 2, y + cos(phi) * t / 2))
    tangent = Vector(cos(theta), sin(theta))
    pts = ([(-L / 2 - overlap, -t / 2)] + [(p.X, p.Y) for p in outer]
           + [((outer[-1] + tangent * overlap).X, (outer[-1] + tangent * overlap).Y),
              ((inner[-1] + tangent * overlap).X, (inner[-1] + tangent * overlap).Y)]
           + [(p.X, p.Y) for p in reversed(inner)] + [(-L / 2 - overlap, t / 2)])
    return polygon(*pts)


def leaf_slot_b(m: Mechanism) -> float:
    """Body edge beside the leaf and the bridge: at least SLOT_MIN from them. With a thin
    leaf this is simply the jaw face; a thick leaf needs a step back."""
    return min(-P.JAW_W / 2, -m.t / 2 - P.SLOT_MIN)


def _flank(m: Mechanism) -> list[tuple[float, float]]:
    """Body edge from the shoulder stop down past the leaf and the bridge to the jaw face."""
    t, W, b_ls = m.t, P.JAW_W, leaf_slot_b(m)
    pts = [(-m.L / 2, t / 2), (-m.L / 2, b_ls)]
    if b_ls < -W / 2 - 1e-9:
        a_step = m.L / 2 + P.BRIDGE + P.TOOTH_GAP
        pts += [(a_step, b_ls), (a_step, -W / 2)]
    return pts


def pocket_local(m: Mechanism) -> Sketch:
    """Space cut out of Tux's body at rest: the slots around the leaf and the jaw."""
    t, W = m.t, P.JAW_W
    top = m.a_pt - 0.5
    low = m.a_tip + 0.03 * m.height
    return polygon((top, t / 2), *_flank(m), (low, -W / 2), (low, 80), (top, 80))


def body_extra_local(m: Mechanism) -> Sketch:
    """Body material along the jaw line (the fixed jaw and the shoulder over the leaf).

    Its outer edge above the leaf (b = t/2) is the stop for the shoulder pad.
    """
    t, W = m.t, P.JAW_W
    top = stop_face_top(m)
    return polygon((top - 3.0, jaw_back(m)), (top, t / 2), *_flank(m), (m.a_tip, -W / 2),
                 (m.a_tip, jaw_back(m)))


def stop_contact(m: Mechanism, load: str) -> float:
    """Local a where the pad's top inner corner lands on the shoulder face at the stop."""
    corner = (m.a_pt, m.t / 2 + m.g_top)
    return pose_point(m.L, m.stop(load), m.load_line(load), *corner)[0]


def stop_face_top(m: Mechanism) -> float:
    """Upper end of the flat stop face (b = t/2): STOP_MARGIN past the highest contact."""
    return min(m.a_pt - 2.0, min(stop_contact(m, load) for load in LOADS) - P.STOP_MARGIN)


def jaw_back(m: Mechanism) -> float:
    """Back edge of the fixed jaw strip (4 mm of material behind the jaw face)."""
    return min(-P.JAW_W / 2, leaf_slot_b(m)) - 4.0


def body_teeth_local(m: Mechanism) -> Sketch:
    W = P.JAW_W
    teeth = Sketch()
    for a in teeth_positions(m)[0]:
        teeth += _box(a - P.TOOTH_W / 2, a + P.TOOTH_W / 2, -W / 2 - 0.05, -W / 2 + P.TOOTH_D)
    return teeth


def pose(m: Mechanism, theta: float, load: str = "squeeze") -> Location:
    """Local motion of the flipper for a swing of theta under `load` (rest: identity)."""
    ea, eb = leaf_end(m.L, theta, m.load_line(load))
    return Pos(ea, eb) * Rot(0, 0, degrees(theta)) * Pos(-m.L / 2, 0)


def _both_sides(m: Mechanism, local: Sketch) -> Sketch:
    right = m.plane.location * local
    return right + mirror_x(right)


@cache
def sweep_local(m: Mechanism, steps: int = 16) -> Sketch:
    """Area swept by the flipper and the leaf over the whole swing, under both loads
    (local frame)."""
    flipper = flipper_local(m)
    swept = Sketch()
    for load in LOADS:
        for k in range(steps + 1):
            theta = m.stop(load) * k / steps
            swept += pose(m, theta, load) * flipper
            swept += leaf_local(m, theta, load)
    return swept


@cache
def body_profile(m: Mechanism) -> Sketch:
    """The fixed part of the black profile: Tux's body with room for both flippers."""
    tux = tux_profile(m.height)
    room = pocket_local(m) + offset(sweep_local(m), P.SLOT_MIN, kind=Kind.ARC)
    body = tux.body - _both_sides(m, room)
    # the jaw, its teeth and the shoulder stop are drawn exactly, after the cut
    return body + _both_sides(m, body_extra_local(m)) + _both_sides(m, body_teeth_local(m))


def moving_local(m: Mechanism, theta: float = 0.0, load: str = "squeeze") -> Sketch:
    """Leaf and flipper of the right side, swung by theta (local frame)."""
    return leaf_local(m, theta, load) + pose(m, theta, load) * flipper_local(m)


def clip_profile(m: Mechanism, theta: float = 0.0, load: str = "squeeze",
                 right_only: bool = False) -> Sketch:
    """The black profile of the clip with the flippers swung by theta under `load`; with
    right_only, the left flipper stays at rest (the desk version holding a card)."""
    right = m.plane.location * moving_local(m, theta, load)
    left = m.plane.location * moving_local(m, 0.0) if right_only else right
    return body_profile(m) + right + mirror_x(left)


def flipper_placed(m: Mechanism, theta: float, load: str = "squeeze") -> Sketch:
    """The right flipper (without the leaf) swung by theta, in Tux coordinates."""
    return m.plane.location * (pose(m, theta, load) * flipper_local(m))


# --- 3D parts, per colour ----------------------------------------------------------------

def clip_colours(size: str, theta: float = 0.0, load: str = "squeeze",
                 right_only: bool = False) -> tuple[tuple[Part, str], ...]:
    """The clip of one size as (part, colour), stacked along Z, flippers swung by theta
    (see clip_profile). Only the print pose (theta = 0) is cached: animation frames are
    used once."""
    if theta == 0:
        return _clip_at_rest(size)
    return _clip_colours(size, theta, load, right_only)


@cache
def _clip_at_rest(size: str) -> tuple[tuple[Part, str], ...]:
    return _clip_colours(size, 0.0)


def _clip_colours(size: str, theta: float, load: str = "squeeze",
                  right_only: bool = False) -> tuple[tuple[Part, str], ...]:
    m = mechanism(size)
    tux = tux_profile(m.height)
    black = extrude(clip_profile(m, theta, load, right_only), P.T_BODY, dir=(0, 0, 1))
    white = Pos(0, 0, P.Z_WHITE) * extrude(tux.white, P.T_WHITE, dir=(0, 0, 1))
    orange = Pos(0, 0, P.Z_ORANGE) * extrude(tux.orange, P.T_ORANGE, dir=(0, 0, 1))
    return ((black, "black"), (white, "white"), (orange, "orange"))


@cache
def make_clip(size: str) -> Part:
    """The printable clip (one piece, print-in-place)."""
    black, white, orange = (p for p, _ in clip_colours(size))
    clip = black + white + orange
    clip.label = f"tux_clip_{size}"
    return clip


# --- desk version: Tux lies on an ice floe and holds a card upright ---------------------

def floe_sketch(m: Mechanism) -> Sketch:
    """A flat, slightly irregular ice floe around Tux."""
    h, r = m.height, P.BASE_MARGIN
    w = 0.42 * h + r
    pts = [(0.0, -r), (0.55 * w, -r + 1.0), (w, 0.08 * h), (w + 1.5, 0.35 * h),
           (0.92 * w, 0.62 * h), (0.70 * w, 0.86 * h), (0.25 * w, h + 0.4 * r),
           (-0.30 * w, h + 0.5 * r), (-0.74 * w, 0.84 * h), (-w - 1.0, 0.55 * h),
           (-w, 0.25 * h), (-0.85 * w, 0.02 * h), (-0.45 * w, -r + 0.5)]
    return Sketch() + spline_face(pts)


def desk_colours(theta: float = 0.0, load: str = "squeeze",
                 right_only: bool = False) -> tuple[tuple[Part, str], ...]:
    """The desk version as (part, colour): the clip plus a floe that leaves the flippers
    free over their whole swing, with a groove along each jaw line for a card."""
    clip = clip_colours(P.DESK_SIZE, theta, load, right_only)
    return ((clip[0][0] + desk_floe(), "black"), clip[1], clip[2])


def card_groove_local(m: Mechanism) -> Sketch:
    """The groove through the floe: the jaw line continued past the flipper tip."""
    return _box(m.L / 2 + P.BRIDGE, m.a_tip + 200, -P.JAW_W / 2,
                -P.JAW_W / 2 + P.CARD_GROOVE)


@cache
def desk_floe() -> Part:
    m = mechanism(P.DESK_SIZE)
    free = offset(sweep_local(m), P.FLIPPER_CLEARANCE, kind=Kind.ARC) + card_groove_local(m)
    return extrude(floe_sketch(m) - _both_sides(m, free), P.T_BASE, dir=(0, 0, 1))


def desk_card(thickness: float = 0.4, width: float = 85.0,
              height: float = 55.0) -> tuple[Part, float]:
    """A card standing on the desk in the right jaw of the desk version, and the swing
    (under the "jaw" load) that lets it in.

    The card starts at the top of the jaw and runs past the flipper tip, through the
    groove in the floe; it lies just outside the body's tooth tips. The swing is the
    smallest that clears every flipper tooth tip.
    """
    m = mechanism(P.DESK_SIZE)
    a0 = m.L / 2 + P.BRIDGE + 0.3
    b0 = P.TOOTH_D - P.JAW_W / 2 + 0.05  # just past the body's tooth tips
    tips = [(a + s * P.TOOTH_W / 2, P.JAW_W / 2 - P.TOOTH_D)
            for a in teeth_positions(m)[1] for s in (-1, 1)]

    def clearance(theta: float) -> float:
        return min(pose_point(m.L, theta, m.a_tip, a, b)[1] for a, b in tips)

    theta = _bisect(clearance, b0 + thickness + 0.05, hi=m.theta_stop_jaw)
    card = Pos(a0 + width / 2, b0 + thickness / 2, height / 2) * Box(width, thickness, height)
    return m.plane.location * card, theta


@cache
def make_desk() -> Part:
    black, white, orange = (p for p, _ in desk_colours())
    desk = black + white + orange
    desk.label = "tux_clip_desk"
    return desk


def card_hold_margin(mass_g: float, height: float, thickness: float,
                     tilt_deg: float = 5.0) -> float:
    """How well the desk version holds a card upright in a flipper slot (> 1 = it holds).

    Static check: the card leans by tilt_deg; its weight at half its height tries to turn
    it over the slot. The jaw clamps the card over the whole slot depth (T_BODY), so the
    clamping force on the two faces makes a resisting couple of about F x T_BODY. Friction
    and the comb teeth only help, so they are left out.
    """
    m = mechanism(P.DESK_SIZE)
    if thickness > m.max_gap:
        return 0.0  # it does not even fit in the jaw
    weight = mass_g * 9.81e-3
    tipping = weight * height / 2 * sin(radians(tilt_deg))
    holding = m.force(thickness) * P.T_BODY
    return holding / tipping


# --- flexure coupon ----------------------------------------------------------------------

def _coupon_levers() -> list[Mechanism]:
    return [coupon_mechanism(n) for n in P.COUPON_LINES]


@cache
def coupon_pitch() -> float:
    """Lever spacing: a flipper's whole swing stays 1.5 mm from the next fixed jaw."""
    levers = _coupon_levers()
    reach = max(sweep_local(m).bounding_box().max.Y for m in levers)
    return reach + 1.5 + max(-jaw_back(m) for m in levers)


def coupon_plane(k: int) -> Plane:
    """Local frame of coupon lever k: the jaw line points straight down (-y)."""
    return Plane(origin=(k * coupon_pitch(), 0, 0), x_dir=(0, -1, 0), z_dir=(0, 0, 1))


def _coupon_bar() -> tuple[float, float, float, float]:
    """(x0, x1, y0, y1) of the top bar that holds the three fixed jaws."""
    levers = _coupon_levers()
    top_of_strip = max(-(m.a_pt - 5.0) for m in levers)  # local a = -y
    swing_top = max(-sweep_local(m).bounding_box().min.X for m in levers)
    y0 = max(top_of_strip - 1.0, swing_top + 1.5)
    x0 = min(jaw_back(m) for m in levers)
    x1 = (len(levers) - 1) * coupon_pitch() + max(
        sweep_local(m).bounding_box().max.Y for m in levers)
    return x0, x1, y0, y0 + 4.0


def coupon_profile(theta_fraction: float = 0.0) -> Sketch:
    """Bar with three levers on 2, 3 and 4 line leaves, each swung by a fraction of its own
    stop angle. Only the print pose is cached."""
    return _coupon_at_rest() if theta_fraction == 0 else _coupon_profile(theta_fraction)


@cache
def _coupon_at_rest() -> Sketch:
    return _coupon_profile(0.0)


def _coupon_profile(theta_fraction: float) -> Sketch:
    x0, x1, y0, y1 = _coupon_bar()
    profile = _box(x0, x1, y0, y1)
    for k, m in enumerate(_coupon_levers()):
        loc = coupon_plane(k).location
        profile += loc * (body_extra_local(m) + body_teeth_local(m))
        profile += loc * _box(m.a_pt - 7.0, m.a_pt - 2.0, jaw_back(m), m.t / 2)  # to the bar
        profile += loc * moving_local(m, m.theta_stop * theta_fraction)
    return profile


def coupon_dots() -> Part:
    """1, 2 and 3 raised dots (2 layers high) on the bar above the three levers."""
    x0, x1, y0, y1 = _coupon_bar()
    dots = Sketch()
    for k in range(len(P.COUPON_LINES)):
        for j in range(k + 1):
            dots += Pos(k * coupon_pitch() + 1.0 + 2.0 * j, (y0 + y1) / 2) * Circle(0.6)
    return Pos(0, 0, P.T_BODY) * extrude(dots, P.layers(2), dir=(0, 0, 1))


@cache
def make_coupon() -> Part:
    """The flexure coupon: one colour, no colour change. 1, 2, 3 dots = 2, 3, 4 lines."""
    coupon = extrude(coupon_profile(), P.T_BODY, dir=(0, 0, 1)) + coupon_dots()
    coupon.label = "coupon_flexure"
    return coupon


def summary(size: str) -> str:
    m = mechanism(size)
    body, flipper = teeth_positions(m)
    return (f"{size}: H={m.height:.0f} opening={m.opening:.2f} (max gap {m.max_gap:.2f}) "
            f"L={m.L:.2f} a_tip={m.a_tip:.2f} teeth={len(body)}+{len(flipper)} "
            f"stop={degrees(m.theta_stop):.1f}/{degrees(m.theta_stop_jaw):.1f} deg "
            f"strain={m.strain(m.theta_stop):.4f}/{m.strain(m.theta_stop_jaw, 'jaw'):.4f} "
            f"g_top={m.g_top:.2f} k={m.stiffness:.1f} Nmm/rad "
            f"F(0)={m.force(0):.3f} N F(1)={m.force(1.0):.3f} N "
            f"F(open)={m.force(m.opening):.3f} N")


if __name__ == "__main__":
    for s in P.SIZES:
        print(summary(s))
