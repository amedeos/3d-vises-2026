"""Tux Clip mechanics: opening, flexure strain, preload, clearances over the swing."""

from math import pi

import pytest

from common.grid import LINE_W, layers, lines
from common.tux import tux_profile
from tux_clip import params as P
from tux_clip.model import (
    body_profile,
    card_hold_margin,
    coupon_mechanism,
    flipper_placed,
    leaf_local,
    make_clip,
    mechanism,
    moving_local,
    _both_sides,
)

SIZES = list(P.SIZES)


@pytest.mark.parametrize("size", SIZES)
def test_jaw_opens_to_the_target(size):
    m = mechanism(size)
    assert m.opening_at(m.theta_stop) == pytest.approx(P.SIZES[size]["opening"], rel=0.10)


@pytest.mark.parametrize("size", SIZES)
def test_flexure_strain_stays_safe(size):
    """At the stop, the leaf bends no more than PETG_SAFE_STRAIN.

    Assumption (params.py): pure bending, eps = t * theta / (2 L), and an allowed strain of
    half the linear-elastic yield strain of Prusament PETG (47 MPa / 1.5 GPa / 2 = 1.57 %).
    """
    m = mechanism(size)
    assert m.strain(m.theta_stop) <= P.PETG_SAFE_STRAIN + 1e-9
    assert P.PETG_SAFE_STRAIN == pytest.approx(0.0157, abs=1e-4)


@pytest.mark.parametrize("size", SIZES)
def test_jaws_close_with_a_positive_preload(size):
    """At rest the comb teeth reach PRELOAD past each other: even a thin stiff card must
    bend the flexure, so the clamping force is positive."""
    m = mechanism(size)
    assert P.PRELOAD > 0
    assert m.opening_at(0.0) == pytest.approx(-P.PRELOAD, abs=1e-9)
    # measured on the drawn teeth, not only on the parameters
    from tux_clip.model import body_teeth_local, flipper_local

    body_tip = body_teeth_local(m).bounding_box().max.Y
    flipper_tip = min(f.bounding_box().min.Y for f in flipper_local(m).faces())
    assert body_tip - flipper_tip == pytest.approx(P.PRELOAD, abs=1e-3)
    assert m.force(0.0) > 0
    assert m.force(0.3) > m.force(0.0)  # a photo gets more force than nothing


@pytest.mark.parametrize("size", SIZES)
def test_flipper_is_free_at_rest(size):
    """At least one line of air between the flipper and the body (it is one print)."""
    m = mechanism(size)
    body, flipper = body_profile(m), flipper_placed(m, 0.0)
    assert flipper.distance_to(body) >= LINE_W - 1e-3


def _overlap(m, theta: float) -> float:
    """Area where the swung leaf and flipper overlap the body (or each other), minus the
    two designed joints of the leaf."""
    body = body_profile(m)
    moving = _both_sides(m, moving_local(m, theta))
    joints = 2 * 2 * 0.05 * m.t  # each leaf overlaps 0.05 mm into the body and the flipper
    leaf = _both_sides(m, leaf_local(m, theta))
    flipper_area = moving.area - leaf.area + joints / 2
    return body.area + leaf.area + flipper_area - (body + moving).area - joints


@pytest.mark.parametrize("size", SIZES)
def test_nothing_collides_over_the_swing(size):
    m = mechanism(size)
    for k in range(8):
        theta = m.theta_stop * k / 8
        assert _overlap(m, theta) < 0.05, f"{size}: overlap at {theta:.3f} rad"
        if k:
            assert flipper_placed(m, theta).distance_to(body_profile(m)) > 0.0


@pytest.mark.parametrize("size", SIZES)
def test_shoulder_stop_limits_the_swing(size):
    """The pad meets the shoulder exactly at theta_stop, so a hard squeeze cannot bend the
    flexure further."""
    m = mechanism(size)
    assert flipper_placed(m, 0.97 * m.theta_stop).distance_to(body_profile(m)) > 0.02
    assert flipper_placed(m, 1.03 * m.theta_stop).intersect(body_profile(m)) is not None


@pytest.mark.parametrize("size", SIZES)
def test_clip_is_one_piece(size):
    assert len(make_clip(size).solids()) == 1


@pytest.mark.parametrize("size", SIZES)
def test_print_time_budget(size):
    """At most about 30 min per clip on an MK4 (0.20mm STRUCTURAL, Prusament PETG).

    PrusaSlicer 2.9.6 estimates, model volume -> time: 6.9 cm3 -> 15 min 54 s,
    11.9 cm3 -> 23 min 29 s, 15.9 cm3 -> 29 min 19 s, 17.2 cm3 -> 30 min 56 s,
    18.1 cm3 -> 32 min 8 s. About 6.1 min plus 1.46 min per cm3 (a little pessimistic
    for the small sizes), so 30 min allows about 16.4 cm3."""
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
        assert m.strain(m.theta_stop) <= P.PETG_SAFE_STRAIN + 1e-9


def test_desk_holds_a_photo_upright():
    # a 10 x 15 cm photo (about 3 g, 0.3 mm), standing in the slot, leaning by 5 degrees
    assert card_hold_margin(3.0, 150.0, 0.3) > 1.0
    # a business card (about 1 g, 0.4 mm, 55 mm high)
    assert card_hold_margin(1.0, 55.0, 0.4) > 1.0


def test_desk_cannot_hold_a_phone():
    """Documented limit (README): a 200 g phone would tip over; it needs a backrest."""
    assert card_hold_margin(200.0, 150.0, 8.0) < 1.0
