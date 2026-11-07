"""Tux Clip previews for the listing: PNG images and GIFs in out/render/tux_clip.

    uv run python -m tux_clip.render          # images
    uv run python -m tux_clip.render --gif    # images and the open/close animation
"""

import sys
from math import pi, sin
from pathlib import Path

from build123d import Pos, extrude

from common.render import gif, render

from . import params as P
from .model import clip_colours, coupon_profile, desk_card, desk_colours, make_coupon, mechanism

FRONT = {"elev": 90, "azim": -90}  # straight down on the face (the clip lies on its back)
HERO = {"elev": 58, "azim": -72}
SIDE = {"elev": 25, "azim": -60}


def clip_items(size: str, theta: float = 0.0, shift: tuple[float, float] = (0, 0)):
    return [(Pos(*shift, 0) * part, colour) for part, colour in clip_colours(size, theta)]


def desk_items(with_card: bool = True):
    """The desk version holding a business card in its right jaw (the left flipper rests)."""
    if not with_card:
        return list(desk_colours())
    card, theta = desk_card()
    return list(desk_colours(theta, "jaw", right_only=True)) + [(card, "card")]


def listing(out: Path, with_gifs: bool = False) -> None:
    """Every image for the Printables page."""
    out.mkdir(parents=True, exist_ok=True)
    m = mechanism("M")
    render(clip_items("M"), out / "clip_M_hero.png", **HERO, zoom=1.25, size=(900, 900))
    render(clip_items("M"), out / "clip_M_front.png", **FRONT, zoom=1.15, size=(800, 800))
    render(clip_items("M", m.theta_stop), out / "clip_M_open.png", **FRONT, zoom=1.15,
           size=(800, 800))
    # the three sizes side by side, feet on one line
    x, items = 0.0, []
    for size in P.SIZES:
        w = clip_colours(size)[0][0].bounding_box().size.X
        x += w / 2
        items += clip_items(size, shift=(x, 0))
        x += w / 2 + 8
    render(items, out / "clip_sizes.png", **HERO, zoom=1.2, size=(1200, 700))
    # from Tux's side, so the card stands behind him
    render(desk_items(), out / "clip_desk.png", elev=30, azim=200, zoom=1.2, size=(900, 800))
    # close-up of the comb jaw at rest and open
    jaw = m.plane.location * Pos((m.L / 2 + m.a_tip) / 2, 0, 0)
    target = (jaw.position.X, jaw.position.Y, P.T_BODY)
    for name, theta in [("rest", 0.0), ("open", m.theta_stop * 0.35)]:
        render(clip_items("M", theta), out / f"clip_jaw_{name}.png", elev=60, azim=-60,
               zoom=4.0, target=target, size=(700, 600))
    render([(make_coupon(), "yellow")], out / "coupon_flexure.png", elev=55, azim=-80,
           zoom=1.2, size=(900, 600))
    if with_gifs:
        frames = [m.theta_stop * sin(k / 14 * pi / 2) ** 2 for k in range(15)]
        gif((clip_items("M", t) for t in frames), out / "clip_M_squeeze.gif", duration=70,
            **FRONT, zoom=1.15, size=(520, 520))
        coupon = [(extrude(coupon_profile(k / 10), P.T_BODY, dir=(0, 0, 1)), "yellow")
                  for k in range(11)]
        gif(([c] for c in coupon), out / "coupon_flexure.gif", duration=90, **FRONT, zoom=1.2,
            size=(560, 420))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target = Path(args[0] if args else "out/render/tux_clip")
    listing(target, with_gifs="--gif" in sys.argv)
    print("wrote", target)
