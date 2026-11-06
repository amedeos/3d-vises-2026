"""Tux Clip: the parts per colour, the desk version, the flexure coupon and the mechanics.

All parts print on their back. `params.py` explains the mechanism and the frames.

The flexure is a leaf of length L that bends with constant curvature (pure bending). Its
bottom end carries the flipper, so a flipper swing of theta moves the flipper exactly like
the end of that circular arc. `pose(m, theta)` gives that motion, and `clip_profile(m,
theta)` draws the clip bent by theta, with the leaf drawn as an arc. The same geometry
gives the print model (theta = 0), the GIF frames and the collision checks.
"""

from dataclasses import dataclass
from functools import cache
from math import cos, degrees, sin, sqrt

from build123d import (
    Circle,
    Kind,
    Location,
    Part,
    Plane,
    Polygon,
    Pos,
    Rectangle,
    Rot,
    Sketch,
    Vector,
    extrude,
    offset,
)

from common.tux import mirror_x, spline_face, tux_profile

from . import params as P


@dataclass(frozen=True)
class Mechanism:
    """The flexure and jaw of the right flipper for one size (the left one is mirrored)."""

    size: str
    height: float
    opening: float  # target jaw opening at the flipper tip (mm)
    t: float  # leaf thickness
    L: float  # leaf length
    a_pt: float  # top of the shoulder pad (local a; negative = above the pivot)
    a_tip: float  # tip of the flipper (local a)
    theta_stop: float  # the swing where the pad meets the body (rad)
    g_top: float  # slot between pad and shoulder at the top of the pad
    pivot: tuple[float, float]  # virtual pivot (middle of the leaf), global x, y

    @property
    def d(self) -> Vector:  # along the jaw line, down and out
        return Vector(sin(P.FLIPPER_ANGLE), -cos(P.FLIPPER_ANGLE), 0)

    @property
    def plane(self) -> Plane:
        """Local frame of the right mechanism: x = a (down the jaw line), y = b (outwards)."""
        return Plane(origin=(*self.pivot, 0), x_dir=self.d, z_dir=(0, 0, 1))

    def strain(self, theta: float) -> float:
        """Peak bending strain in the leaf for a swing of theta."""
        return self.t * theta / (2 * self.L)

    @property
    def stiffness(self) -> float:
        """Rotational stiffness of the leaf (N mm / rad)."""
        return P.PETG_E_FLEX * P.T_BODY * self.t**3 / (12 * self.L)

    def opening_at(self, theta: float) -> float:
        return opening_at(self.L, self.a_tip, theta)

    def theta_for(self, gap: float) -> float:
        """Swing that opens the jaw tip to `gap` (bisection)."""
        lo, hi = 0.0, 1.5
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if self.opening_at(mid) < gap else (lo, mid)
        return (lo + hi) / 2

    def force(self, thickness: float) -> float:
        """Clamping force (N) on a flat, stiff object held at the flipper tip."""
        theta = self.theta_for(thickness)
        return self.stiffness * theta / self.a_tip


def arc_end(L: float, theta: float) -> tuple[float, float]:
    """Local (a, b) of the lower end of a leaf of length L bent by theta (top end fixed)."""
    if abs(theta) < 1e-9:
        return L / 2, 0.0
    return -L / 2 + L * sin(theta) / theta, L * (1 - cos(theta)) / theta


def pose_point(L: float, theta: float, a: float, b: float) -> tuple[float, float]:
    """Where a point of the flipper (local a, b at rest) goes when the flipper swings."""
    ea, eb = arc_end(L, theta)
    da, db = a - L / 2, b
    return ea + da * cos(theta) - db * sin(theta), eb + da * sin(theta) + db * cos(theta)


def opening_at(L: float, a_tip: float, theta: float) -> float:
    """Gap between the tooth tips at the flipper tip (negative = teeth still overlap)."""
    tip_b = pose_point(L, theta, a_tip, P.JAW_W / 2 - P.TOOTH_D)[1]
    return tip_b - (P.TOOTH_D - P.JAW_W / 2)


