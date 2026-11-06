"""Export Tux Clip: STL files (out/stl/tux_clip) and 3MF plates (out/3mf/tux_clip).

Every clip plate has two colour changes, already set in the 3MF: white at
layer_top(Z_WHITE) and orange at layer_top(Z_ORANGE). The coupon has none.

Exits with status 1 if any part fails a check.
"""

import sys
from pathlib import Path

from build123d import Part

from common.export import Change, Plates, centred, export_model, row

from . import params as P
from .model import (
    clip_colours,
    coupon_mechanism,
    desk_colours,
    leaf_slot_b,
    make_clip,
    make_coupon,
    make_desk,
    mechanism,
)

MODEL = "tux_clip"
M600_WHITE, M600_ORANGE = P.M600_WHITE, P.M600_ORANGE  # defined in params.py
CHANGES: list[Change] = [(M600_WHITE, "white"), (M600_ORANGE, "orange")]

# Declared widths, checked by the tests: thin features must be whole lines (2 or more),
# gaps at least one line.
THIN_FEATURES = {"flexure": P.FLEX_T, "tooth": P.TOOTH_W}
GAPS = {"tooth side gap": P.TOOTH_GAP, "tooth tip gap": P.TIP_GAP, "slot": P.SLOT_MIN,
        **{f"leaf slot {n} lines": -leaf_slot_b(coupon_mechanism(n)) - P.lines(n) / 2
           for n in P.COUPON_LINES},
        "leaf to jaw slot": min(-leaf_slot_b(mechanism(s)) - P.FLEX_T / 2 for s in P.SIZES)}


def printable_parts() -> dict[str, Part]:
    """name -> part on the bed (z=0), in its print orientation (on its back)."""
    parts = {f"tux_clip_{size}": make_clip(size) for size in P.SIZES}
    parts["tux_clip_desk"] = make_desk()
    parts["coupon_flexure"] = make_coupon()
    return parts


def colour_parts() -> dict[str, list[tuple[Part, str]]]:
    """name -> the part split into its colours, from the bottom up."""
    parts = {f"tux_clip_{size}": list(clip_colours(size)) for size in P.SIZES}
    parts["tux_clip_desk"] = list(desk_colours())
    parts["coupon_flexure"] = [(make_coupon(), "black")]
    return parts


# the colour changes each plate must have; slicer.py checks the real G-code against this
PLANNED_M600: dict[str, list[Change]] = {
    **{f"tux_clip_{size}": CHANGES for size in P.SIZES},
    "tux_clip_all_sizes": CHANGES,
    "tux_clip_desk": CHANGES,
}


def plates() -> Plates:
    """plate name -> ([(object name, part on the bed, start colour)], colour changes)."""
    pp = printable_parts()
    out: Plates = {}
    for size in P.SIZES:
        name = f"tux_clip_{size}"
        out[name] = ([(name, centred(pp[name]), "black")], PLANNED_M600[name])
    sizes = [f"tux_clip_{size}" for size in P.SIZES]
    out["tux_clip_all_sizes"] = (
        [(n, p, "black") for n, p in zip(sizes, row([pp[n] for n in sizes]))],
        PLANNED_M600["tux_clip_all_sizes"])
    out["tux_clip_desk"] = ([("tux_clip_desk", centred(pp["tux_clip_desk"]), "black")],
                            PLANNED_M600["tux_clip_desk"])
    out["coupon_flexure"] = ([("coupon_flexure", centred(pp["coupon_flexure"]), "black")], [])
    return out


def export_all(out: Path) -> dict[str, list[str]]:
    report = export_model(out, MODEL, printable_parts(), plates())
    print(f"\nColour changes (M600, 0.2 mm layers): white at Z = {M600_WHITE:.2f} mm, "
          f"orange at Z = {M600_ORANGE:.2f} mm. The 3MF plates already have them.")
    return report


if __name__ == "__main__":
    result = export_all(Path(sys.argv[1] if len(sys.argv) > 1 else "out"))
    sys.exit(1 if any(result.values()) else 0)
