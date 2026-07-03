"""
05 — Multi-material cube
=========================
Copper (top), glass (bottom), air (middle) — each with different
thermal properties.  Heat diffuses faster through copper.
Standard GUI: layer toggles, cross-section, opacity.
"""

import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import COPPER, GLASS, AIR

vs = VoxSym()

GRID = 10
HALF = GRID // 2
for x in range(-HALF, HALF):
    for y in range(-HALF, HALF):
        for z in range(-HALF, HALF):
            if z > 0:
                mat = COPPER
            elif z < -2:
                mat = GLASS
            else:
                mat = AIR

            v = Voxel(x=float(x), y=float(y), z=float(z), size=1, color=mat.color)
            v.material = mat
            v.temperature = 300.0
            vs.add_voxel(v)

for v in vs.get_voxels():
    if v.x**2 + v.y**2 + v.z**2 <= 9:
        v.temperature = 1000.0

for sign in (-1, 1):
    vs.add_fixed_temperature((0, 0, sign * 4), 1.5, 300)
    vs.add_fixed_temperature((sign * 4, 0, 0), 1.5, 300)
    vs.add_fixed_temperature((0, sign * 4, 0), 1.5, 300)

vs.setup_gui()
vs.set_layer(VoxSym.LAYER_MATERIAL, True)
vs.temp_range = (250.0, 700.0)

print("Multi-material demo.  Open http://localhost:8080")
print("Copper (top, brown) conducts faster than glass/air (bottom).")
print("Use Cross Section to slice through the material layers.")

sim_time = 0.0

@vs.on_update
def _voxsym_step():
    if not vs.simulation_paused:
        for _ in range(25):
            vs.step_simulation(dt=200.0)
            vs.update()
            sim_time += 200.0
vs.run_simulation()