def _g_top(L: float, a_pt: float, t: float, theta: float) -> float:
    """Pad-to-shoulder slot that closes exactly at the swing theta (pad's top inner corner
    lands on the shoulder face b = t/2)."""
    ea, eb = arc_end(L, theta)
    # pose_point(...)[1] == t/2 for the corner (a_pt, t/2 + g): solve the linear equation
    g = (t / 2 - eb - (a_pt - L / 2) * sin(theta)) / cos(theta) - t / 2
    return g


def _solve(height: float, opening: float, t: float) -> tuple[float, float, float, float]:
    """Leaf length for the target opening, with the strain at full opening within
    PETG_SAFE_STRAIN.

    The flipper has a fixed length, so a longer leaf leaves a shorter jaw (the pivot sits in
    the middle of the leaf). Returns (L, a_tip, theta_stop, opening): the shortest leaf that
    reaches the target opening, or, if none does (thick leaves), the leaf that gives the
    largest opening.
    """
    length = P.FLIPPER_LEN * height
    best = None
    for step in range(20, 4000):
        L = step * 0.05
        a_tip = length - L / 2 - P.PAD_TOP
        if a_tip <= L / 2 + P.BRIDGE + 2:
            break
        theta = mechanism_theta(L, a_tip, opening)
        if t * theta / (2 * L) <= P.PETG_SAFE_STRAIN:
            return L, a_tip, theta, opening
        theta_max = 2 * P.PETG_SAFE_STRAIN * L / t
        reach = opening_at(L, a_tip, theta_max)
        if best is None or reach > best[3]:
            best = (L, a_tip, theta_max, reach)
    if best is None or best[3] <= 0:
        raise ValueError(f"no leaf fits a {height} mm Tux")
    return best


def mechanism_theta(L: float, a_tip: float, opening: float) -> float:
    lo, hi = 0.0, 1.5
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if opening_at(L, a_tip, mid) < opening else (lo, mid)
    return (lo + hi) / 2


@cache
def mechanism(size: str, flex_lines: int = P.FLEX_LINES) -> Mechanism:
    """The mechanism of one size. Thicker leaves are stiffer but open less."""
    spec = P.SIZES[size]
    h = spec["height"]
    t = P.lines(flex_lines)
    L, a_tip, theta, opening = _solve(h, spec["opening"], t)
    return _mechanism(size, h, opening, t, L, a_tip, theta)


def _mechanism(size, h, opening, t, L, a_tip, theta) -> Mechanism:
    a_pt = -L / 2 - P.PAD_TOP
    shoulder = Vector(P.SHOULDER[0] * h, P.SHOULDER[1] * h, 0)
    d = Vector(sin(P.FLIPPER_ANGLE), -cos(P.FLIPPER_ANGLE), 0)
    pivot = shoulder + d * (L / 2 + P.PAD_TOP)
    return Mechanism(size=size, height=h, opening=opening, t=t, L=L, a_pt=a_pt, a_tip=a_tip,
                     theta_stop=theta, g_top=_g_top(L, a_pt, t, theta),
                     pivot=(pivot.X, pivot.Y))


def coupon_mechanism(flex_lines: int) -> Mechanism:
    """A coupon lever: the COUPON_SIZE flipper and leaf length, with a leaf of `flex_lines`
    lines. Its stop keeps the strain within PETG_SAFE_STRAIN, so thicker leaves open less."""
    base = mechanism(P.COUPON_SIZE)
    t = P.lines(flex_lines)
    theta = min(base.theta_stop, 2 * P.PETG_SAFE_STRAIN * base.L / t)
    return _mechanism(f"coupon_{flex_lines}", base.height, opening_at(base.L, base.a_tip, theta),
                      t, base.L, base.a_tip, theta)


# --- 2D geometry of one mechanism, in its local frame (a, b) ---------------------------

def _poly(*pts) -> Sketch:
    return Sketch() + Polygon(*pts, align=None)


def _box(a0: float, a1: float, b0: float, b1: float) -> Sketch:
    return Pos((a0 + a1) / 2, (b0 + b1) / 2) * Rectangle(a1 - a0, b1 - b0)


def wedge_b(m: Mechanism, a: float) -> float:
    """Inner edge of the shoulder pad: a straight slot that widens towards the top."""
    b0, b1 = m.t / 2 + P.SLOT_MIN, m.t / 2 + m.g_top
    return b0 + (b1 - b0) * (m.L / 2 - a) / (m.L / 2 - m.a_pt)


