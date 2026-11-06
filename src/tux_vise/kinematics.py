"""Tux Vise kinematics: turns of the fish knob -> jaw opening, and the thread engagement.

    uv run python -m tux_vise.kinematics

One turn moves the jaw by one PITCH. The screw pushes the jaw with its tip on the chamber
floor, and pulls it with its head on the fork, so the screw sits up to `head_play()`
further out when the jaw opens. The engagement is the overlap of the screw's thread with
the nut, measured on the geometry of both parts.
"""

from . import params as P
from .model import fork_x, nut_x0, screw_stations, tip_x


def head_play() -> float:
    """How far the screw can move out of the jaw from its pushing position: until the
    45-degree cone under its head is as wide as the fork's opening, with the fork pushed
    to the back of its slot."""
    fork_front = fork_x() + 2 * P.CLR_FORK
    cone_contact = P.HEAD_L - P.CLR_FORK  # the cone's radius there: NECK_D / 2 + CLR_FORK
    return fork_front - P.FACE_T - cone_contact


def turns_to_close(opening: float) -> float:
    """Turns of the knob from fully open to `opening`."""
    return (P.OPEN_MAX - opening) / P.PITCH


def opening_after(turns: float) -> float:
    """Jaw opening after `turns` from fully open (0 = closed on the belly)."""
    return max(0.0, P.OPEN_MAX - turns * P.PITCH)


def thread_span(opening: float, play: float = 0.0) -> tuple[float, float]:
    """x range of the screw's thread, with the screw `play` further out than pushing."""
    st, tip = screw_stations(), tip_x(opening) + play
    return tip + st["thread0"], tip + st["thread1"]


def nut_span() -> tuple[float, float]:
    return nut_x0(), nut_x0() + P.NUT_L


def overlap_turns(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Turns of thread where the ranges a (thread) and b (nut) overlap."""
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0])) / P.PITCH


def engaged_turns(opening: float) -> float:
    """Turns of thread inside the nut, in the worse of the push and pull positions."""
    return min(overlap_turns(thread_span(opening, play), nut_span())
               for play in (0.0, head_play()))


def table(step: float = 1.0) -> list[tuple[float, float, float]]:
    """(turns from fully open, opening, engaged turns), every `step` turns."""
    rows, k = [], 0
    total = turns_to_close(0.0)
    while k * step < total + 1e-9:
        t = k * step
        rows.append((t, opening_after(t), engaged_turns(opening_after(t))))
        k += 1
    if rows[-1][0] < total - 1e-9:
        rows.append((total, 0.0, engaged_turns(0.0)))
    return rows


if __name__ == "__main__":
    print(f"Tux Vise: pitch {P.PITCH} mm, opening 0-{P.OPEN_MAX:.0f} mm, "
          f"{turns_to_close(0):.1f} turns from fully open to closed\n")
    print(" turns   opening   thread in the nut")
    for t, opening, engaged in table():
        print(f"{t:6.1f}   {opening:5.1f} mm   {engaged:.1f} turns")
