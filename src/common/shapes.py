"""Small geometry helpers shared by the part modules."""

from math import sqrt

from build123d import Box, Circle, Part, Polygon, Pos, Sketch


def box_between(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> Part:
    """Axis-aligned box from its min and max corners."""
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def polygon(*pts) -> Sketch:
    """A closed polygon through the points, as a Sketch."""
    return Sketch() + Polygon(*pts, align=None)


def teardrop(radius: float) -> Sketch:
    """A circle with a pointed 45-degree roof towards +y (local frame of the sketch).

    Extruded along a horizontal axis, it makes a hole that prints without support: the
    roof replaces the top of the circle, where the surface would be flatter than 45
    degrees.
    """
    s = radius / sqrt(2)
    return Sketch() + Circle(radius) + Polygon((-s, s), (s, s), (0, radius * sqrt(2)),
                                               align=None)
