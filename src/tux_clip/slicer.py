"""Optional: slice the Tux Clip plates with the PrusaSlicer CLI and write projects.

Run `python -m tux_clip.export` first. See `common.slicer` for what it checks.
Set PRUSA_SLICER if `prusa-slicer` is not on the PATH. If the Prusa MK4 profiles are not
installed, set PRUSA_CONFIG to a full PrusaSlicer config (see AGENTS.md).
"""

import sys
from pathlib import Path

from common.slicer import main

from .export import MODEL, PLANNED_M600

if __name__ == "__main__":
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/3mf") / MODEL
    sys.exit(main(folder, PLANNED_M600, MODEL))
