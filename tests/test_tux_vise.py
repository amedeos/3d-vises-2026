"""Tux Vise mechanics: travel, thread engagement, stops, collisions, the thread profile.

The screw's thread is never intersected with the nut's thread here: helical solids are
slow and fragile in booleans. The screw is checked as a stack of plain cylinders (its
outer envelope) against everything else, and the screw/nut fit is checked on the
profile. The real fit is what the thread coupon is for.
"""

from math import radians, tan

import pytest
from build123d import Align, Cone, Cylinder, Part, Pos

from common.grid import LINE_W, lines
from tux_vise import params as P
from tux_vise.kinematics import (
    engaged_turns,
    head_play,
    opening_after,
    table,
    thread_span,
    turns_to_close,
)
from tux_vise.model import (
    assembly,
    feet_top,
    fish_sketch,
    fork_x,
    jaw_x,
    make_base,
    make_jaw,
    make_tux,
    screw_stations,
    tip_x,
    tux_colours,
    use_location,
)
from tux_vise.thread import CREST_W, ROOT_R, ROOT_W

OPENINGS = [0.0, P.OPEN_MAX / 3, 2 * P.OPEN_MAX / 3, P.OPEN_MAX]


def _volume(a: Part, b: Part) -> float:
    common = a & b
    return sum(s.volume for s in common.solids()) if common is not None else 0.0


# --- thread ----------------------------------------------------------------------------

def test_thread_profile_prints_vertically():
    """45-degree flanks (ISO: 15) and whole-line flats; the teeth of screw and nut fit."""
    assert P.THREAD_FLANK >= 45.0
    assert P.THREAD_FLAT >= LINE_W - 1e-9
    assert CREST_W + (ROOT_W - CREST_W) == pytest.approx(ROOT_W)
    # tooth at the root + root gap = one pitch
    assert ROOT_W + P.THREAD_FLAT == pytest.approx(P.PITCH)
    assert ROOT_W - CREST_W == pytest.approx(2 * P.THREAD_DEPTH / tan(radians(P.THREAD_FLANK)))
    assert P.THREAD_D / 2 - ROOT_R == pytest.approx(P.THREAD_DEPTH)


def test_coupon_holds_the_vise_clearance():
    """The vise uses one of the coupon's clearances, so the coupon tells you if it fits."""
    assert P.CLR_THREAD in P.THREAD_GAUGE
    assert list(P.THREAD_GAUGE) == sorted(P.THREAD_GAUGE) and len(P.THREAD_GAUGE) == 4
    assert P.GAUGE_L >= P.MIN_TURNS * P.PITCH - 1e-9


# --- travel and engagement ------------------------------------------------------------------

def test_kinematics_table():
    rows = table()
    assert rows[0][1] == pytest.approx(P.OPEN_MAX) and rows[-1][1] == pytest.approx(0.0)
    assert rows[-1][0] == pytest.approx(P.OPEN_MAX / P.PITCH)
    assert all(b[1] < a[1] for a, b in zip(rows, rows[1:]))
    assert turns_to_close(P.OPEN_MAX) == 0
    assert opening_after(turns_to_close(10.0)) == pytest.approx(10.0)


@pytest.mark.parametrize("opening", OPENINGS)
def test_thread_engagement(opening):
    """At least MIN_TURNS of thread inside the nut at every jaw position, pushing or
    pulling (measured on the geometry of the screw and the base's nut pocket)."""
    assert engaged_turns(opening) >= P.MIN_TURNS


def test_only_the_thread_reaches_the_nut():
    """The plain shank never enters the nut, and the thread stays out of the jaw."""
    st = screw_stations()
    nut1 = P.X_POCKET1  # the far end of the pocket
    for opening in OPENINGS:
        shank_start = tip_x(opening) + st["thread1"]
        assert shank_start > nut1, opening
        thread_start = thread_span(opening)[0]
        assert thread_start > jaw_x(opening) + P.JAW_T, opening


