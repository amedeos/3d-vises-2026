"""Printability on a Prusa MK4: 0.4 mm nozzle, PrusaSlicer "0.20mm STRUCTURAL" profile.

Parametrised over every model and every printable part (see conftest.MODELS).
"""

import pytest

from common import grid
from common.grid import LAYER, LINE_W, layer_top, line_count, lines, on_grid
from common.printability import (
    colour_bands,
    islands,
    layer_sections,
    narrow_gaps,
    off_grid_faces,
    overhangs,
    thin_material,
)
from conftest import MODELS, all_parts, all_plates, colour_parts, export_module, parts, plates

PARTS = all_parts()
PLATES = all_plates()


def test_profile_assumptions():
    assert grid.FIRST_LAYER == grid.LAYER == 0.2
    assert grid.LINE_W == 0.45 and grid.NOZZLE == 0.4
    assert lines(1) == pytest.approx(LINE_W)
    assert lines(2) == pytest.approx(0.857, abs=1e-3)
    assert line_count(lines(3)) == pytest.approx(3)


@pytest.mark.parametrize("model,name", PARTS)
def test_flat_faces_sit_on_layer_boundaries(model, name):
    assert off_grid_faces(parts(model)[name]) == []


@pytest.mark.parametrize("model,name", PARTS)
def test_colours_are_stacked_along_z(model, name):
    """Each colour is a horizontal slab: no two colours share a layer, and every colour
    boundary is a layer boundary."""
    bands = colour_bands(colour_parts(model)[name])
    assert bands[0][1] == pytest.approx(0, abs=1e-3)
    for colour, z0, z1 in bands:
        assert on_grid(z0) and on_grid(z1), (colour, z0, z1)
    for (c0, _, top), (c1, bottom, _) in zip(bands, bands[1:]):
        assert c0 != c1
        assert bottom == pytest.approx(top, abs=1e-3), f"{c0} ends at {top}, {c1} starts at {bottom}"


@pytest.mark.parametrize("model,name", PARTS)
def test_each_colour_rests_on_the_colour_below(model, name):
    """The footprint of every colour lies inside the footprint of the colour below it.

    Some edges are shared on purpose (the white pads under the feet and the beak), so the
    lower footprint gets 0.02 mm of tolerance against tessellation slivers."""
    from shapely.ops import unary_union

    bands = colour_bands(colour_parts(model)[name])
    part = parts(model)[name]
    for (_, z0, z1), (_, z2, z3) in zip(bands, bands[1:]):
        below, above = layer_sections(part, [z1 - LAYER / 2, z2 + LAYER / 2])
        sticking_out = unary_union(above).difference(unary_union(below).buffer(0.02)).area
        assert sticking_out < 0.05, f"{sticking_out:.2f} mm2 over nothing at z={z2}"


@pytest.mark.parametrize("model,plate", PLATES)
def test_colour_changes_match_the_colour_bands(model, plate):
    """The planned M600s are exactly the colour boundaries of the parts on the plate,
    at the print_z of the first layer of each new colour, and at most 3."""
    mod = export_module(model)
    objects, changes = plates(model)[plate]
    assert changes == mod.PLANNED_M600.get(plate, [])
    assert len(changes) <= 3
    expected = set()
    for obj, _, _ in objects:
        bands = colour_bands(colour_parts(model)[obj])
        expected |= {(round(layer_top(z0), 2), c) for c, z0, _ in bands[1:]}
    assert sorted(expected) == sorted((round(z, 2), c) for z, c in changes)


@pytest.mark.parametrize("model,name", PARTS)
def test_no_floating_islands(model, name):
    """Every island of every layer rests on the layer below (nothing starts in mid-air)."""
    assert islands(parts(model)[name]) == []


@pytest.mark.parametrize("model,name", PARTS)
def test_overhangs_are_45_degrees_or_steeper(model, name):
    assert overhangs(parts(model)[name], 45.0) == []


@pytest.mark.parametrize("model", MODELS)
def test_declared_widths(model):
    """Thin features are a whole number of lines, at least 2. Gaps are at least 1 line."""
    mod = export_module(model)
    for feature, width in mod.THIN_FEATURES.items():
        n = line_count(width)
        assert n == pytest.approx(round(n), abs=1e-6) and round(n) >= 2, (feature, width, n)
    for gap, width in mod.GAPS.items():
        assert width >= LINE_W - 1e-9, (gap, width)


def _band_sections(model, name):
    """One cross-section in the middle of each colour band."""
    bands = colour_bands(colour_parts(model)[name])
    heights = [(z0 + z1) / 2 for _, z0, z1 in bands]
    return zip(bands, layer_sections(parts(model)[name], heights))


@pytest.mark.parametrize("model,name", PARTS)
def test_nothing_thinner_than_two_lines(model, name):
    # a disk a little narrower than 2 lines must reach all the material; corners and
    # tips lose a little, so pieces under 0.25 mm2 are ignored
    for (colour, z0, z1), polys in _band_sections(model, name):
        assert thin_material(polys, 0.95 * lines(2)) == [], (colour, z0, z1)


@pytest.mark.parametrize("model,name", PARTS)
def test_no_gap_narrower_than_one_line(model, name):
    for (colour, z0, z1), polys in _band_sections(model, name):
        assert narrow_gaps(polys, 0.9 * LINE_W) == [], (colour, z0, z1)
