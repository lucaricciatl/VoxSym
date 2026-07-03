import viser
import time
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.visualization.renderer import Renderer
from voxsym.physics.electric_field import ElectromagneticSolver
from voxsym.visualization.visualizer import Visualizer, Layer
from voxsym.material import COPPER


# ---------------------------------------------------------------------------
# Build voxel grid — all copper
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Heat diffusion
# ---------------------------------------------------------------------------
for v in vs.get_voxels():
    if v.x**2 + v.y**2 + v.z**2 <= 9:
        v.temperature = 1000.0

vs.add_heat_source((0.0, 0.0, 0.0), radius=2.0, power=2e5)

for sign in (-1, 1):
    vs.add_fixed_temperature((0, 0, sign * 5), 1.5, 300)
    vs.add_fixed_temperature((sign * 5, 0, 0), 1.5, 300)
    vs.add_fixed_temperature((0, sign * 5, 0), 1.5, 300)

# ---------------------------------------------------------------------------
# Electromagnetic fields
# ---------------------------------------------------------------------------
em = ElectromagneticSolver()
em.add_oscillating_electric(0.0, 0.0, 1.5, frequency=0.5, phase=0.0)
em.add_uniform_magnetic(0.0, 1.0, 0.0)

# ---------------------------------------------------------------------------
# Viser server + GUI
# ---------------------------------------------------------------------------
server = viser.ViserServer()

sim_time_gui = server.gui.add_markdown("Simulation time: **0.0 s**")
temp_range_gui = server.gui.add_markdown("T range: **---**")

renderer = Renderer(vs)
viz = Visualizer(server, vs, renderer)
viz.auto_camera()
viz.set_layer(Layer.MATERIAL, True)
viz.temp_range = (250.0, 700.0)
viz.field_subsample = 3
viz.field_arrow_scale = 0.6

# ---- Standard GUI: layers ----
with server.gui.add_folder("Visualization Layers"):
    ef_btn = server.gui.add_button("Toggle E-field")
    bf_btn = server.gui.add_button("Toggle B-field")
    temp_btn = server.gui.add_button("Toggle Temperature")
    mat_btn = server.gui.add_button("Toggle Material")
    base_btn = server.gui.add_button("Base colours")

# ---- Standard GUI: cross-section ----
with server.gui.add_folder("Cross Section"):
    cs_axis_dd = server.gui.add_dropdown(
        "Axis", options=("off", "x", "y", "z"), initial_value="off"
    )
    cs_pos_slider = server.gui.add_slider(
        "Position", min=-HALF, max=HALF - 1, step=1, initial_value=0
    )

# ---- Standard GUI: opacity ----
opacity_slider = server.gui.add_slider(
    "Global opacity", min=0.0, max=1.0, step=0.01, initial_value=1.0
)

# ---- Callbacks (buttons only — sliders/dropdowns read in loop) ----
@ef_btn.on_click
def _(_):
    viz.toggle_layer(Layer.ELECTRIC_FIELD)

@bf_btn.on_click
def _(_):
    viz.toggle_layer(Layer.MAGNETIC_FIELD)

@temp_btn.on_click
def _(_):
    viz.toggle_layer(Layer.TEMPERATURE)

@mat_btn.on_click
def _(_):
    viz.toggle_layer(Layer.MATERIAL)

@base_btn.on_click
def _(_):
    for name in list(viz._active):
        if name != Layer.VOXEL_COLOR:
            viz.set_layer(name, False)
    viz.set_layer(Layer.VOXEL_COLOR, True)

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
print("Viser server running. Open http://localhost:8080")
print("Use Cross Section dropdown + slider to slice through the cube.")

sim_time = 0.0
while True:
    # ---- Read cross-section controls every frame (more reliable than callbacks) ----
    axis_val = cs_axis_dd.value
    viz.cross_section_axis = None if axis_val == "off" else axis_val
    viz.cross_section_pos = cs_pos_slider.value

    for _ in range(25):
        vs.step_simulation(dt=200.0)
        vs.update()
        sim_time += 200.0
    sim_time_gui.content = f"Simulation time: **{sim_time:.0f} s**"

    t_min, t_max, t_mean = vs.temperature_stats()
    temp_range_gui.content = f"T range: **{t_min:.0f} K → {t_max:.0f} K**"

    em.apply_to_voxels(vs.get_voxels(), t=sim_time)

    # Ion diffusion + migration  (dt=0.005 s, stable for D=1e-9, dx=10 µm)
    for _ in range(50):
        vs.step_simulation(dt=0.005)
        vs.update()
        sim_time += 0.005

    viz.render()
    if renderer.handle is not None:
        renderer.handle.opacity = opacity_slider.value

    time.sleep(0.05)
