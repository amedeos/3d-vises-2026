# AGENTS.md

Guidance for coding agents working in this repository.

## Project

Two Tux-themed holding tools for the Printables contest
[Designer Challenge: Vises](https://www.printables.com/contest/534-vises) (contest id 534).
Both models share one code base.

1. **Tux Clip:** a print-in-place flexure clip shaped like Tux. The flippers are the jaws.
   Squeeze his shoulders and the flippers open. Sizes S, M and L, a desk version (Tux lies
   on an ice floe and holds a card upright) and a flexure coupon. Done: see README.
2. **Tux Vise:** a small desk vise. Tux's belly is the fixed jaw, a flipper is the moving
   jaw, a printed trapezoidal screw drives it and the knob is a gnu's head (GNU/Linux: the
   gnu moves Tux). Optional desk foot and a thread coupon. Done: see README.

- **Deadline:** entries close on 22 Nov 2026, 23:59 UTC.
- **Goal:** downloads and likes, not the prize. Every model must be recognisable at first
  glance, small, quick to print, with no supports, no metal hardware and no TPU.
- **Printer:** Original Prusa MK4 (Input Shaper firmware), one extruder, 0.4 mm nozzle.
  Colours come only from M600 filament changes at fixed heights (at most 3 per plate).
- **Slicer profile:** PrusaSlicer "Original Prusa MK4 Input Shaper 0.4 nozzle",
  "0.20mm STRUCTURAL @MK4IS 0.4", "Prusament PETG @PGIS". 0.2 mm layers (first layer too),
  0.45 mm lines. Textured sheet.
