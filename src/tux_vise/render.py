"""Tux Vise previews for the listing: PNG images and a GIF in out/render/tux_vise.

    uv run python -m tux_vise.render          # images
    uv run python -m tux_vise.render --gif    # images and the turning-knob animation
"""

import sys
from math import floor
from pathlib import Path

from build123d import Part, Pos, Rot

from common.export import row
from common.render import gif, render
from common.shapes import box_between

from . import params as P
from .export import COLOUR, printable_parts
from .kinematics import opening_after, turns_to_close
from .model import (
    VISE_PARTS,
    foot_in_place,
    foot_layout,
    foot_locations,
    jaw_x,
    make_foot_screw,
    make_nut,
    tux_colours,
    use_location,
)

HERO = {"elev": 24, "azim": 38}  # from the knob side, Tux's face above the jaw
KNOB_END = {"elev": 10, "azim": 4}
SIDE = {"elev": 14, "azim": 100}


def upright(opening: float) -> float:
    """The opening nearest to `opening`, within the travel, at a whole number of turns from
    fully open: there the renders show the gnu knob upright, horns up."""
    whole = min(max(round(turns_to_close(opening)), 0), floor(turns_to_close(0.0)))
    return opening_after(whole)


def vise_items(opening: float, with_board: bool = False):
    """The assembled vise as (part, colour), the gnu turned to match the opening."""
    # right-handed thread: turning clockwise seen from the knob (a positive turn about the
    # screw's print axis) drives it towards Tux
    angle = 360.0 * turns_to_close(opening)
    items = [(use_location("tux") * part, colour) for part, colour in tux_colours()]
    for name in ("base", "jaw", "fork", "nut"):
        items.append((use_location(name, opening) * VISE_PARTS[name](), COLOUR[f"tux_vise_{name}"]))
    screw = use_location("screw", opening) * (Rot(0, 0, angle) * VISE_PARTS["screw"]())
    items.append((screw, COLOUR["tux_vise_screw"]))
    if with_board:
        items.append((board(opening), "green"))
    return items


def board(opening: float) -> Part:
    """A small circuit board held between the belly and the jaw."""
    return box_between(P.X_BELLY, jaw_x(opening), -16, 16, 22, 44)


def foot_items(desk: float = 25.0):
    """The vise on its desk foot, clamped to the edge of a desk `desk` mm thick."""
    loc = foot_locations(desk)
    f = foot_layout()
    items = vise_items(upright(12.0)) + [
        (foot_in_place(), COLOUR["tux_vise_foot"]),
        (loc["foot_nut"] * make_nut(), COLOUR["tux_vise_foot_nut"]),
        (loc["foot_screw"] * make_foot_screw(), COLOUR["tux_vise_foot_screw"]),
        (box_between(-30, 120, f["spine1"], 90, -(P.T_ARM + desk), -P.T_ARM), "card"),
    ]
    return items


def parts_on_bed() -> list[tuple[Part, str]]:
    """Every printable part in its print pose, side by side (Tux in his colours)."""
    pp = printable_parts()
    names = [n for n in pp if not n.startswith("coupon")]
    placed = row([pp[n] for n in names], gap=10.0)
    items = []
    for name, part in zip(names, placed):
        if name == "tux_vise_tux":
            shift = part.bounding_box().min - pp[name].bounding_box().min
            items += [(Pos(shift) * p, c) for p, c in tux_colours()]
        else:
            items.append((part, COLOUR[name]))
    return items


def listing(out: Path, with_gifs: bool = False) -> None:
    """Every image for the Printables page."""
    out.mkdir(parents=True, exist_ok=True)
    # whole turns from fully open keep the gnu upright
    render(vise_items(upright(0.0), with_board=True), out / "vise_hero.png", **HERO, zoom=1.3,
           size=(1000, 800))
    render(vise_items(upright(P.OPEN_MAX * 0.6)), out / "vise_open.png", **HERO, zoom=1.3,
           size=(1000, 800))
    render(vise_items(upright(12.0)), out / "vise_knob_end.png", **KNOB_END, zoom=1.35,
           size=(800, 800))
    render(vise_items(upright(12.0)), out / "vise_side.png", **SIDE, zoom=1.3, size=(1000, 700))
    render(parts_on_bed(), out / "vise_parts.png", elev=48, azim=-70, zoom=1.25,
           size=(1200, 700))
    render(foot_items(), out / "vise_on_desk.png", elev=18, azim=-120, zoom=1.2,
           size=(1000, 800))
    pp = printable_parts()
    coupon = row([pp["coupon_thread_gauge"], pp["coupon_thread_stub"]], gap=10.0)
    render([(p, "orange") for p in coupon], out / "coupon_thread.png", elev=50, azim=-70,
           zoom=1.2, size=(900, 600))
    if with_gifs:
        steps = 18
        openings = [P.OPEN_MAX * (1 - k / steps) for k in range(steps + 1)]
        gif((vise_items(o) for o in openings), out / "vise_turn.gif", duration=90, **HERO,
            zoom=1.3, size=(560, 450))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target = Path(args[0] if args else "out/render/tux_vise")
    listing(target, with_gifs="--gif" in sys.argv)
    print("wrote", target)
