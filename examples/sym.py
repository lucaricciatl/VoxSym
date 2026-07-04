"""
sym — WebGL/Three.js viewer demo
=================================
A simple copper cube rendered through the VoxSym WebGL backend.
Use the browser sidebar to toggle layers, slice and control playback.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import COPPER

vs = VoxSym()

GRID = 12
HALF = GRID // 2
for x in range(-HALF, HALF):
    for y in range(-HALF, HALF):
        for z in range(-HALF, HALF):
            voxel = Voxel(
                x=float(x), y=float(y), z=float(z),
                size=1, color=COPPER.color,
            )
            voxel.material = COPPER
            voxel.temperature = 300.0
            voxel.opacity = 1.0
            vs.add_voxel(voxel)

# Heat a central region
for v in vs.get_voxels():
    if v.x**2 + v.y**2 + v.z**2 <= 9:
        v.temperature = 1000.0

vs.add_heat_source((0.0, 0.0, 0.0), radius=2.0, power=2e5)
for sign in (-1, 1):
    vs.add_fixed_temperature((0, 0, sign * 5), 1.5, 300)
    vs.add_fixed_temperature((sign * 5, 0, 0), 1.5, 300)
    vs.add_fixed_temperature((0, sign * 5, 0), 1.5, 300)

vs.add_uniform_electric(0.0, 0.0, 1.5)
vs.add_uniform_magnetic(0.0, 1.0, 0.0)

vs.setup_gui()
vs.set_layer(VoxSym.LAYER_MATERIAL, True)
vs.set_layer(VoxSym.LAYER_ELECTRIC_FIELD, True)
vs.auto_camera()
vs.temp_range = (250.0, 700.0)
vs.field_subsample = 3
vs.field_arrow_scale = 0.6

print(f"WebGL/Three.js viewer demo.  Open http://{vs.server.host}:{vs.server.port}")
print("Use the browser sidebar to toggle layers and slice the cube.")


@vs.on_update
def _voxsym_step():
    for _ in range(25):
        vs.step_and_update(dt=200.0)
    vs.apply_em_fields(t=vs.elapsed_time)


vs.run_simulation()