- **Material:** Prusament PETG (black, white, Yellow Gold). In the code the colour is `"yellow"`.
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
uv run python -m tux_clip.model            # flexure numbers per size (opening, swing, force)
uv run python -m tux_clip.export           # STLs -> out/stl/tux_clip, 3MF plates -> out/3mf/tux_clip
uv run python -m tux_clip.slicer           # optional, PrusaSlicer CLI: times, checks, projects
uv run python -m tux_clip.render           # PNG previews -> out/render/tux_clip (add --gif)
uv run python -m tux_vise.kinematics       # turns of the gnu -> opening, thread engagement
uv run python -m tux_vise.export           # out/stl/tux_vise, out/3mf/tux_vise
uv run python -m tux_vise.slicer           # optional
uv run python -m tux_vise.render           # out/render/tux_vise (add --gif)
```

- The full test suite takes about 45 s.

## Layout

| File | Role |
|---|---|
| `src/common/grid.py` | `LAYER`, `LINE_W`, `lines(n)`, `layer_top()`, `snap_up()`: the slicer grid |
| `src/common/tux.py` | The Tux profile (2D regions per colour), parametric by height |
| `src/common/shapes.py` | Small geometry helpers (`box_between`, `polygon`, `teardrop`) |
| `src/common/export.py` | Part checks, STL export, 3MF plates with M600 metadata |
| `src/common/render.py` | numpy z-buffer renderer (no OpenGL), PNG and GIF |
| `src/common/slicer.py` | Optional PrusaSlicer CLI step: times, M600 and support checks, projects |
| `src/common/printability.py` | Layer-grid, island, overhang and line-width analysis used by the tests |
| `src/tux_clip/params.py` | **Single source of truth** for every Tux Clip size and clearance |
| `src/tux_clip/model.py` | Clip parts per colour, desk version, coupon, flexure mechanics |
| `src/tux_clip/export.py`, `render.py`, `slicer.py` | Entry points (`python -m tux_clip.<name>`) |
| `src/tux_vise/params.py` | **Single source of truth** for the vise: layout along x, thread, clearances, foot |
| `src/tux_vise/thread.py` | The 45-degree trapezoidal thread (bd_warehouse `Thread`): screw, nut bore, threaded hole |
| `src/tux_vise/gnu.py` | The gnu knob of the three screws: our own stylised gnu head, outline built with shapely |
| `src/tux_vise/model.py` | Every vise part in its print pose, `use_location()` / `assembly()`, foot, coupon |
| `src/tux_vise/kinematics.py` | Turns -> opening, thread engagement (from the geometry) |
| `src/tux_vise/export.py`, `render.py`, `slicer.py` | Entry points (`python -m tux_vise.<name>`). `export.thread_zones()` lists the threads the width tests skip. |
| `tests/conftest.py` | `MODELS`: the model packages the tests run on. Each `<model>.export` provides `printable_parts()`, `colour_parts()`, `plates()`, `PLANNED_M600`, `THIN_FEATURES`, `GAPS`. |
| `tests/` | pytest suite. Keep it green. |
| `docs/photos/` | Photos of real prints, used in the README. Small JPEGs (about 100 KB), no EXIF. |

## Tux Clip mechanism (do not break it)

- The clip prints **on its back**. Everything is 2.5D: one black profile extruded to
  `T_BODY`, white and yellow reliefs on top. Never add a feature that needs a different
  height inside the black body.
- Each flipper is a lever on a leaf flexure (`FLEX_LINES` lines wide). The mechanism lives
  in a local frame (a, b): a runs down the jaw line, b points away from the body, the
  origin is the virtual pivot (middle of the leaf). `Mechanism.plane` places it.
- **The leaf is not a circular arc.** A force on the flipper bends it with a curvature
  that is zero on the force's line and grows linearly away from it (`leaf_angle`). Two
  loads matter (`LOADS`): "squeeze" (fingers on the pad top, and the stop at the same
  place: a = a_pt) sets the stop and the opening; "jaw" (an object at the tip: a = a_tip)
  sets the clamping force and can push the flipper to the stop too. The peak strain is
  `t theta / 2L * (1 + L / 2|a_load|)`, at the end of the leaf farther from the load.
  Treating the leaf as an arc overstated the opening by about 25 % (code review, Nov 2026).
- `_solve` picks the shortest leaf whose peak strain at **both** stops stays within
  `PETG_SAFE_STRAIN` (half the 5.1 % elongation at yield) and that still leaves
  `MIN_TEETH` teeth on the jaw. A thicker leaf opens less, not more strained. The squeeze
  stop (pad meets the shoulder face b = t/2) is computed from the same pose (`_g_top`),
  the jaw stop from the same slot, so the leaf can never bend further.
- `pose(m, theta, load)` moves the flipper with the end of the bent leaf. Render,
  collision tests and the desk floe all use it: do not pose the flipper with a plain
  rotation.
- The body is cut by the area the flipper sweeps under both loads (`sweep_local`), then
  the jaw strip, the teeth and the shoulder stop are added back exactly
  (`body_extra_local`). That keeps the head round and the stop face exact. The stop face
  reaches `STOP_MARGIN` past the point where the pad lands (`stop_contact`).
- Desk version: a card is much wider than the jaw, so it stands on the desk with one end
  in the jaw and the rest along a groove in the floe (`CARD_GROOVE`). `desk_card()` places
  it and opens only the right flipper under the "jaw" load; a test checks that it fits.
- Comb teeth: `TOOTH_W = lines(2)`, side gap and tip gap 0.5 mm, overlap `PRELOAD`. The
  overlap is the preload: at rest the jaw is "closed past zero".
- The forces are small (0.04-0.15 N on a thin card at the tip, see README). That is the
  physics of a PETG leaf at a safe strain, not a bug. The coupon (2/3/4 line leaves) lets
  the owner trade opening for grip.
- Print time grows about 6.1 min + 1.46 min per cm3 of model (PrusaSlicer 2.9.6, flat
  parts). `test_print_time_budget` uses this to keep every clip under 30 min. The L size is
  75 mm with an 11 mm opening for that reason; 13 mm needs an 85 mm Tux (about 36 min).

## Tux Vise mechanism (do not break it)

- **Frames.** `params.py` describes the vise frame: x along the screw from Tux to the gnu,
  z up, the bottom of the base on z = 0. Every part is *built in its print pose* (that is
  what `printable_parts()` and the layer tests use) and `use_location(name, opening)`
  moves it into the vise. `assembly(opening)` places them all.
- **Thread.** Build every thread with `thread.py`, never directly with bd_warehouse: the
  screw, the vise nut, the foot nut and the four coupon holes must share one profile, so
  the coupon tells the truth. The flanks are 45 degrees (ISO 2904 has 15): that is what
  lets the thread print upright under the 45-degree overhang rule. Crest flat and root
  gap are one line. The clearance (`CLR_THREAD`, radial) is given to the nut only, through
  bd_warehouse's `manufacturing_compensation`; it is one of the `THREAD_GAUGE` values.
- **Clean thread solids.** With bd_warehouse's default interference (0.2) the fuse leaves
  zero-area faces along the root, which the overhang check reads as flat overhangs.
  `thread.py` uses 0.1 and a core 0.01 mm proud of the root. A plain shank next to a
  thread's square end must be 0.1 mm wider than the thread, or the end overhangs.
- **Screw and fork.** The screw's head sits in a chamber in the jaw; the fork, dropped into
  a slot from the top, catches the neck behind it. Pushing, the tip presses the chamber
  floor; pulling, the 45-degree cone under the head presses the fork. `head_play()` is
  computed from that geometry; the engagement is checked in both positions.
- **Stops.** Fully open, the jaw's back meets the end block (`X_END`); closed, its face meets
  the white belly (`X_BELLY` = opening 0). The beak and feet stand `T_YELLOW` proud: the
  jaw's top stays 1.5 mm under the beak (`jaw_top()`) and its lower front steps back over
  the feet.
- **45-degree roofs.** Horizontal holes in upright parts are teardrops
  (`common.shapes.teardrop`). The jaw's rail slot has a 45-degree gable instead of a flat
  ceiling. Where two 45-degree roofs cross, the line where they meet is flatter than 45
  degrees: PrusaSlicer adds support there, while `printability.overhangs` (face normals)
  does not see it. Keep roofs from crossing (the feet recess stays above the slot roof).
- **Width tests on 3D parts.** `test_layers` takes a section every 1 mm in each colour band
  and skips the discs that `export.thread_zones()` declares: a horizontal slice of a
  thread cuts each tooth into a crescent that tapers to nothing. The tooth itself is
  2.55 mm wide at its root.
- **Collisions.** Never intersect the helical solids (slow and fragile). The tests check the
  screw as plain cylinders (`screw_envelope`) against every part but the nut, and the
  screw/nut fit on the profile. The physical fit is the coupon's job.
- **Plates.** A plate without M600 prints in one filament, so parts that share a plate share
  a colour (`export.COLOUR`). Only Tux changes colour.
- **Print time.** Tall thin parts (the screws, the coupon stub) are slow because of the
  slicer's minimum layer time, not because of their volume.
- **Gnu knob.** All three screws (vise, foot, coupon) stand on the same gnu head,
  `gnu_sketch(GNU_R)`. `GNU_R` is its own parameter, so the foot and the coupon do not
  depend on the vise layout; the vise's knob must still fit within `KNOB_R` (a test checks
  it). It is our own drawing, not the GNU logo (a trademark; its fine hair would be
  thinner than two lines). Its outline is built in shapely, because build123d's 2D offsets
  fail on it: a closing (notches under a line) and an opening (tips of at least two
  lines), so it passes the width tests by construction. The knob carries the plain shank
  (`SHANK_R`): it covers the shank's disc, and the eyes and nostrils (holes) stay outside
  it, or the shank's bottom would hang over a hole. Each hole also keeps two lines of wall
  to the outline. Below about 23.2 mm the nostrils do not fit: `gnu_sketch` raises an
  error. `make_screw` turns the gnu over so that, in the renders, its horns point up at
  every whole turn from fully open (`render.upright` picks those openings). On a printed
  vise the knob's angle at a given opening depends on how the nut sits in its pocket:
  nothing in the design sets it.

## Layers and lines (0.4 mm nozzle, 0.2 mm layers)

- In its print position, **every flat horizontal face must sit on a layer boundary**
  (k × `LAYER`). Use `snap_up()` for derived heights.
- Thin walls are a whole number of lines: use `lines(n)`, never `n * LINE_W`.
  `lines(2)` is 0.857 mm. The minimum is 2 lines.
- Gaps and grooves are at least `LINE_W` wide.
- Every layer rests on the layer below (no islands). Overhangs are 45° or steeper.
- The width tests use an exact morphological opening of each section
  (`shapely` `buffer(-r).buffer(r)`), with 0.03 mm of tolerance for the mesh. A raster
  version could not tell 0.80 mm from 2 lines (0.857 mm).

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
- PrusaSlicer ignores the object colours of a 3MF (`displaycolor`). It shows the layers
  before the first M600 in the filament profile's `filament_colour` (`#FF8000`, orange, for
  Prusament PETG). `slicer.py` writes the plate's start colour (the object colour) as
  `filament_colour` in each project and checks that a slice of the project reads it back.
  A plain plate cannot carry it without becoming a project (a 3MF with
  `Slic3r_PE.config`), and the plain plates must work with any printer profile.
