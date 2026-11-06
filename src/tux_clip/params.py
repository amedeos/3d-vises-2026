"""Single source of truth for every Tux Clip dimension (millimetres, radians unless noted).

The clip prints **on its back**, face up. Everything is 2.5D: a flat profile extruded
along Z, so the flexures are vertical walls that bend in the XY plane. They bend along
their extrusion lines, never across the layers.

Colours are stacked along Z (one M600 before the first white layer, one before the first
orange layer):

- black  0 -> T_BODY: the whole silhouette, the flippers, the flexures and the jaw teeth
- white  T_BODY -> T_BODY + T_WHITE: belly, eyes, and pads under the beak and the feet
- orange -> + T_ORANGE: beak and feet

How it works: each flipper is a lever on a leaf flexure (a thin vertical wall). Above
the flexure is the shoulder pad, below it is the jaw. Squeeze the two shoulders towards
each other and the flipper tips swing out. At rest the teeth of the flipper and of the
body mesh like a comb, with their tips PRELOAD past each other, so the jaws hold even a
thin card with some force. A stop between the shoulder pad and the body limits the
swing, so the flexure never bends past PETG_SAFE_STRAIN (model.py computes the real,
uneven bend of the leaf, not a circular arc).

Frames: x to the right, y up, feet on y=0, centre line x=0 (as in common.tux). Each
mechanism lives in a local jaw frame (a, b): a runs along the jaw line, down and out,
b points away from the body. Its origin is the flexure's virtual pivot.
"""

from math import radians

from common.grid import FIRST_LAYER, LAYER, LINE_W, layer_top, layers, lines  # noqa: F401

# --- material: Prusament PETG technical data sheet v1.1 (16-02-2022), printed in XY -----
PETG_E = 1500.0  # tensile modulus (MPa)
PETG_E_FLEX = 1700.0  # flexural modulus (MPa): used for the flexure stiffness
PETG_YIELD_STRAIN = 0.051  # elongation at yield point, ISO 527-1 (5.1 % in XY and in Z)
# Allowed peak bending strain in the leaf: half the elongation at yield, so 2.55 %. The
# factor of 2 is for repeated use. It applies to the most bent point of the leaf.
PETG_SAFE_STRAIN = 0.5 * PETG_YIELD_STRAIN

# --- thickness and colours (print orientation: on the back) --------------------------
T_BODY = layers(24)  # 4.8 mm of black: the flexure height
T_WHITE = layers(3)  # 0.6 mm of white relief
T_ORANGE = layers(3)  # 0.6 mm of orange relief
Z_WHITE = T_BODY  # colour boundary black -> white (4.8 mm)
Z_ORANGE = T_BODY + T_WHITE  # colour boundary white -> orange (5.4 mm)
# M600 heights: PrusaSlicer's print_z of the first layer of the new colour. Every clip
# plate and the desk plate change to white at 5.00 mm and to orange at 5.60 mm; the
# flexure coupon has no colour change.
M600_WHITE = layer_top(Z_WHITE)
M600_ORANGE = layer_top(Z_ORANGE)

# --- sizes: Tux height and the jaw opening at the flipper tip ------------------------
# The openings are a little under the most each height allows, so the jaw keeps 7-9
# teeth. L: 13 mm needs an 85 mm Tux (about 36 min) and 18 mm a 95 mm Tux (about 43 min);
# a 75 mm Tux stays under 30 min and opens 11 mm.
SIZES = {
    "S": {"height": 50.0, "opening": 4.0},
    "M": {"height": 65.0, "opening": 8.0},
    "L": {"height": 75.0, "opening": 11.0},
}

# --- the flipper and its jaw (fractions of the height, or mm) -------------------------
FLIPPER_ANGLE = radians(12.0)  # jaw line, from vertical, tip pointing out
SHOULDER = (0.218, 0.617)  # top of the shoulder pad on the jaw line (x, y as fractions of H)
FLIPPER_LEN = 0.46  # from the top of the pad to the tip, along the jaw line (x H)
PAD_TOP = 1.5  # the pad reaches this far above the top of the flexure: the stop is there

# --- flexure ---------------------------------------------------------------------------
FLEX_LINES = 2  # leaf thickness in extrusion lines (the coupon tests 2, 3 and 4)
FLEX_T = lines(FLEX_LINES)

# --- comb teeth on the jaws --------------------------------------------------------------
PRELOAD = 1.0  # at rest the tooth tips reach this far past each other
TOOTH_W = lines(2)  # tooth width along the jaw
TOOTH_GAP = 0.5  # side gap between a flipper tooth and a body tooth (>= LINE_W)
TIP_GAP = 0.5  # tooth tip to the opposite jaw (>= LINE_W)
TOOTH_D = PRELOAD + TIP_GAP  # how far a tooth sticks out of its jaw
JAW_W = 2 * TOOTH_D - PRELOAD  # distance between the two jaw faces (tooth bases)
BRIDGE = 1.6  # solid top of the flipper's jaw, where the flexure joins it
SLOT_MIN = 0.5  # narrowest slot around the flexure (>= LINE_W)
MIN_TEETH = 3  # the jaw keeps at least body, flipper, body tooth (a longer leaf = shorter jaw)
STOP_MARGIN = 1.0  # the flat stop face reaches this far past the point the pad lands on

# --- desk version: Tux lies on a flat ice floe ------------------------------------------
DESK_SIZE = "M"
T_BASE = layers(12)  # 2.4 mm thick base plate, solid
BASE_MARGIN = 9.0  # the floe reaches this far around Tux
FLIPPER_CLEARANCE = 1.0  # free space around the swept area of each flipper
# A card stands on the desk with one end in the jaw; the rest of its bottom edge runs
# along this groove through the floe, which continues the jaw line past the flipper tip.
CARD_GROOVE = 3.0

# --- flexure coupon: three short levers with 2, 3 and 4 line leaves -----------------------
COUPON_LINES = (2, 3, 4)
COUPON_SIZE = "S"  # the levers copy this size's flexure and jaw
