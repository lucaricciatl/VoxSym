"""
06 — Visualizer layers
======================
Demonstrates all visualisation layers: base colours, temperature,
material, electric field, and magnetic field.
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
            v.temperature = 300.0
            vs.add_voxel(v)

for v in vs.get_voxels():
    if v.x**2 + v.y**2 + v.z**2 <= 4:
        v.temperature = 800.0

for sign in (-1, 1):
    vs.add_fixed_temperature((0, 0, sign * 3), 1.5, 300)
    vs.add_fixed_temperature((sign * 3, 0, 0), 1.5, 300)
    vs.add_fixed_temperature((0, sign * 3, 0), 1.5, 300)

vs.add_uniform_electric(2.0, 0.0, 0.0)
vs.add_uniform_magnetic(0.0, 1.0, 0.0)

vs.setup_gui()
vs.set_layer(VoxSym.LAYER_MATERIAL, True)
vs.temp_range = (250.0, 700.0)
vs.field_subsample = 2

print("Layer demo.  Open http://localhost:8080")
print("Toggle layers and use Cross Section to slice through the cube.")

sim_time = 0.0

@vs.on_update
def _voxsym_step():
    if not vs.simulation_paused:
        for _ in range(25):
            vs.step_simulation(dt=200.0)
            vs.update()
            sim_time += 200.0

    vs.apply_em_fields(t=sim_time * 0.001)
vs.run_simulation()