def test_knob_clears_the_desk_and_the_end_block():
    """The fish turns within KNOB_R of the axis, below the axis height, and does not touch
    the end block when the jaw is closed."""
    bb = fish_sketch(P.KNOB_R).bounding_box()
    corners = [(x, y) for x in (bb.min.X, bb.max.X) for y in (bb.min.Y, bb.max.Y)]
    reach = max((x * x + y * y) ** 0.5 for x, y in corners)
    fish = fish_sketch(P.KNOB_R)
    from build123d import Circle

    assert (fish - Circle(P.KNOB_R + 1e-3)).area == pytest.approx(0, abs=1e-3)
    assert P.KNOB_R < P.Z_AXIS and reach > 0
    st = screw_stations()
    assert tip_x(0.0) + st["knob"] >= P.BASE_L + P.KNOB_GAP - 1e-9


# --- stops -----------------------------------------------------------------------------------

def test_jaw_stops_on_the_end_block_and_on_the_belly():
    """Fully open, the jaw's back meets the end block (a base feature). Closed, its face
    meets Tux's white belly and stays clear of the orange feet."""
    base, jaw = make_base(), make_jaw()
    open_jaw = use_location("jaw", P.OPEN_MAX) * jaw
    assert _volume(open_jaw, base) < 0.01
    assert _volume(Pos(0.3, 0, 0) * open_jaw, base) > 0.1
    closed = use_location("jaw", 0.0) * jaw
    tux = use_location("tux") * make_tux()
    assert _volume(closed, tux) < 0.01
    assert _volume(Pos(-0.3, 0, 0) * closed, tux) > 0.1
    white = use_location("tux") * tux_colours()[1][0]
    orange = use_location("tux") * tux_colours()[2][0]
    assert _volume(Pos(-0.3, 0, 0) * closed, white) > 0.1  # the belly is the jaw face
    assert _volume(Pos(-0.3, 0, 0) * closed, orange) < 0.01  # the feet sit in the recess


@pytest.mark.parametrize("opening", OPENINGS)
def test_jaw_stays_on_the_rail(opening):
    """The rail runs under the whole jaw slot over the full travel (the jaw can only leave
    the rail at the Tux end, and Tux blocks it)."""
    assert P.X_RAIL0 <= jaw_x(opening) + 1.0
    assert jaw_x(opening) + P.JAW_T <= P.X_END + 1e-9


def test_feet_recess_covers_the_feet():
    assert P.JAW_Z0 + 0.0 < feet_top() < P.JAW_Z0 + 20
    assert P.FEET_RECESS >= P.T_ORANGE + 0.5


# --- collisions -----------------------------------------------------------------------------

def screw_envelope(opening: float, play: float = 0.0) -> Part:
    """The screw as plain cylinders along x (head, neck, thread major diameter, shank,
    knob disc), in place."""
    st, tip = screw_stations(), tip_x(opening) + play

    def cyl(r, s0, s1, r1=None):
        shape = (Cylinder(r, s1 - s0, rotation=(0, 90, 0),
                          align=(Align.CENTER, Align.CENTER, Align.MIN)) if r1 is None else
                 Cone(r, r1, s1 - s0, rotation=(0, 90, 0),
                      align=(Align.CENTER, Align.CENTER, Align.MIN)))
        return Pos(tip + s0, 0, P.Z_AXIS) * shape

    cone_h = (P.HEAD_D - P.NECK_D) / 2
    return (cyl(P.HEAD_D / 2, 0, st["head"] - cone_h)
            + cyl(P.HEAD_D / 2, st["head"] - cone_h, st["head"], P.NECK_D / 2)
            + cyl(P.NECK_D / 2, st["head"], st["thread0"])
            + cyl(P.THREAD_D / 2, st["thread0"], st["thread1"])
            + cyl(P.THREAD_D / 2 + 0.1, st["thread1"], st["knob"])
            + cyl(P.KNOB_R, st["knob"], st["length"]))


@pytest.mark.parametrize("opening", OPENINGS)
def test_nothing_collides_over_the_travel(opening):
    """Tux, base, jaw, fork and nut never overlap (Tux's soles stand on the base: up to
    0.05 mm3 of contact). The screw's envelope touches none of them except the nut, whose
    thread it enters. Pulling, the head moves out by head_play() and its cone meets the
    fork: that contact is the design, so the fork is left out there."""
    parts = assembly(opening)
    names = ["tux", "base", "jaw", "fork", "nut"]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert _volume(parts[a], parts[b]) < 0.05, (opening, a, b)
    for play, others in ((0.0, ["tux", "base", "jaw", "fork"]),
                         (head_play(), ["tux", "base", "jaw"])):
        screw = screw_envelope(opening, play)
        for name in others:
            assert _volume(screw, parts[name]) < 0.01, (opening, play, name)


