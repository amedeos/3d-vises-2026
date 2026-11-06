# Tux Clip and Tux Vise 🐧

Two entries for the Printables contest **[Designer Challenge: Vises](https://www.printables.com/contest/534-vises)**.

Both models are Tux, the Linux penguin. They print without supports, need no screws, springs or other hardware, and get their colours from filament changes (M600) on a single-extruder printer.

The models are fully parametric. They are written in Python with [build123d](https://github.com/gumyr/build123d), and both share one code base.

## Tux Clip

A small clip shaped like Tux. **Squeeze his shoulders and his flippers open.** Let go and they close on whatever you put under them: a note, a photo, a ticket, a cable, the top of a bag.

It is one piece, printed in place: no assembly, nothing to snap in. It comes in three sizes, plus a desk version that holds a card upright, and a small coupon to feel the stiffness of the flexure.


### How it works

- **Flexure.** Each flipper hangs on a thin, flexible wall (a leaf, 2 lines wide). When you squeeze the shoulder, the leaf bends and the flipper swings out around it, like a seesaw.
- **Comb jaws.** The inside of each flipper and the side of the body have teeth that mesh like a comb. At rest the tips of the teeth reach **1 mm past each other**, without touching. So the jaw is already "closed past zero": a thin card must push the flipper open by its own thickness plus that millimetre, and the flexure presses back. Paper and thin plastic are held because they have to wave through the teeth.
- **Stop.** The top of the flipper meets the shoulder after a fixed swing. You cannot bend the leaf further than that, however hard you squeeze. That keeps the leaf at no more than half the elastic limit of PETG, so it does not tire.
- **Printed on its back.** The leaf is a vertical wall, so it bends along its extrusion lines, never across the layers. That is the strong direction of a 3D print.

| Size | Tux height | Jaw opening | Swing | Leaf length | Grip on a 1 mm card* |
|---|---|---|---|---|---|
| S | 50 mm | 5 mm | 21° | 10.2 mm | 0.31 N |
| M | 65 mm | 10 mm | 31° | 14.9 mm | 0.13 N |
| L | 75 mm | 13 mm | 33° | 16.0 mm | 0.09 N |

\* Calculated at the flipper tip, with a 2-line leaf. The grip is about twice as strong halfway up the jaw, and grows with the thickness of what you clamp. **Tux Clip is a gentle clip**: it holds notes, photos, tickets and cables, not a heavy stack of paper. If you want a firmer grip, print the coupon and use a thicker leaf (see below).

All the numbers come from `src/tux_clip/model.py`. The tests check the opening, the strain in the leaf, the preload of the comb, and that the flipper never touches the body over its whole swing.


### Desk version

Tux lies on his back on a small ice floe and holds a card upright in his flipper. Squeeze his shoulder, drop the card into the slot and let go. It is still one piece: the floe leaves room for the flippers to swing.

It holds a business card or a 10 × 15 cm photo. **It cannot hold a phone**: a phone is about 70 times heavier than a photo and would tip over (a test checks this limit).


### Printing

Prusa MK4 (Input Shaper firmware), **Prusament PETG**, 0.4 mm nozzle, **0.20mm STRUCTURAL** profile, **no supports**. PrusaSlicer confirms this: even with automatic supports turned on, it does not generate any. Use the textured or satin sheet: PETG sticks too much to the smooth PEI sheet.

There are three kinds of files. Use whichever you like:

- **`out/3mf/tux_clip/projects/*.3mf` — easiest.** PrusaSlicer projects with the MK4 + 0.20mm STRUCTURAL + Prusament PETG settings already loaded. The colour changes are already set.
- **`out/3mf/tux_clip/*.3mf`** — the same plates without print settings. They also include the colour changes. Use them with any printer profile.
- **`out/stl/tux_clip/*.stl`** — one file per part, already lying on its back.

| Plate (3MF) | Parts | Colours | Time* | Filament* |
|---|---|---|---|---|
| `tux_clip_S` | clip S | black, white, orange | 16 min | 5 g |
| `tux_clip_M` | clip M | black, white, orange | 23 min | 8 g |
| `tux_clip_L` | clip L | black, white, orange | 29 min | 11 g |
| `tux_clip_all_sizes` | S, M and L | black, white, orange | 1 h 08 min | 24 g |
| `tux_clip_desk` | desk version | black, white, orange | 36 min | 14 g |
| `coupon_flexure` | flexure coupon | any, no colour change | 16 min | 4 g |

\* PrusaSlicer 2.9.6 estimates (Prusament PETG, 0.20mm STRUCTURAL). The desk version is over the 30 minute target of the clips, because of the floe.

### Colour changes (M600)

Every clip prints black first, then the belly and eyes in white, then the beak and feet in orange. Each colour is a flat layer on top of the one before, so two colour changes are enough:

| Part | Z (print_z) | From | To | What changes colour |
|---|---|---|---|---|
| all clips and the desk version | 5.00 mm | black | white | belly, eyes (pupils stay black) |
| all clips and the desk version | 5.60 mm | white | orange | beak and feet |
| flexure coupon | — | — | — | no colour change |

The 3MF files already contain them. With the STL files, add them yourself: open the preview, move the vertical slider to the layer and click the **+**.

**One colour is fine too.** The belly, the eyes, the beak and the feet are raised by 0.6 mm each, and the pupils are holes, so a single-colour Tux still looks like Tux. Delete the colour changes in PrusaSlicer, or print the STL file.

### Designed for 0.2 mm layers and 0.45 mm lines

The model follows the slicer grid, so nothing gets rounded away:

- **Layers.** Lying on its back, every flat surface sits on a layer boundary: the black body is 4.8 mm (24 layers), the white and orange reliefs 0.6 mm (3 layers) each.
- **Colour boundaries** are flat layers too, at 4.8 and 5.4 mm. The M600 goes before the first layer of the new colour (Z = 5.00 and 5.60 mm). PrusaSlicer's G-code confirms both.
- **Lines.** The leaf and the comb teeth are exactly 2 lines wide (0.86 mm). Every slot, gap and hole is at least one line wide (0.5 mm), so nothing fuses during the print.
- **No islands.** Every layer rests on the layer below, and there are no overhangs at all.

`tests/test_layers.py` checks all of this for every part. If you change `LAYER` or `LINE_W` in `src/common/grid.py`, the tests show what no longer fits the grid.

`slicer.py` needs PrusaSlicer with the MK4 profiles installed. If `prusa-slicer` is not on your PATH, set `PRUSA_SLICER`, for example `PRUSA_SLICER="flatpak run com.prusa3d.PrusaSlicer"`. If the profiles are not installed, set `PRUSA_CONFIG` to a full PrusaSlicer config (`.ini`) for the same printer, print and filament profiles.

### Print the flexure coupon first (about 16 min)

Print `coupon_flexure.3mf` in one colour. It is a bar with three short flippers, each on a different leaf:

| Dots | Leaf | Opening | Grip on a 1 mm card |
|---|---|---|---|
| 1 | 2 lines (0.86 mm) | 5.0 mm | 0.31 N |
| 2 | 3 lines (1.26 mm) | 3.1 mm | 1.00 N |
| 3 | 4 lines (1.67 mm) | 2.1 mm | 2.32 N |

The coupon also tests your printer: the flippers are free only thanks to 0.5 mm gaps that run the full height of the part. If a flipper comes out stuck (PETG strings, or a squashed first layer), widen `SLOT_MIN` and `TOOTH_GAP` in `src/tux_clip/params.py` before you print the clips.

Squeeze each flipper and feel the difference. A thicker leaf grips harder but opens less, because every leaf stops at the same safe bend. The clips use 2 lines (1 dot). To change it, set `FLEX_LINES` in `src/tux_clip/params.py`: the model makes the leaf as long as it needs and opens as far as the leaf allows. The tests then tell you the new opening.


### Using it

1. Remove the print from the sheet. Nothing needs cleaning: there are no supports and no pieces to break free.
2. Hold Tux between your thumb and index finger, on the two shoulders (the tops of the flippers), and squeeze. Both flippers open.
3. Slide the edge of the paper, the card or the cable into the slot under a flipper and let go.

## Tux Vise

*Not started yet.*

## Requirements

- [uv](https://docs.astral.sh/uv/) and Python 3.14 (3.13 also works)
- `uv sync` installs build123d, bd_warehouse, trimesh and pillow

```sh
uv run pytest                           # printable parts, layer grid, colours, mechanics, 3MF files
uv run python -m tux_clip.model         # flexure numbers for every size
uv run python -m tux_clip.export        # STL files (out/stl) and 3MF plates (out/3mf)
uv run python -m tux_clip.slicer        # optional, needs PrusaSlicer: times + projects
uv run python -m tux_clip.render        # listing images in out/render (no OpenGL needed)
uv run python -m tux_clip.render --gif  # ...plus the GIFs
```

`export` exits with status 1 if a part has a problem. You can find every size and clearance in `src/tux_clip/params.py`.

## License

- Model and code: **CC BY-SA 4.0** (see `LICENSE`).
- Tux by Larry Ewing (lewing@isc.tamu.edu), made with GIMP.
