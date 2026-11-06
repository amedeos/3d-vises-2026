"""The printed thread: a trapezoid with 45-degree flanks, made with bd_warehouse.

Every threaded part (the screw, the nut, the coupon's nut holes and stub) is built here,
from the same profile, so whatever fits on the thread coupon fits in the vise.

All threads are built along +z (their print axis), starting at z = 0.
"""

from math import radians, tan

from bd_warehouse.thread import Thread
from build123d import Align, Cylinder, Part, Pos

from . import params as P

# The thread is fused into a core (screw) or a bore (nut). A small interference and a
# core 0.01 mm proud of the thread root give clean solids: with bd_warehouse's default
# interference (0.2) the fuse leaves zero-area faces along the root.
INTERFERENCE = 0.1
CORE_OVERLAP = 0.01

ROOT_R = P.THREAD_D / 2 - P.THREAD_DEPTH  # screw core radius
CREST_W = P.THREAD_FLAT  # axial width of the crest flat
ROOT_W = P.THREAD_FLAT + 2 * P.THREAD_DEPTH * tan(radians(P.THREAD_FLANK))  # tooth at its root


def _cylinder(r: float, length: float) -> Part:
    return Cylinder(r, length, align=(Align.CENTER, Align.CENTER, Align.MIN))


def screw_thread(length: float, ends=("square", "chamfer")) -> Part:
    """External thread on its core, from z = 0 to z = length (nominal size)."""
    thread = Thread(apex_radius=P.THREAD_D / 2, apex_width=CREST_W, root_radius=ROOT_R,
                    root_width=ROOT_W, pitch=P.PITCH, length=length, end_finishes=ends,
                    interference=INTERFERENCE)
    return _cylinder(ROOT_R + CORE_OVERLAP, length) + thread


def nut_bore(length: float, clearance: float) -> tuple[Part, Part]:
    """(cutter, thread) for a threaded hole from z = 0 to z = length.

    Cut the cutter from the part, then add the thread. `clearance` is radial: the whole
    internal thread moves outwards by it (bd_warehouse's manufacturing_compensation).
    """
    thread = Thread(apex_radius=ROOT_R, apex_width=CREST_W, root_radius=P.THREAD_D / 2,
                    root_width=ROOT_W, pitch=P.PITCH, length=length,
                    end_finishes=("square", "square"), interference=INTERFERENCE,
                    manufacturing_compensation=clearance)
    cutter = _cylinder(P.THREAD_D / 2 + clearance - CORE_OVERLAP, length)
    return cutter, thread


def threaded_hole(part: Part, x: float, y: float, length: float, clearance: float) -> Part:
    """`part` with a vertical threaded hole at (x, y), from z = 0 to z = length."""
    cutter, thread = nut_bore(length, clearance)
    return (part - Pos(x, y, 0) * cutter) + Pos(x, y, 0) * thread

