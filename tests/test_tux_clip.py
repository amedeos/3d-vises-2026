"""Tux Clip mechanics: opening, flexure strain, preload, clearances over the swing."""

import pytest
from build123d import Pos, Rectangle

from common.grid import LINE_W, layers, lines
from common.tux import tux_profile
from tux_clip import params as P
from tux_clip.model import (
    LOADS,
    _both_sides,
    body_profile,
    body_teeth_local,
    card_hold_margin,
    coupon_mechanism,
    flipper_local,
    flipper_placed,
    leaf_local,
    leaf_point,
    make_clip,
    mechanism,
    pose,
    stop_contact,
    stop_face_top,
    teeth_positions,
)

SIZES = list(P.SIZES)


@pytest.mark.parametrize("size", SIZES)
def test_jaw_opens_to_the_target(size):
    m = mechanism(size)
    assert m.opening_at(m.theta_stop) == pytest.approx(P.SIZES[size]["opening"], rel=0.10)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("load", LOADS)
def test_flexure_strain_stays_safe(size, load):
    """At either stop, the most bent point of the leaf stays within PETG_SAFE_STRAIN.

    Assumption (params.py): the curvature grows linearly away from the load line, and the
    allowed strain is half the elongation at yield of Prusament PETG (5.1 % / 2 = 2.55 %).
    """
    m = mechanism(size)
    assert m.strain(m.stop(load), load) <= P.PETG_SAFE_STRAIN + 1e-9
    assert P.PETG_SAFE_STRAIN == pytest.approx(0.0255, abs=1e-4)


@pytest.mark.parametrize("load", LOADS)
def test_leaf_shape(load):
    """The bent leaf keeps its length, turns its end by theta, and its curvature is zero on
    the load line and largest at the far end (the strain formula relies on that)."""
    m = mechanism("M")
    theta, a_load = m.stop(load), m.load_line(load)
    pts = [leaf_point(m.L, theta, a_load, -m.L / 2 + m.L * k / 400) for k in range(401)]
    length = sum(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
                 for (x0, y0), (x1, y1) in zip(pts, pts[1:]))
    assert length == pytest.approx(m.L, rel=1e-4)
    (xa, ya), (xb, yb) = pts[-2], pts[-1]
    from math import atan2

    assert atan2(yb - ya, xb - xa) == pytest.approx(theta, abs=2e-3)
    # a circular arc of the same swing would give a smaller peak strain
    assert m.strain(theta, load) > m.t * theta / (2 * m.L)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("flex_lines", [2, 3, 4])
def test_every_leaf_keeps_a_comb(size, flex_lines):
    """Thicker leaves open less but keep a real comb: at least MIN_TEETH teeth, flipper
    teeth included, so the preload is still there (README: change FLEX_LINES)."""
    m = mechanism(size, flex_lines)
    body, flipper = teeth_positions(m)
    assert len(body) + len(flipper) >= P.MIN_TEETH and flipper
    assert m.opening > 1.0
    assert m.opening_at(0.0) == pytest.approx(-P.PRELOAD, abs=1e-9)


@pytest.mark.parametrize("size", SIZES)
def test_jaws_close_with_a_positive_preload(size):
    """At rest the comb teeth reach PRELOAD past each other: even a thin stiff card must
    bend the flexure, so the clamping force is positive."""
    m = mechanism(size)
    assert P.PRELOAD > 0
    assert m.opening_at(0.0) == pytest.approx(-P.PRELOAD, abs=1e-9)
    # measured on the drawn teeth, not only on the parameters: the flipper below its
    # bridge is only the jaw and its teeth
    body_tip = body_teeth_local(m).bounding_box().max.Y
    jaw_zone = Pos(m.a_tip, 0) * Rectangle(2 * (m.a_tip - m.L / 2 - P.BRIDGE) - 0.02, 40)
    flipper_tip = (flipper_local(m) & jaw_zone).bounding_box().min.Y
    assert body_tip - flipper_tip == pytest.approx(P.PRELOAD, abs=1e-3)
    assert m.force(0.0) > 0
    assert m.force(0.3) > m.force(0.0)  # a photo gets more force than nothing


@pytest.mark.parametrize("size", SIZES)
def test_flipper_is_free_at_rest(size):
    """At least one line of air between the flipper and the body (it is one print)."""
    m = mechanism(size)
    body, flipper = body_profile(m), flipper_placed(m, 0.0)
    assert flipper.distance_to(body) >= LINE_W - 1e-3


def _area(sketch) -> float:
    return sketch.area if sketch is not None else 0.0