def teeth_positions(m: Mechanism) -> tuple[list[float], list[float]]:
    """Centres (local a) of the body teeth and of the flipper teeth, alternating."""
    half_pitch = P.TOOTH_W + P.TOOTH_GAP
    a = m.L / 2 + P.BRIDGE + P.TOOTH_GAP + P.TOOTH_W / 2
    body, flipper = [], []
    k = 0
    while a + P.TOOTH_W / 2 <= m.a_tip - 0.4:
        (body if k % 2 == 0 else flipper).append(a)
        a += half_pitch
        k += 1
    return body, flipper


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


def flipper_local(m: Mechanism) -> Sketch:
    """The flipper (shoulder pad, jaw and its teeth) at rest, without the leaf."""
    t, W = m.t, P.JAW_W
    far = m.a_tip + 20
    allowed = _poly((m.a_pt, wedge_b(m, m.a_pt)), (m.L / 2, m.t / 2 + P.SLOT_MIN),
                    (m.L / 2, -t / 2), (m.L / 2 + P.BRIDGE, -t / 2),
                    (m.L / 2 + P.BRIDGE, W / 2), (far, W / 2), (far, 60), (m.a_pt, 60))
    flipper = flipper_envelope(m) & allowed
    for a in teeth_positions(m)[1]:
        flipper += _box(a - P.TOOTH_W / 2, a + P.TOOTH_W / 2, W / 2 - P.TOOTH_D, W / 2 + 0.05)
    return flipper


def leaf_local(m: Mechanism, theta: float = 0.0, overlap: float = 0.05) -> Sketch:
    """The leaf, straight at rest or bent into a circular arc by theta."""
    t, L = m.t, m.L
    if abs(theta) < 1e-6:
        return _box(-L / 2 - overlap, L / 2 + overlap, -t / 2, t / 2)
    R = L / theta
    centre = Vector(-L / 2, R)
    n = max(8, int(degrees(theta)))
    outer, inner = [], []
    for k in range(n + 1):
        phi = theta * k / n
        u = Vector(sin(phi), -cos(phi))
        outer.append(centre + u * (R + t / 2))
        inner.append(centre + u * (R - t / 2))
    tangent = Vector(cos(theta), sin(theta))
    pts = ([(-L / 2 - overlap, -t / 2)] + [(p.X, p.Y) for p in outer]
           + [((outer[-1] + tangent * overlap).X, (outer[-1] + tangent * overlap).Y),
              ((inner[-1] + tangent * overlap).X, (inner[-1] + tangent * overlap).Y)]
           + [(p.X, p.Y) for p in reversed(inner)] + [(-L / 2 - overlap, t / 2)])
    return _poly(*pts)


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
    return _poly((top, t / 2), *_flank(m), (low, -W / 2), (low, 80), (top, 80))


def body_extra_local(m: Mechanism) -> Sketch:
    """Body material along the jaw line (the fixed jaw and the shoulder over the leaf).

    Its outer edge above the leaf (b = t/2) is the stop for the shoulder pad.
    """
    t, W = m.t, P.JAW_W
    top = m.a_pt - 2.0
    return _poly((top - 3.0, jaw_back(m)), (top, t / 2), *_flank(m), (m.a_tip, -W / 2),
                 (m.a_tip, jaw_back(m)))


def jaw_back(m: Mechanism) -> float:
    """Back edge of the fixed jaw strip (4 mm of material behind the jaw face)."""
    return min(-P.JAW_W / 2, leaf_slot_b(m)) - 4.0


def body_teeth_local(m: Mechanism) -> Sketch:
    W = P.JAW_W
    teeth = Sketch()
    for a in teeth_positions(m)[0]:
        teeth += _box(a - P.TOOTH_W / 2, a + P.TOOTH_W / 2, -W / 2 - 0.05, -W / 2 + P.TOOTH_D)
    return teeth


def pose(m: Mechanism, theta: float) -> Location:
    """Local motion of the flipper for a swing of theta (rest: identity)."""
    ea, eb = arc_end(m.L, theta)
    return Pos(ea, eb) * Rot(0, 0, degrees(theta)) * Pos(-m.L / 2, 0)


