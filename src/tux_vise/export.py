"""Export Tux Vise: STL files (out/stl/tux_vise) and 3MF plates (out/3mf/tux_vise).

Only Tux changes colour: white at layer_top(Z_WHITE) and yellow at layer_top(Z_ORANGE),
already set in his 3MF. Every other plate prints in one colour.

Exits with status 1 if any part fails a check.
"""

import sys
from pathlib import Path

from build123d import Part

from common.export import Change, Plates, centred, export_model, row

from . import params as P
from .model import (
    make_base,
    make_foot,
    make_foot_screw,
    make_fork,
    make_gauge,
    make_jaw,
    make_nut,
    make_screw,
    make_stub,
    make_tux,
    gauge_holes,
    screw_stations,
    foot_screw_stations,
    tux_colours,
)

MODEL = "tux_vise"
M600_WHITE, M600_ORANGE = P.M600_WHITE, P.M600_ORANGE  # defined in params.py
CHANGES: list[Change] = [(M600_WHITE, "white"), (M600_ORANGE, "yellow")]

# Declared widths, checked by the tests: thin features must be whole lines (2 or more),
# gaps at least one line. The vise has no thin walls; its narrowest holes are these.
THIN_FEATURES: dict[str, float] = {}
# the gnu's eyes and nostrils are at least lines(4) across (gnu.holes)
GAPS = {"gnu eyes and nostrils": P.lines(4),
        "fork opening": P.NECK_D + 2 * P.CLR_FORK,
        "thread root gap": P.THREAD_FLAT}

# Suggested colours. Tux has three (M600); every other plate prints in one colour, so the
# parts that share a plate share a colour.
COLOUR = {"tux_vise_tux": "black", "tux_vise_base": "blue", "tux_vise_jaw": "black",
          "tux_vise_fork": "black", "tux_vise_nut": "black", "tux_vise_screw": "yellow",
          "tux_vise_foot": "blue", "tux_vise_foot_screw": "blue", "tux_vise_foot_nut": "blue",
          "coupon_thread_gauge": "yellow", "coupon_thread_stub": "yellow"}


def _thread_zone(r: float, z0: float, z1: float, x: float = 0.0, y: float = 0.0):
    return (x, y, r, z0, z1)


def thread_zones() -> dict[str, list[tuple[float, float, float, float, float]]]:
    """Where each part has a thread, as (x, y, radius, z0, z1) in its print pose.

    The width tests skip these discs: a horizontal slice through a helix cuts each tooth
    into a crescent that tapers to nothing, whatever the tooth is like. The tooth itself is
    2.55 mm wide at its root (almost 6 lines), and the slicer builds it along the helix.
    """
    st = screw_stations()
    length = st["length"]
    nut_r = P.THREAD_D / 2 + P.CLR_THREAD + 0.01
    gauge = [_thread_zone(P.THREAD_D / 2 + clr + 0.01, -1, P.GAUGE_L + 1, x, y)
             for clr, (x, y) in zip(P.THREAD_GAUGE, gauge_holes())]
    return {
        "tux_vise_nut": [_thread_zone(nut_r, -1, P.NUT_L + 1)],
        "tux_vise_foot_nut": [_thread_zone(nut_r, -1, P.NUT_L + 1)],
        "tux_vise_screw": [_thread_zone(P.THREAD_D / 2 + 0.01, length - st["thread1"],
                                        length - st["thread0"] + 1)],
        "tux_vise_foot_screw": [_thread_zone(P.THREAD_D / 2 + 0.01,
                                             foot_screw_stations()["length"]
                                             - foot_screw_stations()["thread1"], 1e3)],
        "coupon_thread_gauge": gauge,
        "coupon_thread_stub": [_thread_zone(P.THREAD_D / 2 + 0.01, P.KNOB_T + P.LAYER,
                                            P.KNOB_T + P.LAYER + P.GAUGE_STUB + 1)],
    }


def printable_parts() -> dict[str, Part]:
    """name -> part on the bed (z = 0), in its print pose."""
    return {
        "tux_vise_tux": make_tux(),
        "tux_vise_base": make_base(),
        "tux_vise_jaw": make_jaw(),
        "tux_vise_fork": make_fork(),
        "tux_vise_nut": make_nut(),
        "tux_vise_screw": make_screw(),
        "tux_vise_foot": make_foot(),
        "tux_vise_foot_screw": make_foot_screw(),
        "tux_vise_foot_nut": make_nut(),  # the same nut, for the foot
        "coupon_thread_gauge": make_gauge(),
        "coupon_thread_stub": make_stub(),
    }


def colour_parts() -> dict[str, list[tuple[Part, str]]]:
    """name -> the part split into its colours, from the bottom up."""
    parts = {name: [(part, COLOUR[name])] for name, part in printable_parts().items()
             if name != "tux_vise_tux"}
    parts["tux_vise_tux"] = list(tux_colours())
    return parts


# the colour changes each plate must have; slicer.py checks the real G-code against this
PLANNED_M600: dict[str, list[Change]] = {"tux_vise_tux": CHANGES}


def plates() -> Plates:
    """plate name -> ([(object name, part on the bed, start colour)], colour changes)."""
    pp = printable_parts()

    def plate(names: list[str], colour: str | None = None):
        parts = [pp[n] for n in names]
        placed = [centred(parts[0])] if len(parts) == 1 else row(parts)
        return [(n, p, colour or COLOUR[n]) for n, p in zip(names, placed)]

    one_colour = ["tux_vise_base", "tux_vise_jaw", "tux_vise_fork", "tux_vise_nut",
                  "tux_vise_screw"]

    return {
        "tux_vise_tux": (plate(["tux_vise_tux"]), PLANNED_M600["tux_vise_tux"]),
        "tux_vise_base": (plate(["tux_vise_base"]), []),
        "tux_vise_jaw": (plate(["tux_vise_jaw", "tux_vise_fork", "tux_vise_nut"]), []),
        "tux_vise_screw": (plate(["tux_vise_screw"]), []),
        # everything but Tux on one plate, in one colour: faster than the three plates
        "tux_vise_parts_one_colour": (plate(one_colour, "black"), []),
        "tux_vise_foot": (plate(["tux_vise_foot", "tux_vise_foot_screw", "tux_vise_foot_nut"],
                                "blue"), []),
        "coupon_thread": (plate(["coupon_thread_gauge", "coupon_thread_stub"]), []),
    }


def export_all(out: Path) -> dict[str, list[str]]:
    report = export_model(out, MODEL, printable_parts(), plates())
    print(f"\nColour changes (M600, 0.2 mm layers): Tux only, white at Z = {M600_WHITE:.2f} mm, "
          f"yellow at Z = {M600_ORANGE:.2f} mm. The 3MF plate already has them.")
    return report


if __name__ == "__main__":
    result = export_all(Path(sys.argv[1] if len(sys.argv) > 1 else "out"))
    sys.exit(1 if any(result.values()) else 0)
