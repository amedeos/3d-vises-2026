"""Single source of truth for every Tux Vise dimension (millimetres, degrees unless noted).

Assembly frame ("use"): x runs along the screw, from Tux (x = 0 side) to the fish knob;
y across; z up; the bottom of the base on z = 0.

- Tux (the fixed jaw) stands at the x = 0 end, his belly facing +x. He prints on his back
  with black, white and orange (two M600), like the clip, and plugs into the base.
- The base carries a dovetail rail along x and, at the far end, the end block with the
  nut pocket.
- The moving jaw is a flipper. It slides on the rail; its face is the clamping face.
- The screw goes through the nut in the end block. Its head sits in a chamber in the jaw
  and a fork, dropped into the jaw from above, keeps it there: turning the fish knob
  pushes the jaw closed and pulls it open.
- The nut is a separate insert, printed with its axis vertical, so the thread prints
  well. The screw prints vertically too, standing on its fish knob.

Every part is printed in its own pose (see model.py): the base, the jaw and the end block
upright as used; Tux, the fork and the fish flat; the nut and the screw with the thread
axis vertical.
"""

from common.grid import FIRST_LAYER, LAYER, LINE_W, layer_top, layers, lines, snap_up  # noqa: F401

# --- Tux, the fixed jaw: printed on his back ------------------------------------------
TUX_H = 64.0  # Tux height, feet to head
T_TUX = layers(30)  # 6.0 mm black plate
T_WHITE = layers(3)  # 0.6 mm white: the belly is the face of the fixed jaw
T_ORANGE = layers(2)  # 0.4 mm orange: beak and feet stand this far proud of the belly
Z_WHITE = T_TUX  # colour boundary black -> white (print pose)
Z_ORANGE = T_TUX + T_WHITE  # colour boundary white -> orange
# M600 heights (print_z of the first layer of the new colour). Only Tux changes colour.
M600_WHITE = layer_top(Z_WHITE)
M600_ORANGE = layer_top(Z_ORANGE)
TENON_W = 20.0  # tab under Tux's feet that plugs into the base
CLR_FIT = 0.15  # per side: tenon in its mortise, nut in its pocket

# --- base ------------------------------------------------------------------------------
BASE_W = 40.0  # width at the bottom
T_PLATE = layers(40)  # 8.0 mm plate
BEVEL = 2.0  # 45-degree bevel on the two long bottom edges (the desk foot holds them)
BACK_T = 5.0  # backstop behind Tux (Tux leans on it when the vise clamps)
BACK_W = 26.0
BACK_H = 34.0

# --- dovetail rail along x, on the plate (same profile as the Halloween coffin rail) ---
RAIL_STEM_W = 6.0
RAIL_HEAD_W = 10.0  # 45-degree flare from the stem to the head
RAIL_HEAD_Z0 = T_PLATE + 1.6  # where the flare starts
RAIL_HEAD_Z1 = T_PLATE + 4.0  # top of the rail
CLR_SLIDE = 0.30  # per side, rail <-> jaw slot

# --- thread: a trapezoid with 45-degree flanks ------------------------------------------
# ISO 2904 trapezoidal threads have 15-degree flanks: printed vertically, every tooth
# would overhang at 15 degrees from horizontal. This trapezoid keeps ISO's pitch and
# diameter but has 45-degree flanks, so it prints vertically with no overhang flatter
# than 45 degrees. The crest flat and the root gap are one line wide each.
THREAD_D = 14.0  # major diameter
PITCH = 3.0
THREAD_FLANK = 45.0  # flank angle from the axis-normal plane (ISO: 15)
THREAD_FLAT = LINE_W  # crest flat and root gap
# depth from the pitch: P = flat + 2 * depth * tan(90 - flank) + flat
THREAD_DEPTH = (PITCH - 2 * THREAD_FLAT) / 2  # 1.05 mm with 45-degree flanks
# Radial clearance, given to the nut only (the screw is nominal). With 45-degree flanks,
# a radial clearance c is 0.71 c across the flanks and about 2 c of axial play. The
# thread coupon picks it: CLR_THREAD is the 2-dot hole.
THREAD_GAUGE = (0.15, 0.25, 0.35, 0.45)  # radial clearances of the four coupon holes
CLR_THREAD = THREAD_GAUGE[1]
CLR_BORE = 0.40  # radial, plain holes the screw passes through
MIN_TURNS = 3  # thread engagement at every jaw position, in turns

# --- nut: a square insert, printed with its axis vertical --------------------------------
NUT_W = 24.0
NUT_L = layers(60)  # 12.0 mm = 4 turns

# --- end block, at the far end of the base -----------------------------------------------
WALL_IN = 4.0  # wall between the jaw and the nut
WALL_OUT = 5.0  # outer wall: the clamping force pushes the nut against it
WALL_SIDE = 4.0
POCKET_FLOOR = T_PLATE + layers(30)  # 14.0: the nut rests here
Z_AXIS = POCKET_FLOOR + NUT_W / 2  # 26.0: the screw axis

# --- moving jaw (a flipper), printed upright -------------------------------------------
JAW_T = 18.0  # length along x
JAW_Z0 = T_PLATE + layers(3)  # 8.6: bottom of the jaw, clear of the plate
FACE_T = 3.0  # front plate, between the clamping face and the head chamber
FEET_RECESS = 1.0  # the lower front steps back over Tux's feet (they stand T_ORANGE proud)

# --- screw head and the fork that holds it --------------------------------------------
HEAD_D = 11.0
HEAD_L = 4.0  # including the 45-degree cone under the head
NECK_D = 8.0
HEAD_PLAY = 0.6  # axial play of the head in its chamber
FORK_T = layers(15)  # 3.0 mm, printed flat
FORK_W = 16.0
CLR_FORK = 0.20  # per side, fork in its slot and around the neck
THREAD_GAP = 0.6  # the thread starts this far behind the jaw's back face

# --- travel and the fish knob --------------------------------------------------------------
OPEN_MAX = 35.0  # jaw opening, from the white belly to the jaw face
KNOB_T = layers(30)  # 6.0 mm fish, printed flat; the screw stands on it
KNOB_GAP = 2.0  # fish to the end block at the closed position
KNOB_R = Z_AXIS - 2.0  # the fish turns within this radius, clear of the desk

# --- layout along x (assembly), derived ----------------------------------------------------
X_TUX = BACK_T  # Tux's back
X_BELLY = X_TUX + T_TUX + T_WHITE  # the white belly: opening 0
X_ORANGE = X_TUX + T_TUX + T_WHITE + T_ORANGE  # beak and feet
X_RAIL0 = X_ORANGE + 0.4  # the rail starts in front of Tux's feet
X_END = X_BELLY + OPEN_MAX + JAW_T  # end block inner face: the jaw stops here
X_POCKET0 = X_END + WALL_IN
X_POCKET1 = X_POCKET0 + NUT_L + 2 * CLR_FIT
BASE_L = X_POCKET1 + WALL_OUT

# --- thread coupon: four nut holes and 20 mm of screw ----------------------------------------
GAUGE_L = layers(45)  # 9 mm = 3 turns, the engagement the vise needs
GAUGE_PITCH = 22.0
GAUGE_STUB = 20.0  # length of the coupon screw's thread
