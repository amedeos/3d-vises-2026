# AGENTS.md

Guidance for coding agents working in this repository.

## Project

Two Tux-themed holding tools for the Printables contest
[Designer Challenge: Vises](https://www.printables.com/contest/534-vises) (contest id 534).
Both models share one code base.

1. **Tux Clip:** a print-in-place flexure clip shaped like Tux. The flippers are the jaws.
   Squeeze his shoulders and the flippers open. Sizes S, M and L, a desk version and a
   flexure coupon.
2. **Tux Vise:** a small desk vise. Tux's belly is the fixed jaw, a flipper is the moving
   jaw, a printed trapezoidal screw drives it and the knob is a fish. (Phase 3: not started.)

- **Deadline:** entries close on 22 Nov 2026, 23:59 UTC.
- **Goal:** downloads and likes, not the prize. Every model must be recognisable at first
  glance, small, quick to print, with no supports, no metal hardware and no TPU.
- **Printer:** Original Prusa MK4 (Input Shaper firmware), one extruder, 0.4 mm nozzle.
  Colours come only from M600 filament changes at fixed heights (at most 3 per plate).
- **Slicer profile:** PrusaSlicer "Original Prusa MK4 Input Shaper 0.4 nozzle",
  "0.20mm STRUCTURAL @MK4IS 0.4", "Prusament PETG @PGIS". 0.2 mm layers (first layer too),
  0.45 mm lines. Textured sheet.
- **Material:** Prusament PETG (black, white, orange).
- **License:** CC BY-SA 4.0. Tux by Larry Ewing (lewing@isc.tamu.edu), made with GIMP.
  Any bundled font must be under the SIL OFL.

## Language

- Write all repository text in **English at B2/C1 level**: README, docstrings, comments,
  commit messages. Use clear, short sentences and common words.
- The owner chats in Italian.

## Environment and commands

- Python 3.14 (3.13 also works), [uv](https://docs.astral.sh/uv/),
  [build123d](https://github.com/gumyr/build123d) 0.13, bd_warehouse 0.4 (threads).

```sh
uv sync
uv run pytest                              # all checks, both models
uv run python -m tux_clip.export           # STLs -> out/stl/tux_clip, 3MF plates -> out/3mf/tux_clip
uv run python -m tux_clip.slicer           # optional, PrusaSlicer CLI: times, checks, projects
uv run python -m tux_clip.render           # PNG previews -> out/render/tux_clip (add --gif)
```

## Layout

| File | Role |
|---|---|
| `src/common/grid.py` | `LAYER`, `LINE_W`, `lines(n)`, `layer_top()`, `snap_up()`: the slicer grid |
| `src/common/tux.py` | The Tux profile (2D regions per colour), parametric by height |
| `src/common/shapes.py` | Small geometry helpers (`box_between`, `ellipsoid`) |
| `src/common/export.py` | Part checks, STL export, 3MF plates with M600 metadata |
| `src/common/render.py` | numpy z-buffer renderer (no OpenGL), PNG and GIF |
| `src/common/slicer.py` | Optional PrusaSlicer CLI step: times, M600 and support checks, projects |
| `src/common/printability.py` | Layer-grid, island, overhang and line-width analysis used by the tests |
| `src/tux_clip/params.py` | **Single source of truth** for every Tux Clip size and clearance |
| `src/tux_clip/model.py` | Clip parts per colour, desk version, coupon, flexure mechanics |
| `src/tux_clip/export.py`, `render.py`, `slicer.py` | Entry points (`python -m tux_clip.<name>`) |
| `tests/` | pytest suite. Keep it green. |

## Layers and lines (0.4 mm nozzle, 0.2 mm layers)

- In its print position, **every flat horizontal face must sit on a layer boundary**
  (k × `LAYER`). Use `snap_up()` for derived heights.
- Thin walls are a whole number of lines: use `lines(n)`, never `n * LINE_W`.
  `lines(2)` is 0.857 mm. The minimum is 2 lines.
- Gaps and grooves are at least `LINE_W` wide.
- Every layer rests on the layer below (no islands). Overhangs are 45° or steeper.

## Colours (M600 on a single extruder)

- Every colour boundary is a flat horizontal plane in the print position, on a layer
  boundary. Colours are stacked along Z: never two colours on the same layer.
- The M600 goes before the first layer of the new colour: `layer_top(boundary)`.
- Build each colour as its own Part and union them for export. The export module of each
  model lists the planned changes in `PLANNED_M600`; `slicer.py` checks the real G-code
  against that table, not against the 3MF.
- Every model must also look like Tux when printed in one colour.

## Checks after any geometry change

1. Run `uv run pytest`.
2. Run the export. Every part must print `OK`.
3. Render and look at the images.
4. Compare the part volumes with the previous run. A boolean that fails **silently** can
   halve a part without any error.

## 3MF and PrusaSlicer notes

- PrusaSlicer reads `Metadata/Prusa_Slicer_custom_gcode_per_print_z.xml` even from a 3MF
  without print settings. That is how the M600 travels with the plates.
- The `code` and `mode` elements need `bed_idx="0"` (PrusaSlicer 2.9 has multiple beds).
  Without it the CLI still applies the colour change, but the GUI silently drops it.
- The CLI crashes on `--export-3mf` without a display (it renders a thumbnail with
  OpenGL). So `slicer.py` slices to text G-code instead. It copies the
  `; prusaslicer_config` block into `Metadata/Slic3r_PE.config` and sets
  `binary_gcode = 1` again.
- The MK4 profiles build supports only inside support enforcers, so a normal slice never
  shows a missing support. `slicer.py` slices once more with
  `--support-material --support-material-auto --dont-support-bridges`; the result must have
  no support extrusions.
- `--printer-profile` needs a PrusaSlicer data folder with the Prusa vendor profiles
  installed. On a machine without one, pass `--datadir` in `PRUSA_SLICER`.

## build123d gotchas

- `Box(..., align=None)` puts the box's **corner** at the origin, not its centre.
- With sketches on `Plane.XZ`, the order of the points decides the extrude direction.
  Pass `dir=` to `extrude`.
- A polygon drawn clockwise has a downward normal, so it extrudes downwards. Always pass
  `dir=(0, 0, 1)` when you extrude a sketch upwards.
- `split()` can return a list. `render` accepts lists.
- Cut overlapping 2D shapes one at a time. One cutting tool made of overlapping pieces
  can leave doubled edges.
- Never cut with a sphere or a cone where its pole or apex ends up on a visible surface.
  The STL gets degenerate triangles there.
- Part builders are cached (`functools.cache`). Never change a returned part in place.
  Transform it (`Pos(...) * part`) or combine it (`part & region`).

## Git

Do not commit or push unless the owner asks.
