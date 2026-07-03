"""
01 — Basic voxel grid
=====================
Creates a 10×10×10 copper cube and renders it with Viser.
Standard GUI: layer toggles, cross-section, opacity.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import COPPER

vs = VoxSym()

GRID = 10
HALF = GRID // 2
for x in range(-HALF, HALF):
    for y in range(-HALF, HALF):
        for z in range(-HALF, HALF):
            v = Voxel(x=float(x), y=float(y), z=float(z), size=1, color=COPPER.color)
            v.material = COPPER
            vs.add_voxel(v)

vs.setup_gui()

print(f"Rendered {len(vs.get_voxels())} copper voxels.  Open http://localhost:8080")
print("Use Cross Section dropdown + slider to slice through the cube.")


@vs.on_update
def _voxsym_step():
    pass

vs.run_simulation()