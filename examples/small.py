"""
Small test — ion migration under E-field in water.
Ions start on the z=0 plane and drift under a constant E-field.
dx = 10 µm, dt = 1e-5 s — CFL stable for both diffusion and migration.
"""

import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import WATER

GRID = 10
HALF = GRID // 2
size = 10**-5  # 10 µm voxels

vs = VoxSym()

for x in range(-HALF, HALF):
    for y in range(-HALF, HALF):
        for z in range(-HALF, HALF):
            voxel = Voxel(
                x=float(x) * size, y=float(y) * size, z=float(z) * size,
                size=size, color=WATER.color,
            )
            voxel.material = WATER
            voxel.temperature = 300.0
            voxel.opacity = 1.0
            if z == 0:
                voxel.ion_concentration = 100.0
            vs.add_voxel(voxel)

# Constant E-field along +Z — ions drift upward continuously
vs.add_uniform_electric(0.0, 0.0, 50000.0)

vs.setup_gui()
vs.set_layer(VoxSym.LAYER_ION_CONCENTRATION, True)
vs.set_layer(VoxSym.LAYER_ELECTRIC_FIELD, True)
vs.auto_camera()
vs.opacity = 0.3

print("Ion migration demo.  Open http://localhost:8080")
print("Ions on z=0 plane drift upward under E-field.")
print("Blue = low conc, yellow = high conc.")

sim_time = 0.0

@vs.on_update
def _voxsym_step():
    vs.apply_em_fields(t=sim_time)

    # dt=1e-5: diffusion CFL=0.1, migration CFL=0.0002 — both stable
    if not vs.simulation_paused:
        for _ in range(50):
            vs.step_and_update(dt=1e-4)
            sim_time += 1e-3
vs.run_simulation()