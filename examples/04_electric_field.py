"""
04 — Electric & magnetic fields
===============================
Shows how to set up electric and magnetic fields and visualise
them as arrow overlays.
Standard GUI: layer toggles, cross-section, opacity.
"""

import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import COPPER

vs = VoxSym()

GRID = 8
HALF = GRID // 2
for x in range(-HALF, HALF):
    for y in range(-HALF, HALF):
        for z in range(-HALF, HALF):
            v = Voxel(x=float(x), y=float(y), z=float(z), size=1, color=COPPER.color)
            v.material = COPPER
            vs.add_voxel(v)

vs.add_uniform_electric(2.0, 0.0, 0.0)
vs.add_oscillating_electric(0.0, 0.0, 1.5, frequency=0.5, phase=0.0)
vs.add_uniform_magnetic(0.0, 1.0, 0.0)

# ---------------------------------------------------------------------------
# Simulation parameters
# ---------------------------------------------------------------------------
vs.set_time_step(0.05)         # 50 ms per sub-step

vs.setup_gui()
vs.set_layer(VoxSym.LAYER_ELECTRIC_FIELD, True)
vs.set_layer(VoxSym.LAYER_MAGNETIC_FIELD, True)
vs.field_subsample = 3
vs.field_arrow_scale = 0.4

print("Field visualisation demo.  Open http://localhost:8080")
print("Red arrows = E-field, blue arrows = B-field.")

vs.run_simulation()