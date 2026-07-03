"""
10 — Record, export to CSV, and playback in the main window
=============================================================
Run a small heat-diffusion simulation, automatically save the full
voxel history to the default results folder, then load and replay it
in the same VoxSym window.

The default save location is::

    ./results/10_record_and_play/DDMMYYYY.npz
    ./results/10_record_and_play/DDMMYYYY.csv

Use the **Recording / Playback** → **Load Simulation** button to upload
any other `.npz` or `.csv` recording.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import COPPER

# Record headlessly on a non-default port; the main playback window uses 8080.
vs = VoxSym(port=8081)

GRID = 8
HALF = GRID // 2
for x in range(-HALF, HALF):
    for y in range(-HALF, HALF):
        for z in range(-HALF, HALF):
            v = Voxel(x=float(x), y=float(y), z=float(z), size=1, color=COPPER.color)
            v.material = COPPER
            v.temperature = 300.0
            vs.add_voxel(v)

# Hot centre
for v in vs.get_voxels():
    if v.x**2 + v.y**2 + v.z**2 <= 4:
        v.temperature = 1000.0

sim_time = 0.0
dt = 100.0
steps = 50
for _ in range(steps):
    vs.step_simulation(dt)
    vs.update()
    sim_time += dt
    vs.record(sim_time)

# Auto-save to ./results/10_record_and_play/DDMMYYYY.{npz,csv}
npz_path, csv_path = vs.autosave()
print(f"Saved {npz_path}")
print(f"Saved {csv_path}")

# Switch to the main playback window on port 8080.
vs2 = VoxSym(port=8080, enable_recorder=False)
vs2.load_simulation(npz_path)
vs2.setup_gui()
vs2.set_layer(VoxSym.LAYER_MATERIAL, True)
vs2.temp_range = (250.0, 700.0)

print("\nPlayback open at http://localhost:8080")
print("Controls: ▶ Play / ⏸ Pause / ⏹ Stop / Timeline / Speed")
print("Click 'Load Simulation' to upload another .npz or .csv file.")

vs2.run_simulation()
