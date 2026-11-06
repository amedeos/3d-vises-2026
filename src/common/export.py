"""Export helpers shared by both models: part checks, STL files and 3MF plates.

- One STL per part, already in its print orientation.
- One 3MF per print job ("plate"): parts arranged on the MK4 bed, with names and colours.
  Plates with colour changes carry them as PrusaSlicer metadata, so the M600s are already
  set when you open the file in PrusaSlicer.
"""

import tempfile
import zipfile
from pathlib import Path

import trimesh
from build123d import Color, Mesher, Part, Pos, export_stl

BED = (250.0, 210.0, 220.0)  # Prusa MK4
BED_CENTRE = (BED[0] / 2, BED[1] / 2)  # PrusaSlicer arranges around the middle of the bed
STL_TOLERANCE = (0.01, 0.1)  # linear (mm), angular (rad)
COLOURS = {"black": "#1c1a1e", "orange": "#f07318", "white": "#ece8dc", "grey": "#4a494e",
           "blue": "#3a73b3"}
M600_ENTRY = "Metadata/Prusa_Slicer_custom_gcode_per_print_z.xml"
MAX_CHANGES = 3  # colour changes per plate

# A colour change is (print_z, new colour): the M600 comes before the layer at print_z.
Change = tuple[float, str]
PlateObjects = list[tuple[str, Part, str]]  # (object name, part on the bed, start colour)
Plates = dict[str, tuple[PlateObjects, list[Change]]]


def check(part: Part) -> list[str]:
    """Problems with the CAD solid itself (empty list = fine)."""
    problems = []
    bb = part.bounding_box()
    if not part.is_valid:
        problems.append("invalid solid")
    if abs(bb.min.Z) > 1e-3:
        problems.append(f"not on the bed (zmin={bb.min.Z:.3f})")
    if bb.size.X > BED[0] or bb.size.Y > BED[1] or bb.size.Z > BED[2]:
        problems.append(f"larger than the bed {bb.size}")
    if len(part.solids()) != 1:
        problems.append(f"{len(part.solids())} separate bodies")
    return problems


def write_stl(part: Part, path: Path) -> list[str]:
    """Write the STL and check the mesh that a slicer will actually load."""
    export_stl(part, path, tolerance=STL_TOLERANCE[0], angular_tolerance=STL_TOLERANCE[1])
    mesh = trimesh.load(path)
    return [] if mesh.is_watertight else ["mesh not watertight"]


def mesh_problems(part: Part) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        return write_stl(part, Path(tmp) / "part.stl")


def centred(part: Part, cx: float = BED_CENTRE[0], cy: float = BED_CENTRE[1]) -> Part:
    """Move a part (already lying on z=0) so the centre of its footprint is at (cx, cy)."""
    bb = part.bounding_box()
    return Pos(cx - (bb.min.X + bb.max.X) / 2, cy - (bb.min.Y + bb.max.Y) / 2, 0) * part


def on_bed(part: Part, x_min: float, y_min: float) -> Part:
    """Move a part (already lying on z=0) so its footprint starts at (x_min, y_min)."""
    bb = part.bounding_box()
    return Pos(x_min - bb.min.X, y_min - bb.min.Y, 0) * part


def row(parts: list[Part], gap: float = 8.0, y_centre: float = BED[1] / 2) -> list[Part]:
    """Lay parts out left to right, centred on the bed."""
    widths = [p.bounding_box().size.X for p in parts]
    x = (BED[0] - sum(widths) - gap * (len(parts) - 1)) / 2
    placed = []
    for part, w in zip(parts, widths):
        placed.append(on_bed(part, x, y_centre - part.bounding_box().size.Y / 2))
        x += w + gap
    return placed


def _named(part: Part, name: str, colour: str) -> Part:
    part = part.moved(Pos())  # a copy: the cached parts must not be changed
    part.label = name
    part.color = Color(COLOURS[colour])
    return part


def m600_metadata(changes: list[Change]) -> str:
    """PrusaSlicer's colour-change list, as stored inside its 3MF files."""
    # bed_idx: PrusaSlicer 2.9 keeps colour changes per bed (multiple beds); older versions
    # ignore the attribute
    codes = "".join(f'<code bed_idx="0" print_z="{z:.2f}" type="0" extruder="1" '
                    f'color="{COLOURS[colour]}" extra="" gcode="M600"/>\n'
                    for z, colour in sorted(changes))
    return ('<?xml version="1.0" encoding="utf-8"?>\n<custom_gcodes_per_print_z>\n'
            f'{codes}<mode bed_idx="0" value="SingleExtruder"/>\n'
            '</custom_gcodes_per_print_z>\n')


def write_3mf(path: Path, objects: PlateObjects, changes: list[Change] = ()):
    """Write a 3MF plate; the object colour is the starting filament."""
    if len(changes) > MAX_CHANGES:
        raise ValueError(f"{path.name}: {len(changes)} colour changes, at most {MAX_CHANGES}")
    mesher = Mesher()
    for name, part, colour in objects:
        mesher.add_shape(_named(part, name, colour), linear_deflection=STL_TOLERANCE[0],
                         angular_deflection=STL_TOLERANCE[1])
    mesher.write(str(path))
    if changes:
        with zipfile.ZipFile(path, "a", zipfile.ZIP_DEFLATED) as z:
            z.writestr(M600_ENTRY, m600_metadata(list(changes)))


def export_model(out: Path, model: str, parts: dict[str, Part], plates: Plates) -> dict:
    """Write every STL into out/stl/<model> and the plates into out/3mf/<model>.

    Returns {part name: [problems]}; an empty list means the part is fine.
    """
    stl_dir, mf_dir = out / "stl" / model, out / "3mf" / model
    stl_dir.mkdir(parents=True, exist_ok=True)
    mf_dir.mkdir(parents=True, exist_ok=True)
    report = {}
    for name, part in parts.items():
        problems = check(part) + write_stl(part, stl_dir / f"{name}.stl")
        report[name] = problems
        status = "OK" if not problems else "; ".join(problems)
        print(f"{name:36s} {part.volume / 1000:6.2f} cm3  {status}")
    for name, (objects, changes) in plates.items():
        write_3mf(mf_dir / f"{name}.3mf", objects, changes)
        note = ", ".join(f"Z {z:.2f} -> {c}" for z, c in changes)
        print(f"{name + '.3mf':36s} {len(objects)} object(s)  {'M600 at ' + note if note else ''}")
    return report