def _overlap(m, theta: float, load: str) -> float:
    """Area where the body, the swung leaf and the swung flipper overlap each other, minus
    the designed joints (each leaf reaches 0.05 mm into the body and into the flipper)."""
    body = body_profile(m)
    leaf = _both_sides(m, leaf_local(m, theta, load))
    flipper = _both_sides(m, pose(m, theta, load) * flipper_local(m))
    joints = 4 * 0.05 * m.t
    return _area(body & leaf) + _area(body & flipper) + _area(leaf & flipper) - joints


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("load", LOADS)
def test_nothing_collides_over_the_swing(size, load):
    """From rest to the stop, under either load: the leaf, the flipper and the body never
    overlap, and the flipper only touches the body at the stop."""
    m = mechanism(size)
    stop = m.stop(load)
    # sweep_local cuts the body with poses at stop * k / 16: test the poses in between
    thetas = [0.0] + [stop * j / 32 for j in range(1, 32, 4)] + [stop * 31 / 32, stop]
    for theta in thetas:
        assert abs(_overlap(m, theta, load)) < 0.05, f"{size}: overlap at {theta:.3f} rad"
        if 0 < theta < stop:
            assert flipper_placed(m, theta, load).distance_to(body_profile(m)) > 0.0


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("load", LOADS)
def test_shoulder_stop_limits_the_swing(size, load):
    """The pad meets the shoulder exactly at the stop, so a hard squeeze (or a thick object)
    cannot bend the flexure further. It lands on the flat stop face, STOP_MARGIN from its
    upper end and clear of the leaf below."""
    m = mechanism(size)
    stop = m.stop(load)
    assert flipper_placed(m, 0.97 * stop, load).distance_to(body_profile(m)) > 0.02
    assert flipper_placed(m, 1.03 * stop, load).intersect(body_profile(m)) is not None
    contact = stop_contact(m, load)
    assert stop_face_top(m) + P.STOP_MARGIN - 1e-9 <= contact < -m.L / 2 - P.STOP_MARGIN


@pytest.mark.parametrize("size", SIZES)
def test_clip_is_one_piece(size):
    assert len(make_clip(size).solids()) == 1


@pytest.mark.parametrize("size", SIZES)
def test_print_time_budget(size):
    """At most about 30 min per clip on an MK4 (0.20mm STRUCTURAL, Prusament PETG).

    PrusaSlicer 2.9.6 estimates, model volume -> time: 6.9 cm3 -> 15 min 54 s,
    11.9 cm3 -> 23 min 29 s, 15.9 cm3 -> 29 min 19 s, 16.2 cm3 -> 29 min 26 s,
    17.2 cm3 -> 30 min 56 s, 18.1 cm3 -> 32 min 8 s. About 6.1 min plus 1.46 min per cm3
    (a little pessimistic for the small sizes), so 30 min allows about 16.4 cm3."""
    minutes = 6.1 + 1.46 * make_clip(size).volume / 1000
    assert minutes <= 30.0


def test_tux_still_reads_in_one_colour():
    """The reliefs are at least 2 layers high, and the pupils at least 2 lines wide even
    on the smallest Tux, so a one-colour print still shows the face, belly and feet."""
    assert P.T_WHITE >= layers(2) and P.T_ORANGE >= layers(2)
    small = tux_profile(min(s["height"] for s in P.SIZES.values()))
    pupil = small.pupils.faces()[0].bounding_box()
    assert min(pupil.size.X, pupil.size.Y) >= lines(2)


def test_coupon_levers_trade_opening_for_stiffness():
    levers = [coupon_mechanism(n) for n in P.COUPON_LINES]
    assert [round(m.t, 3) for m in levers] == [round(lines(n), 3) for n in P.COUPON_LINES]
    for a, b in zip(levers, levers[1:]):
        assert b.stiffness > a.stiffness and b.opening < a.opening
    for m in levers:
        for load in LOADS:
            assert m.strain(m.stop(load), load) <= P.PETG_SAFE_STRAIN + 1e-9


def test_force_respects_the_stop():
    """An object thicker than the jaw can take is refused, not squeezed past the stop."""
    m = mechanism("M")
    assert m.theta_for(m.max_gap) == pytest.approx(m.theta_stop_jaw, abs=1e-6)
    with pytest.raises(ValueError):
        m.force(m.max_gap + 0.5)


def test_desk_holds_a_photo_upright():
    # a 10 x 15 cm photo (about 3 g, 0.3 mm), standing in the slot, leaning by 5 degrees
    assert card_hold_margin(3.0, 150.0, 0.3) > 1.0
    # a business card (about 1 g, 0.4 mm, 55 mm high)
    assert card_hold_margin(1.0, 55.0, 0.4) > 1.0


def test_desk_card_stands_in_the_jaw():
    """The card used in the listing really fits: it stands on the desk (z = 0), one end
    in the jaw over most of its length, the rest along the groove in the floe, and it
    touches nothing with the right flipper opened by the card."""
    from tux_clip.model import desk_card, desk_colours

    card, theta = desk_card()
    black = desk_colours(theta, "jaw", right_only=True)[0][0]
    common = black & card
    assert (sum(s.volume for s in common.solids()) if common else 0.0) < 0.01
    assert card.bounding_box().min.Z == pytest.approx(0.0, abs=1e-6)
    m = mechanism(P.DESK_SIZE)
    assert m.a_tip - (m.L / 2 + P.BRIDGE) > 8.0  # a jaw of 8 mm or more grips the card
    with pytest.raises(ValueError):  # a card thicker than the jaw opens is refused
        desk_card(thickness=7.0)
    assert m.opening_at(theta, "jaw") < m.opening  # a squeeze opens the jaw that far


def test_desk_cannot_hold_a_phone():
    """Documented limit (README): a 200 g phone would tip over; it needs a backrest."""
    m = mechanism(P.DESK_SIZE)
    assert 8.0 <= m.max_gap  # it fits in the jaw...
    assert card_hold_margin(200.0, 150.0, 8.0) < 1.0  # ...but the clip cannot hold it up