def _both_sides(m: Mechanism, local: Sketch) -> Sketch:
    right = m.plane.location * local
    return right + mirror_x(right)


@cache
def sweep_local(m: Mechanism, steps: int = 16) -> Sketch:
    """Area swept by the flipper and the leaf over the whole swing (local frame)."""
    swept = Sketch()
    for k in range(steps + 1):
        theta = m.theta_stop * k / steps
        swept += pose(m, theta) * flipper_local(m)
        swept += leaf_local(m, theta)
    return swept


@cache
def body_profile(m: Mechanism) -> Sketch:
    """The fixed part of the black profile: Tux's body with room for both flippers."""
    tux = tux_profile(m.height)
    room = pocket_local(m) + offset(sweep_local(m), P.SLOT_MIN, kind=Kind.ARC)
    body = tux.body - _both_sides(m, room)
    # the jaw, its teeth and the shoulder stop are drawn exactly, after the cut
    return body + _both_sides(m, body_extra_local(m)) + _both_sides(m, body_teeth_local(m))


def moving_local(m: Mechanism, theta: float = 0.0) -> Sketch:
    """Leaf and flipper of the right side, swung by theta (local frame)."""
    return leaf_local(m, theta) + pose(m, theta) * flipper_local(m)


def clip_profile(m: Mechanism, theta: float = 0.0) -> Sketch:
    """The black profile of the clip with both flippers swung by theta."""
    return body_profile(m) + _both_sides(m, moving_local(m, theta))


def flipper_placed(m: Mechanism, theta: float) -> Sketch:
    """The right flipper (without the leaf) swung by theta, in Tux coordinates."""
    return m.plane.location * (pose(m, theta) * flipper_local(m))


# --- 3D parts, per colour ----------------------------------------------------------------

@cache
def clip_colours(size: str, theta: float = 0.0) -> tuple[tuple[Part, str], ...]:
    """The clip of one size as (part, colour), stacked along Z, flippers swung by theta."""
    m = mechanism(size)
    tux = tux_profile(m.height)
    black = extrude(clip_profile(m, theta), P.T_BODY, dir=(0, 0, 1))
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


@cache
def desk_colours(theta: float = 0.0) -> tuple[tuple[Part, str], ...]:
    """The desk version as (part, colour): the clip plus a floe that leaves the flippers
    free over their whole swing."""
    m = mechanism(P.DESK_SIZE)
    clip = clip_colours(P.DESK_SIZE, theta)
    free = _both_sides(m, offset(sweep_local(m), P.FLIPPER_CLEARANCE, kind=Kind.ARC))
    base = extrude(floe_sketch(m) - free, P.T_BASE, dir=(0, 0, 1))
    return ((clip[0][0] + base, "black"), clip[1], clip[2])


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
    weight = mass_g * 9.81e-3
    tipping = weight * height / 2 * sin(tilt_deg * 3.141592653589793 / 180)
    holding = m.force(thickness) * P.T_BODY
    return holding / tipping


# --- flexure coupon ----------------------------------------------------------------------

def _coupon_levers() -> list[Mechanism]:
    return [coupon_mechanism(n) for n in P.COUPON_LINES]


def coupon_pitch() -> float:
    """Lever spacing: a flipper's whole swing fits before the next fixed jaw."""
    reach = max(sweep_local(m).bounding_box().max.Y for m in _coupon_levers())
    return reach + 1.5 + P.JAW_W / 2 + 4.0


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


@cache
def coupon_profile(theta_fraction: float = 0.0) -> Sketch:
    """Bar with three levers on 2, 3 and 4 line leaves, each swung by a fraction of its own
    stop angle."""
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
    return (f"{size}: H={m.height:.0f} L={m.L:.2f} a_tip={m.a_tip:.2f} "
            f"theta_stop={degrees(m.theta_stop):.1f} deg strain={m.strain(m.theta_stop):.4f} "
            f"g_top={m.g_top:.2f} k={m.stiffness:.1f} Nmm/rad "
            f"F(0)={m.force(0):.3f} N F(1)={m.force(1.0):.3f} N "
            f"F(open)={m.force(m.opening):.3f} N")


if __name__ == "__main__":
    for s in P.SIZES:
        print(summary(s))