def test_screw_and_nut_fit_on_the_profile():
    """Radial clearance between the screw's crest and the nut's root, and between the
    nut's crest and the screw's core, both equal CLR_THREAD."""
    nut_root = P.THREAD_D / 2 + P.CLR_THREAD
    nut_crest = ROOT_R + P.CLR_THREAD
    assert nut_root - P.THREAD_D / 2 == pytest.approx(P.CLR_THREAD)
    assert nut_crest - ROOT_R == pytest.approx(P.CLR_THREAD)
    assert P.CLR_THREAD >= 0.1


# --- captive parts ------------------------------------------------------------------------------

def test_head_is_held_by_the_fork():
    """The head is wider than the fork's opening and narrower than its chamber; the fork
    sits behind the head with the designed play."""
    assert P.HEAD_D > P.NECK_D + 2 * P.CLR_FORK + 2 * lines(2)
    assert P.HEAD_D / 2 + 0.4 < P.Z_AXIS - P.JAW_Z0  # the chamber fits in the jaw
    assert fork_x() == pytest.approx(P.FACE_T + P.HEAD_L + P.HEAD_PLAY)
    assert head_play() > 0


def test_nut_is_captive():
    """In the pocket, the nut cannot turn (square), cannot move along the screw more than
    its clearance (walls on both sides), and cannot lift out while the screw goes
    through it. Only gravity holds it before the screw is in."""
    assert P.X_POCKET1 - P.X_POCKET0 - P.NUT_L == pytest.approx(2 * P.CLR_FIT)
    assert P.NUT_W / 2 > P.THREAD_D / 2 + P.CLR_THREAD + 3 * LINE_W


def test_vise_length():
    assert 80.0 <= P.BASE_L <= 90.0


# --- desk foot ------------------------------------------------------------------------------

DESKS = [P.DESK_MIN, (P.DESK_MIN + P.DESK_MAX) / 2, P.DESK_MAX]


@pytest.mark.parametrize("desk", DESKS)
def test_foot_screw_engagement(desk):
    """The foot screw keeps MIN_TURNS in its nut for every desk in the range, and its plain
    shank never enters the nut."""
    from tux_vise.model import foot_layout, foot_screw_stations

    f, st = foot_layout(), foot_screw_stations()
    tip = -(P.T_ARM + desk)
    nut0, nut1 = f["nut0"] + P.CLR_FIT, f["nut0"] + P.CLR_FIT + P.NUT_L
    thread0, thread1 = tip - st["thread1"], tip
    engaged = max(0.0, min(nut1, thread1) - max(nut0, thread0)) / P.PITCH
    assert engaged >= P.MIN_TURNS
    assert tip - st["thread1"] < nut0  # the shank starts below the nut
    assert tip - st["knob"] <= f["bottom0"] - 0.5  # the fish stays under the arm


def test_base_is_held_by_the_foot():
    """The base slides into the channel; the lips cover its bevels, so it cannot lift out,
    and nothing overlaps."""
    from tux_vise.model import (_channel_half, foot_in_place, foot_locations,
                                foot_screw_stations, make_foot_screw, make_nut)

    assert _channel_half(P.LIP_TOP) < P.BASE_W / 2  # the lips reach over the bevel
    base, foot = make_base(), foot_in_place()
    assert _volume(base, foot) < 0.05
    assert _volume(Pos(0, 0, 0.5) * base, foot) > 0.1  # lifting it hits the lips
    for desk in DESKS:
        loc = foot_locations(desk)
        nut = loc["foot_nut"] * make_nut()
        screw = loc["foot_screw"] * make_foot_screw()
        assert _volume(nut, foot) < 0.05
        length = foot_screw_stations()["length"]
        envelope = loc["foot_screw"] * (Pos(0, 0, P.KNOB_T) * Cylinder(
            P.THREAD_D / 2 + 0.1, length - P.KNOB_T, align=(Align.CENTER, Align.CENTER, Align.MIN)))
        assert _volume(envelope, foot) < 0.01, desk
        assert screw.bounding_box().max.Z == pytest.approx(-(P.T_ARM + desk))