- The CLI crashes on `--export-3mf` without a display (it renders a thumbnail with
  OpenGL). So `slicer.py` slices to text G-code instead. It copies the
  `; prusaslicer_config` block into `Metadata/Slic3r_PE.config` and sets
  `binary_gcode = 1` again.
- The MK4 profiles build supports only inside support enforcers, so a normal slice never
  shows a missing support. `slicer.py` slices once more with
  `--support-material --support-material-auto --dont-support-bridges`; the result must have
  no support extrusions.
- `--printer-profile` needs a PrusaSlicer data folder with the Prusa vendor profiles
  installed (Configuration Wizard). **Without them the CLI does not fail: it slices with
  its defaults** (a 200 x 200 mm bed, no filament density), drops parts outside that bed
  and gives wrong times. `slicer.py` flags a bed that is not the MK4 one and then writes no
  project. Copying the vendor `.ini` into a bare `--datadir` was not enough. What works:
  `PRUSA_CONFIG` pointing to a full config (the `Metadata/Slic3r_PE.config` of a project
  3MF made on a machine with the profiles, without the `; ` prefixes), loaded with
  `--load`.
- With colour changes, PrusaSlicer 2.9 writes `total filament used [g] = 0.00`.
  `slicer.py` computes the grams from `filament used [cm3]` and `filament_density`.

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
- Where two curved shapes meet at a sharp angle (belly and feet, upper and lower beak), the
  notch is narrower than a line. `tux.close_crevices` fills it (offset out and back in).
- Do not check overhangs on a mesh: a curved vertical wall gets thin, tilted triangles.
  `printability.overhangs` samples the exact face normals instead.
- Shared edges between two colours (the white pad under each foot has the outline of the
  foot) give tessellation slivers; the colour-stacking test allows 0.02 mm.

## Git

Do not commit or push unless the owner asks.
