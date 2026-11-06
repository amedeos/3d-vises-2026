"""Tux Vise: every part in its print pose, and where it goes in the vise.

Print poses (each part rests on z = 0):

- Tux: on his back, like the clip. Black plate, white and orange reliefs on top.
- base: upright, as used.
- jaw: upright, as used, shifted down by JAW_Z0.
- fork: flat.
- nut: thread axis vertical.
- screw: thread axis vertical, standing on its gnu knob; the head is at the top.
- coupon: the gauge strip flat (holes vertical), the stub standing on a gnu knob too.

`use_location(name, opening)` moves a part from its print pose into the vise, with the
jaw opened by `opening` (mm, from the white belly to the jaw face).
"""

from functools import cache
from math import sqrt

from build123d import (
    Align,
    Box,
    Circle,
    Cylinder,
    Location,
    Part,
    Plane,
    Pos,
    Rectangle,
    Rot,
    Sketch,
    extrude,
)

from common.grid import snap_down
from common.shapes import box_between, polygon, teardrop
from common.tux import close_crevices, spline_face, tux_profile

from . import params as P
from .gnu import gnu_sketch
from .thread import screw_thread, threaded_hole

# Plane that maps a flat print pose (x across, y up, z = thickness) onto a part standing
# in the vise and facing +x: print x -> y, print y -> z, print z -> x.
def _standing(x: float, y: float, z: float) -> Plane:
    return Plane(origin=(x, y, z), x_dir=(0, 1, 0), z_dir=(1, 0, 0))


