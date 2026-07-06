"""Minimal backend for E2E tests: copper voxels with temperature + E/B fields."""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import COPPER

vs = VoxSym(host="0.0.0.0", port=8080)

GRID = 8
HALF = GRID // 2
for x in range(-HALF, HALF):
    for y in range(-HALF, HALF):
        for z in range(-HALF, HALF):
            v = Voxel(x=float(x), y=float(y), z=float(z), size=1, color=COPPER.color)
            v.material = COPPER
            # Temperature gradient so the plasma heatmap is visible.
            v.temperature = 300.0 + 10.0 * (x + y + z)
            vs.add_voxel(v)

vs.add_uniform_electric(2.0, 0.0, 0.0)
vs.add_uniform_magnetic(0.0, 1.0, 0.0)

vs.disable_heat()
vs.set_time_step(0.05)
vs.setup_gui()

print("E2E backend ready at http://0.0.0.0:8080")

# Keep process alive and render frames in the background.
vs.play()
vs.run_simulation()
