# Tux Clip and Tux Vise 🐧

Two entries for the Printables contest **[Designer Challenge: Vises](https://www.printables.com/contest/534-vises)**.

Both models are Tux, the Linux penguin. They print without supports, need no screws or springs, and get their colours from filament changes (M600) on a single-extruder printer.

The models are fully parametric. They are written in Python with [build123d](https://github.com/gumyr/build123d).

## Tux Clip

*Work in progress.*

### How it works

### Printing

### Colour changes (M600)

### Print the flexure coupon first

## Tux Vise

*Not started yet.*

## Requirements

- [uv](https://docs.astral.sh/uv/) and Python 3.14 (3.13 also works)
- `uv sync` installs build123d, bd_warehouse, trimesh and pillow

```sh
uv run pytest                          # printable parts, layer grid, colours, mechanics
uv run python -m tux_clip.export       # STL files and 3MF plates in out/
uv run python -m tux_clip.slicer       # optional, needs PrusaSlicer: times + projects
uv run python -m tux_clip.render --gif # listing images and GIFs in out/render
```

## License

- Model and code: **CC BY-SA 4.0** (see `LICENSE`).
- Tux by Larry Ewing (lewing@isc.tamu.edu), made with GIMP.