def _yz(sketch: Sketch, x0: float, x1: float) -> Part:
    """A (y, z) sketch extruded along x from x0 to x1."""
    plane = Plane(origin=(x0, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
    return extrude(plane * sketch, x1 - x0, dir=(1, 0, 0))


def _xz(sketch: Sketch, y0: float, y1: float) -> Part:
    """An (x, z) sketch extruded along y from y0 to y1."""
    plane = Plane(origin=(0, y0, 0), x_dir=(1, 0, 0), z_dir=(0, -1, 0))
    return extrude(plane * sketch, y1 - y0, dir=(0, 1, 0))


def _bore_x(radius: float, x0: float, x1: float, y: float, z: float) -> Part:
    """Horizontal teardrop hole along x (roof up), for parts printed upright."""
    return _yz(Pos(y, z) * teardrop(radius), x0, x1)


# --- Tux, the fixed jaw ---------------------------------------------------------------------

def tenon_depth() -> float:
    """The tab under Tux's feet stops short of the bottom of the base: Tux stands on his
    feet, not on the tab."""
    return P.T_PLATE - 0.4


@cache
def tux_colours() -> tuple[tuple[Part, str], ...]:
    """Tux on his back, as (part, colour) from the bottom up."""
    tux = tux_profile(P.TUX_H)
    # the tab reaches up into the body between the feet (it is higher there than under them)
    top = (tux.body & Rectangle(1.0, 20.0)).bounding_box().min.Y + 1.0
    tenon = Pos(0, (top - tenon_depth()) / 2) * Rectangle(P.TENON_W, top + tenon_depth())
    # the corners where the tab meets the feet are narrower than a line: fill them, but
    # only above the soles (Tux stands on the base)
    filled = close_crevices(tux.body + tenon) & (Pos(0, 50) * Rectangle(200, 100))
    black = extrude(filled + tenon, P.T_TUX, dir=(0, 0, 1))
    white = Pos(0, 0, P.Z_WHITE) * extrude(tux.white, P.T_WHITE, dir=(0, 0, 1))
    orange = Pos(0, 0, P.Z_ORANGE) * extrude(tux.orange, P.T_ORANGE, dir=(0, 0, 1))
    return ((black, "black"), (white, "white"), (orange, "orange"))


@cache
def make_tux() -> Part:
    black, white, orange = (p for p, _ in tux_colours())
    tux = black + white + orange
    tux.label = "tux_vise_tux"
    return tux


def feet_top() -> float:
    """Height of the top of Tux's feet in the vise (z)."""
    return P.T_PLATE + tux_profile(P.TUX_H).feet.bounding_box().max.Y


# --- base: plate, rail, backstop, end block -------------------------------------------------

def rail_points(grow: float = 0.0, z_floor: float = P.T_PLATE - 0.5,
                top: float | None = None) -> list[tuple[float, float]]:
    """(y, z) outline of the dovetail rail (stem + 45-degree head), grown by `grow`.

    Every edge moves outwards by exactly `grow`, measured at right angles (the Halloween
    coffin rail). `top` replaces the top height.
    """
    sw = P.RAIL_STEM_W / 2 + grow
    hw = P.RAIL_HEAD_W / 2 + grow
    flare = P.RAIL_HEAD_W / 2 - P.RAIL_STEM_W / 2  # 45 degrees: rise = run
    z0 = P.RAIL_HEAD_Z0 - grow * (sqrt(2) - 1)
    z_flare_top = z0 + flare
    z1 = P.RAIL_HEAD_Z1 + grow if top is None else top
    right = [(sw, z0), (hw, z_flare_top)]
    if z1 - z_flare_top > 1e-6:
        right.append((hw, z1))
    left = [(-y, z) for y, z in reversed(right)]
    return [(-sw, z_floor - grow), (sw, z_floor - grow), *right, *left]


def slot_top() -> float:
    """Top of the jaw's rail slot (before its roof), on a layer boundary of the jaw."""
    return P.JAW_Z0 + P.snap_up(P.RAIL_HEAD_Z1 + P.CLR_SLIDE - P.JAW_Z0)


def slot_points() -> list[tuple[float, float]]:
    """(y, z) outline of the jaw's slot: the rail grown by CLR_SLIDE, with a 45-degree
    roof instead of a flat ceiling (the jaw prints upright)."""
    pts = rail_points(P.CLR_SLIDE, z_floor=P.JAW_Z0 - 1.0, top=slot_top())
    hw = P.RAIL_HEAD_W / 2 + P.CLR_SLIDE
    k = len(pts) // 2 + 1  # after the right half, before the left half
    return pts[:k] + [(0.0, slot_top() + hw)] + pts[k:]


def end_block_top() -> float:
    return P.snap_up(P.Z_AXIS + P.NUT_W / 2 + P.CLR_FIT)


@cache
def make_base() -> Part:
    """The base, printed upright as used."""
    hw, top_hw = P.BASE_W / 2, P.BASE_W / 2 - P.BEVEL
    plate = _yz(polygon((-hw, 0), (hw, 0), (top_hw, P.BEVEL), (top_hw, P.T_PLATE),
                      (-top_hw, P.T_PLATE), (-top_hw, P.BEVEL)), 0, P.BASE_L)
    rail = _yz(polygon(*rail_points()), P.X_RAIL0, P.X_END + 0.5)
    bw, bh, ch = P.BACK_W / 2, P.BACK_H, 6.0  # backstop with 45-degree shoulders
    back = _yz(polygon((-bw, 0), (bw, 0), (bw, bh - ch), (bw - ch, bh), (-bw + ch, bh),
                     (-bw, bh - ch)), 0, P.X_TUX - P.CLR_FIT)
    ew = P.NUT_W / 2 + P.CLR_FIT + P.WALL_SIDE
    block = box_between(P.X_END, P.BASE_L, -ew, ew, 0, end_block_top())
    base = plate + rail + back + block
    # mortise for Tux's tab, through the plate
    tw = P.TENON_W / 2 + P.CLR_FIT
    base -= box_between(P.X_TUX - P.CLR_FIT, P.X_TUX + P.T_TUX + P.CLR_FIT, -tw, tw, -1,
                        P.T_PLATE + 1)
    # nut pocket, open at the top, and the screw's hole through both walls
    pw = P.NUT_W / 2 + P.CLR_FIT
    base -= box_between(P.X_POCKET0, P.X_POCKET1, -pw, pw, P.POCKET_FLOOR,
                        end_block_top() + 1)
    base -= _bore_x(P.THREAD_D / 2 + P.CLR_BORE, P.X_END - 1, P.BASE_L + 1, 0, P.Z_AXIS)
    base.label = "tux_vise_base"
    return base


# --- the moving jaw (a flipper) and the fork ---------------------------------------------

def jaw_top() -> float:
    """Top of the jaw (z): 1.5 mm under Tux's beak, which stands proud of the belly."""
    return P.T_PLATE + tux_profile(P.TUX_H).beak.bounding_box().min.Y - 1.5


@cache
def flipper_sketch() -> Sketch:
    """Front view (y, z) of the moving jaw: a flipper, wide on the rail, round at the top,
    leaning a little to one side. In jaw coordinates: z = 0 is the bottom of the jaw."""
    h = jaw_top() - P.JAW_Z0
    pts = [(17.6, -3.0), (17.2, 0.15 * h), (15.4, 0.38 * h), (11.8, 0.62 * h),
           (6.4, 0.84 * h), (0.6, 0.98 * h), (-4.8, 1.0 * h), (-9.6, 0.94 * h),
           (-13.2, 0.77 * h), (-15.6, 0.52 * h), (-17.0, 0.26 * h), (-17.6, -3.0)]
    flipper = Sketch() + spline_face(pts)
    return flipper & (Pos(0, 50) * Rectangle(60, 100))


def fork_x() -> float:
    """Jaw coordinate x of the fork slot (from the clamping face)."""
    return P.FACE_T + P.HEAD_L + P.HEAD_PLAY


def fork_slot_bottom() -> float:
    """Jaw coordinate z of the bottom of the fork slot, on a layer boundary. The fork rests
    on it, its tines at least fork_tine_below() under the neck."""
    return snap_down(P.Z_AXIS - P.NECK_D / 2 - fork_tine_below() - P.JAW_Z0)


def fork_tine_below() -> float:
    """How far the fork's tines reach below the neck of the screw."""
    return 2.5


@cache
def make_jaw() -> Part:
    """The moving jaw in its print pose (upright; z = 0 is its bottom, x = 0 its face)."""
    jaw = _yz(flipper_sketch(), 0, P.JAW_T)
    dz = -P.JAW_Z0  # use z -> jaw z
    jaw -= Pos(0, 0, dz) * _yz(polygon(*slot_points()), -1, P.JAW_T + 1)
    # The lower front steps back over Tux's feet, with a 45-degree ceiling. The ceiling
    # stays above the roof of the rail slot: where two 45-degree roofs cross, the line
    # where they meet is flatter than 45 degrees and PrusaSlicer wants support under it.
    slot_peak = slot_top() + P.RAIL_HEAD_W / 2 + P.CLR_SLIDE - P.JAW_Z0
    z1 = P.snap_up(max(feet_top() + 0.6 - P.JAW_Z0, slot_peak + P.LAYER))
    r = P.FEET_RECESS
    jaw -= _xz(polygon((-1, -1), (r, -1), (r, z1), (0, z1 + r), (-1, z1 + r + 1)), -30, 30)
    # the head chamber and the bore behind it (the head passes through at assembly)
    jaw -= _bore_x(P.HEAD_D / 2 + 0.4, P.FACE_T, P.JAW_T + 1, 0, P.Z_AXIS + dz)
    # the fork's slot, open at the top; where the flipper gets too narrow for two lines of
    # wall beside it, the slot runs across the whole jaw
    fw = P.FORK_W / 2 + P.CLR_FORK
    x0, x1 = fork_x(), fork_x() + P.FORK_T + 2 * P.CLR_FORK
    jaw -= box_between(x0, x1, -fw, fw, fork_slot_bottom(), 60)
    jaw -= box_between(x0, x1, -30, 30, fork_slot_split(), 60)
    jaw.label = "tux_vise_jaw"
    return jaw


def flipper_half_width(z: float) -> float:
    """Half-width of the narrower side of the flipper at jaw height z."""
    bb = (flipper_sketch() & (Pos(0, z) * Rectangle(80, 0.01))).bounding_box()
    return min(-bb.min.X, bb.max.X)


@cache
def fork_slot_split() -> float:
    """Jaw height from which the fork slot runs across the whole jaw: below it, both walls
    beside the slot are at least two lines thick."""
    need = P.FORK_W / 2 + P.CLR_FORK + P.lines(2) + 0.1
    z = fork_slot_bottom()
    while flipper_half_width(z + P.LAYER) >= need:
        z += P.LAYER
    return z


def fork_height() -> float:
    """From the tips of the tines to the top, which stands 2 mm above the jaw (to pull it
    out)."""
    return jaw_top() + 2.0 - (P.JAW_Z0 + fork_slot_bottom())


@cache
def make_fork() -> Part:
    """The fork, flat: tines down (y = 0 at their tips), the screw's neck between them."""
    w, h = P.FORK_W / 2, fork_height()
    gap = P.NECK_D / 2 + P.CLR_FORK
    # resting on the slot floor, the top of the opening clears the neck by CLR_FORK
    neck_top = P.Z_AXIS + gap - (P.JAW_Z0 + fork_slot_bottom())
    outline = polygon((-w, 0), (w, 0), (w, h - w), (0, h), (-w, h - w))
    fork = extrude(outline - polygon((-gap, -1), (gap, -1), (gap, neck_top),
                                   (-gap, neck_top)), P.FORK_T, dir=(0, 0, 1))
    fork.label = "tux_vise_fork"
    return fork


# --- nut and screw -----------------------------------------------------------------------

@cache
def make_nut(clearance: float = P.CLR_THREAD) -> Part:
    """The square nut insert, thread axis vertical."""
    block = Box(P.NUT_W, P.NUT_W, P.NUT_L, align=(Align.CENTER, Align.CENTER, Align.MIN))
    nut = threaded_hole(block, 0, 0, P.NUT_L, clearance)
    nut.label = "tux_vise_nut"
    return nut


def screw_stations() -> dict[str, float]:
    """Distances along the screw from its tip (s = 0, in the jaw) to the knob.

    head: 0 -> HEAD_L, neck -> thread0, thread0 -> thread1, plain shank -> knob,
    knob -> length.
    """
    tip_closed = P.X_BELLY + P.FACE_T  # tip x with the jaw closed (opening 0)
    thread0 = (P.JAW_T - P.FACE_T) + P.THREAD_GAP
    thread1 = P.snap_up(P.X_POCKET1 + 0.6 - tip_closed)  # past the nut when closed
    knob = P.snap_up(P.BASE_L + P.KNOB_GAP - tip_closed)
    return {"head": P.HEAD_L, "thread0": thread0, "thread1": thread1, "knob": knob,
            "length": knob + P.KNOB_T}


@cache
def make_screw() -> Part:
    """The screw standing on its gnu knob (print pose): knob at z = 0, head at the top."""
    st = screw_stations()
    length = st["length"]
    z = lambda s: length - s  # noqa: E731  (screw station -> print height)
    # use_location turns the knob's +y downwards: turned over, the gnu's horns point up
    # in the renders at every whole turn from fully open (render.upright). On a printed
    # vise the knob's angle at a given opening depends on how the nut sits in its pocket.
    knob = extrude(Rot(0, 0, 180) * gnu_sketch(P.GNU_R), P.KNOB_T, dir=(0, 0, 1))
    # 0.1 mm wider than the thread, so the thread's square end sits on it
    shank = Pos(0, 0, P.KNOB_T) * Cylinder(P.SHANK_R, z(st["thread1"]) - P.KNOB_T,
                                           align=(Align.CENTER, Align.CENTER, Align.MIN))
    thread = Pos(0, 0, z(st["thread1"])) * screw_thread(st["thread1"] - st["thread0"])
    neck = Pos(0, 0, z(st["thread0"])) * Cylinder(
        P.NECK_D / 2, st["thread0"] - st["head"] + 0.01,
        align=(Align.CENTER, Align.CENTER, Align.MIN))
    cone_h = (P.HEAD_D - P.NECK_D) / 2  # 45 degrees under the head
    cone = Pos(0, 0, z(st["head"])) * extrude(Circle(P.NECK_D / 2), cone_h,
                                              taper=-45.0, dir=(0, 0, 1))
    head = Pos(0, 0, z(st["head"]) + cone_h) * Cylinder(
        P.HEAD_D / 2, st["head"] - cone_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    screw = knob + shank + thread + neck + cone + head
    screw.label = "tux_vise_screw"
    return screw


# --- where each part goes in the vise --------------------------------------------------------

def jaw_x(opening: float) -> float:
    """x of the jaw's clamping face."""
    return P.X_BELLY + opening


def tip_x(opening: float) -> float:
    """x of the screw tip when it pushes the jaw (tip on the chamber floor)."""
    return jaw_x(opening) + P.FACE_T


def nut_x0() -> float:
    """x of the nut's inner end, centred in its pocket."""
    return P.X_POCKET0 + P.CLR_FIT


def use_location(name: str, opening: float = 0.0) -> Location:
    """Location that moves a part from its print pose into the vise."""
    if name == "tux":
        return _standing(P.X_TUX, 0, P.T_PLATE).location
    if name == "base":
        return Location()
    if name == "jaw":
        return Location((jaw_x(opening), 0, P.JAW_Z0))
    if name == "fork":  # resting on the floor of its slot
        z = P.JAW_Z0 + fork_slot_bottom()
        return _standing(jaw_x(opening) + fork_x() + P.CLR_FORK, 0, z).location
    if name == "nut":
        return Plane(origin=(nut_x0(), 0, P.Z_AXIS), x_dir=(0, 1, 0),
                     z_dir=(1, 0, 0)).location
    if name == "screw":
        length = screw_stations()["length"]
        return Plane(origin=(tip_x(opening) + length, 0, P.Z_AXIS), x_dir=(0, 1, 0),
                     z_dir=(-1, 0, 0)).location
    raise KeyError(name)


VISE_PARTS = {"tux": make_tux, "base": make_base, "jaw": make_jaw, "fork": make_fork,
              "nut": make_nut, "screw": make_screw}


def assembly(opening: float = 0.0) -> dict[str, Part]:
    """Every part of the vise in place, with the jaw opened by `opening`."""
    return {name: use_location(name, opening) * build() for name, build in VISE_PARTS.items()}


# --- thread coupon -------------------------------------------------------------------------

GAUGE_HALF_W, GAUGE_MARGIN = 13.0, 11.0


def gauge_holes() -> list[tuple[float, float]]:
    """(x, y) of the coupon's four nut holes, in the order of THREAD_GAUGE."""
    return [(GAUGE_MARGIN + k * P.GAUGE_PITCH, -2.0) for k in range(len(P.THREAD_GAUGE))]


@cache
def make_gauge() -> Part:
    """Four nut holes with the THREAD_GAUGE clearances, marked with 1 to 4 dots."""
    n = len(P.THREAD_GAUGE)
    length = 2 * GAUGE_MARGIN + P.GAUGE_PITCH * (n - 1)
    strip = box_between(0, length, -GAUGE_HALF_W, GAUGE_HALF_W, 0, P.GAUGE_L)
    for clr, (x, y) in zip(P.THREAD_GAUGE, gauge_holes()):
        strip = threaded_hole(strip, x, y, P.GAUGE_L, clr)
    dots = Sketch()
    for k, (x, _) in enumerate(gauge_holes()):
        for d in range(k + 1):
            dots += Pos(x + (d - k / 2) * 2.2, GAUGE_HALF_W - 2.4) * Circle(0.8)
    strip += Pos(0, 0, P.GAUGE_L) * extrude(dots, P.layers(2), dir=(0, 0, 1))
    strip.label = "coupon_thread_gauge"
    return strip


@cache
def make_stub() -> Part:
    """20 mm of the real screw thread on a gnu knob, to try in the gauge's holes."""
    knob = extrude(gnu_sketch(P.GNU_R), P.KNOB_T, dir=(0, 0, 1))
    base = Pos(0, 0, P.KNOB_T) * Cylinder(P.SHANK_R, P.LAYER,
                                          align=(Align.CENTER, Align.CENTER, Align.MIN))
    stub = knob + base + Pos(0, 0, P.KNOB_T + P.LAYER) * screw_thread(P.GAUGE_STUB)
    stub.label = "coupon_thread_stub"
    return stub


# --- desk foot ------------------------------------------------------------------------------
# Built in the vise frame (x along the base, the channel floor at z = 0, the desk on the +y
# side of the spine), then turned onto its side for printing.

def _channel_half(z: float) -> float:
    """Half-width of the channel at height z: the base's bevelled bottom grown by
    CLR_SLIDE (measured at right angles)."""
    c = P.CLR_SLIDE
    return max(P.BASE_W / 2 + c * sqrt(2) - z, P.BASE_W / 2 - P.BEVEL + c)


def foot_layout() -> dict[str, float]:
    """y and z of the foot's features (vise frame; channel floor at z = 0)."""
    lip_out = _channel_half(0.0) + P.LIP_W
    spine1 = -lip_out  # the spine's inner face: it touches the desk edge
    nut_wall = P.NUT_WALL
    bottom1 = -(P.T_ARM + P.DESK_MAX)  # top of the bottom arm
    nut_h = P.NUT_L + 2 * P.CLR_FIT
    bottom0 = bottom1 - P.snap_up(nut_h + 2 * nut_wall)
    screw_y = spine1 + nut_wall + P.NUT_W / 2 + P.CLR_FIT
    return {"lip_out": lip_out, "spine0": spine1 - P.SPINE_T, "spine1": spine1,
            "bottom0": bottom0, "bottom1": bottom1, "nut0": bottom0 + nut_wall,
            "nut1": bottom0 + nut_wall + nut_h, "screw_y": screw_y,
            "arm_end": screw_y + P.NUT_W / 2 + P.CLR_FIT + nut_wall}


def _bore_z(radius: float, x: float, y: float, z0: float, z1: float) -> Part:
    """Vertical hole (vise frame) whose roof points to +x: horizontal when the foot lies
    on its side for printing."""
    plane = Plane(origin=(x, y, z0), x_dir=(0, -1, 0), z_dir=(0, 0, 1))
    return extrude(plane * teardrop(radius), z1 - z0, dir=(0, 0, 1))


@cache
def foot_in_place() -> Part:
    """The desk foot in the vise frame (channel floor at z = 0, x from -FOOT_CAP)."""
    f = foot_layout()
    ch0, lip_top = _channel_half(0.0), P.LIP_TOP
    profile = polygon(
        (f["spine0"], f["bottom0"]), (f["arm_end"], f["bottom0"]),
        (f["arm_end"], f["bottom1"]), (f["spine1"], f["bottom1"]),
        (f["spine1"], -P.T_ARM), (f["lip_out"], -P.T_ARM), (f["lip_out"], lip_top),
        (f["spine0"], lip_top))
    side = _channel_half(lip_top)  # the base's vertical side, grown
    knee = ch0 - side  # where the grown bevel meets it (45 degrees: rise = run)
    channel = polygon((-ch0, 0), (ch0, 0), (side, knee), (side, lip_top + 1),
                    (-side, lip_top + 1), (-side, knee))
    nut = polygon((f["screw_y"] - P.NUT_W / 2 - P.CLR_FIT, f["nut0"]),
                (f["screw_y"] + P.NUT_W / 2 + P.CLR_FIT, f["nut0"]),
                (f["screw_y"] + P.NUT_W / 2 + P.CLR_FIT, f["nut1"]),
                (f["screw_y"] - P.NUT_W / 2 - P.CLR_FIT, f["nut1"]))
    body = _yz(profile - channel - nut, 0, P.FOOT_L)
    cap = _yz(profile - nut, -P.FOOT_CAP, 0)  # the base stops against it
    foot = body + cap
    foot -= _bore_z(P.THREAD_D / 2 + P.CLR_BORE, P.FOOT_L / 2, f["screw_y"],
                    f["bottom0"] - 1, f["bottom1"] + 1)
    return foot


def foot_print_location() -> Location:
    """From the vise frame to the print pose: on its side, x up."""
    return _standing(0, 0, 0).location.inverse()


@cache
def make_foot() -> Part:
    foot = foot_print_location() * foot_in_place()
    bb = foot.bounding_box()
    foot = Pos(-bb.min.X, -bb.min.Y, -bb.min.Z) * foot
    foot.label = "tux_vise_foot"
    return foot


def foot_screw_stations() -> dict[str, float]:
    """Distances along the foot screw from its tip (s = 0, against the desk)."""
    f = foot_layout()
    tip_thin = -(P.T_ARM + P.DESK_MIN)  # the screw at its highest
    thread1 = P.snap_up(tip_thin - (f["nut0"] - P.CLR_FIT) + 0.6)  # covers the nut
    knob = P.snap_up(tip_thin - f["bottom0"] + 1.0)  # knob 1 mm under the arm
    return {"thread1": thread1, "knob": knob, "length": knob + P.KNOB_T}


@cache
def make_foot_screw() -> Part:
    """The foot screw standing on its gnu knob: thread at the top, tip flat."""
    st = foot_screw_stations()
    length = st["length"]
    knob = extrude(gnu_sketch(P.GNU_R), P.KNOB_T, dir=(0, 0, 1))
    shank = Pos(0, 0, P.KNOB_T) * Cylinder(P.SHANK_R, length - st["thread1"] - P.KNOB_T,
                                           align=(Align.CENTER, Align.CENTER, Align.MIN))
    thread = Pos(0, 0, length - st["thread1"]) * screw_thread(st["thread1"])
    screw = knob + shank + thread
    screw.label = "tux_vise_foot_screw"
    return screw


def foot_locations(desk: float) -> dict[str, Location]:
    """Where the foot's nut and screw go (the foot itself: `foot_in_place()`) for a desk `desk` mm thick (vise frame,
    base on the foot: the base's bottom at z = 0)."""
    f = foot_layout()
    tip = -(P.T_ARM + desk)
    length = foot_screw_stations()["length"]
    return {
        "foot_nut": Location((P.FOOT_L / 2, f["screw_y"], f["nut0"] + P.CLR_FIT)),
        "foot_screw": Location((P.FOOT_L / 2, f["screw_y"], tip - length)),
    }
