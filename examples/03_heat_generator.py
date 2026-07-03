"""
03 — HeatGenerator API
======================
Demonstrates the HeatGenerator class: pulsing heat into specific
voxels, regions, planes, and lines.
Standard GUI: layer toggles, cross-section, opacity.
"""

import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import COPPER
from voxsym.physics.heat_generator import HeatGenerator

vs = VoxSym()

GRID = 10
HALF = GRID // 2
for x in range(-HALF, HALF):
    for y in range(-HALF, HALF):
        for z in range(-HALF, HALF):
            v = Voxel(x=float(x), y=float(y), z=float(z), size=1, color=COPPER.color)
            v.material = COPPER
            v.temperature = 300.0
            vs.add_voxel(v)

for sign in (-1, 1):
    vs.add_fixed_temperature((0, 0, sign * 4), 1.5, 300)
    vs.add_fixed_temperature((sign * 4, 0, 0), 1.5, 300)
    vs.add_fixed_temperature((0, sign * 4, 0), 1.5, 300)

gen = HeatGenerator(vs)

vs.setup_gui()
vs.set_layer(VoxSym.LAYER_MATERIAL, True)
vs.temp_range = (250.0, 700.0)

# ---- Heat Generator buttons ----
with vs.server.gui.add_folder("Heat Generator"):
    pulse_region_btn = vs.server.gui.add_button("Pulse centre +500 K")
    pulse_line_btn = vs.server.gui.add_button("Pulse diagonal line")
    pulse_plane_btn = vs.server.gui.add_button("Pulse z=0 plane")
    reset_btn = vs.server.gui.add_button("Reset all to 300 K")

@pulse_region_btn.on_click
def _(_):
    gen.pulse_region((0, 0, 0), radius=2.5, delta_T=500.0)
    print("Pulsed +500 K at centre")

@pulse_line_btn.on_click
def _(_):
    gen.pulse_line((-3, -3, -3), (3, 3, 3), radius=1.0, delta_T=400.0)
    print("Pulsed +400 K along diagonal")

@pulse_plane_btn.on_click
def _(_):
    gen.pulse_plane("z", 0.0, delta_T=300.0, thickness=1.5)
    print("Pulsed +300 K on z=0 plane")

@reset_btn.on_click
def _(_):
    gen.reset_all(300.0)
    print("Reset all to 300 K")

print("HeatGenerator demo.  Open http://localhost:8080")
print("Use Cross Section to see inside after pulsing heat.")

sim_time = 0.0

@vs.on_update
def _voxsym_step():
    if not vs.simulation_paused:
        for _ in range(25):
            vs.step_simulation(dt=200.0)
            vs.update()
            sim_time += 200.0
vs.run_simulation()