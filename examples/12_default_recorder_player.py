"""
12 — Recorder + Player + Simulation Control
=============================================
Every ``VoxSym`` instance now records automatically.  Just run the
simulation as usual; frames are captured at every ``update()``.

The main GUI has two new folders:

**Simulation Control**

* **▶ Play** — resume stepping.
* **⏸ Pause** — pause stepping (rendering continues).
* **⏹ Stop** — exit the simulation loop and trigger autosave.

**Recording / Playback**

* **Load Simulation** — upload and replay a `.npz` or `.csv` recording
  directly in the main window.
* **💾 Autosave** — save both ``.npz`` and ``.csv`` to
  ``./results/<script_name>/DDMMYYYY.*``.
* **Save .npz / .csv** — export the current recording.

This example runs a small heat-diffusion simulation.  Open
http://localhost:8080, use the control buttons, then click **▶ Open
Player** at any time to inspect and replay the recorded history.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import COPPER

vs = VoxSym(port=8080)

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

vs.setup_gui()
vs.set_layer(VoxSym.LAYER_MATERIAL, True)
vs.temp_range = (250.0, 700.0)

print("Heat diffusion demo.  Open http://localhost:8080")
print("Use Simulation Control (Play / Pause / Stop) in the GUI.")
print("Click 'Load Simulation' in Recording / Playback to upload a recording.")
print("Loaded recordings replay in the same window.")

# Main loop: recorder captures every step_and_update automatically.

@vs.on_update
def _voxsym_step():
    if not vs.simulation_paused:
        for _ in range(25):
            vs.step_and_update(dt=200.0)

vs.run_simulation()