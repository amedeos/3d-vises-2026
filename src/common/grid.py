"""The slicer grid: 0.2 mm layers and 0.45 mm lines (Prusa MK4, 0.4 mm nozzle,
PrusaSlicer "0.20mm STRUCTURAL").

In its print position, every flat horizontal face of a part must sit on a layer boundary,
and thin walls must be a whole number of extrusion lines. The tests check both.
"""

from math import ceil, floor, pi

NOZZLE = 0.4
LAYER = 0.2  # layer height
FIRST_LAYER = 0.2  # first layer height
LINE_W = 0.45  # extrusion width (perimeters and infill)
# centre distance of two touching lines, as PrusaSlicer computes it
LINE_SPACING = LINE_W - LAYER * (1 - pi / 4)


def lines(n: int) -> float:
    """Width of a wall made of n touching extrusion lines."""
    return (n - 1) * LINE_SPACING + LINE_W


def line_count(width: float) -> float:
    """How many lines a wall of this width holds (a whole number for a good wall)."""
    return (width - LINE_W) / LINE_SPACING + 1


def layers(n: int) -> float:
    """Height of n layers."""
    return round(n * LAYER, 6)


def layer_top(z: float) -> float:
    """Top (print_z) of the first layer that starts at or above height z."""
    if z <= 1e-9:
        return FIRST_LAYER
    k = ceil((z - FIRST_LAYER) / LAYER - 1e-9) + 1
    return round(FIRST_LAYER + k * LAYER, 6)


def snap_down(z: float) -> float:
    """Largest layer boundary at or below z (boundaries: 0, FIRST_LAYER, + n * LAYER)."""
    if z < FIRST_LAYER - 1e-9:
        return 0.0
    return round(FIRST_LAYER + floor((z - FIRST_LAYER) / LAYER + 1e-9) * LAYER, 6)


def snap_up(z: float) -> float:
    """Smallest layer boundary at or above z (boundaries: 0, FIRST_LAYER, + n * LAYER)."""
    if z <= FIRST_LAYER:
        return 0.0 if z <= 1e-9 else FIRST_LAYER
    return round(FIRST_LAYER + ceil((z - FIRST_LAYER) / LAYER - 1e-9) * LAYER, 6)


def on_grid(z: float, tol: float = 1e-3) -> bool:
    """True if z is a layer boundary (0, FIRST_LAYER, FIRST_LAYER + n * LAYER)."""
    if abs(z) < tol:
        return True
    n = round((z - FIRST_LAYER) / LAYER)
    return n >= 0 and abs(FIRST_LAYER + n * LAYER - z) < tol
