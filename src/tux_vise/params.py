"""Single source of truth for every Tux Vise dimension (millimetres, degrees unless noted).

Assembly frame ("use"): x runs along the screw, from Tux (x = 0 side) to the gnu knob;
y across; z up; the bottom of the base on z = 0.

- Tux (the fixed jaw) stands at the x = 0 end, his belly facing +x. He prints on his back
  with black, white and orange (two M600), like the clip, and plugs into the base.
- The base carries a dovetail rail along x and, at the far end, the end block with the
  nut pocket.
- The moving jaw is a flipper. It slides on the rail; its face is the clamping face.
- The screw goes through the nut in the end block. Its head sits in a chamber in the jaw
  and a fork, dropped into the jaw from above, keeps it there: turning the gnu knob
  pushes the jaw closed and pulls it open.
- The nut is a separate insert, printed with its axis vertical, so the thread prints
  well. The screw prints vertically too, standing on its gnu knob.

Every part is printed in its own pose (see model.py): the base, the jaw and the end block
upright as used; Tux, the fork and the gnu flat; the nut and the screw with the thread
axis vertical.
"""

from math import radians, tan

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
THREAD_FLANK = 45.0  # flank angle from the axis-normal plane (ISO: 15); >= 45 to print
THREAD_FLAT = LINE_W  # crest flat and root gap
# Over the depth, each flank moves along the axis by depth * tan(flank), so one pitch is
# flat + 2 * depth * tan(flank) + flat.
THREAD_DEPTH = (PITCH - 2 * THREAD_FLAT) / (2 * tan(radians(THREAD_FLANK)))  # 1.05 mm
# Radial clearance, given to the nut only (the screw is nominal). With 45-degree flanks,
# a radial clearance c is 0.71 c across the flanks and about 2 c of axial play. The
# thread coupon picks it: CLR_THREAD is the 2-dot hole.
THREAD_GAUGE = (0.15, 0.25, 0.35, 0.45)  # radial clearances of the four coupon holes
CLR_THREAD = THREAD_GAUGE[1]
CLR_BORE = 0.40  # radial, plain holes the screw passes through
SHANK_R = THREAD_D / 2 + 0.1  # plain shank next to a thread: 0.1 mm wider, or the
# thread's square end overhangs
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
HEAD_PLAY = 0.6  # room behind the head, to the fork slot (kinematics.head_play() is the
# real axial play of the screw in the jaw: this plus the fork's clearances)
FORK_T = layers(15)  # 3.0 mm, printed flat
FORK_W = 16.0
CLR_FORK = 0.20  # per side, fork in its slot and around the neck
THREAD_GAP = 0.6  # the thread starts this far behind the jaw's back face

# --- travel and the gnu knob ---------------------------------------------------------------
OPEN_MAX = 35.0  # jaw opening, from the white belly to the jaw face
KNOB_T = layers(30)  # 6.0 mm gnu head, printed flat; the screw stands on it
KNOB_GAP = 2.0  # knob to the end block at the closed position
KNOB_R = Z_AXIS - 2.0  # the knobs of all three screws turn within this radius; the
# vise's knob stays clear of the desk

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

# --- desk foot (optional): a C clamp under the Tux end of the base ----------------------
# Printed on its side: its (y, z) profile on the bed, extruded along x. The base slides
# into the channel on top (its bevels go under the two lips) until it meets the cap. The
# foot screw goes up through a second nut and presses the underside of the desk.
FOOT_L = 28.0  # along x (the nut, 24 mm, slides in from the side)
FOOT_CAP = 2.0  # wall at one end of the channel: the base stops against it
LIP_W = 3.0  # lips over the base's bevels
LIP_TOP = BEVEL + 1.4  # height of the lips above the channel floor
T_ARM = 4.0  # top arm, between the base and the desk
SPINE_T = 7.0  # the upright in front of the desk edge
NUT_WALL = 3.0  # above and below the nut in the bottom arm
DESK_MIN = 15.0  # desk thickness range
DESK_MAX = 35.0
