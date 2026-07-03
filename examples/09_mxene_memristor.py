"""
09 — MXene Memristor
====================
Graphene | H₂SO₄ electrolyte | Ti₃C₂ MXene stack.
H⁺ ions in the electrolyte migrate into/out of the MXene under
an oscillating electric field along X, simulating memristive switching.

Geometry (10 µm voxels):
  [Gr] [Gr] [H₂SO₄] [H₂SO₄] [MXene] [MXene] [MXene] [MXene] [MXene]
    2×10×10      2×10×10                5×10×10
"""

import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import Material


def _fmt_time(t: float) -> str:
    """Format time with auto-scaled units."""
    if t >= 1.0:
        return f"{t:.3f} s"
    elif t >= 1e-3:
        return f"{t*1e3:.2f} ms"
    elif t >= 1e-6:
        return f"{t*1e6:.2f} µs"
    else:
        return f"{t*1e9:.2f} ns"

# ---------------------------------------------------------------------------
# Materials (literature values)
# ---------------------------------------------------------------------------

GRAPHENE = Material(
    name="graphene",
    conductivity=1.0e6,            # S/m  (highly conductive)
    thermal_conductivity=2000.0,    # W/(m·K)
    specific_heat=700.0,           # J/(kg·K)
    density=2260.0,                # kg/m³
    ion_diffusivity=1e-12,           # impermeable to ions
    ionic_valence=0,
    ion_conc_max=0.0,
    color=(60, 60, 60),            # dark gray
)

H2SO4_ELECTROLYTE = Material(
    name="h2so4_1M",
    conductivity=40.0,             # S/m  (1M H₂SO₄)
    thermal_conductivity=0.5,      # W/(m·K)
    specific_heat=3500.0,          # J/(kg·K)
    density=1200.0,                # kg/m³
    ion_diffusivity=1e-9,          # m²/s  (H⁺ in water)
    ionic_valence=1,
    ion_conc_max=1000.0,           # mol/m³  (1M)
    color=(150, 220, 150),         # light green
)

TI3C2_MXENE = Material(
    name="ti3c2_mxene",
    conductivity=2.4e5,            # S/m
    thermal_conductivity=10.0,     # W/(m·K)
    specific_heat=900.0,           # J/(kg·K)
    density=4500.0,                # kg/m³
    ion_diffusivity=5e-10,         # m²/s  (intercalated H⁺)
    ionic_valence=1,
    ion_conc_max=800.0,          # mol/m³
    color=(80, 160, 180),          # teal
)

GOLD = Material(
    name="gold",
    conductivity=4.1e7,            # S/m
    thermal_conductivity=320.0,    # W/(m·K)
    specific_heat=130.0,           # J/(kg·K)
    density=19300.0,               # kg/m³
    ion_diffusivity=1e-15,         # impermeable to ions
    ionic_valence=0,
    ion_conc_max=0.0,
    color=(255, 215, 0),           # gold
)
# ---------------------------------------------------------------------------
# Build the memristor stack
# ---------------------------------------------------------------------------
vs = VoxSym()

GRID_Y = 10
GRID_Z = 10
HALF_Y = GRID_Y // 2
HALF_Z = GRID_Z // 2
size = 1e-5  # 10 µm

# X layout: graphene (0-1), H₂SO₄ (2-6), MXene (7-11)
for xi, (x_start, x_end, mat) in enumerate([
    (0, 2, GRAPHENE),
    (2, 7, H2SO4_ELECTROLYTE),
    (7, 12, TI3C2_MXENE),
]):
    for x in range(x_start, x_end):
        for y in range(-HALF_Y, HALF_Y):
            for z in range(-HALF_Z, HALF_Z-4):
                v = Voxel(
                    x=float(x) * size,
                    y=float(y) * size,
                    z=float(z) * size,
                    size=size,
                    color=mat.color,
                )
                v.material = mat
                v.temperature = 300.0
                # H⁺ ions start in the electrolyte
                if mat is H2SO4_ELECTROLYTE:
                    v.ion_concentration = 300.0  # 1M
                if mat is TI3C2_MXENE:
                    v.ion_concentration = 0.0  # start empty
                vs.add_voxel(v)

# Add gold electrodes on the bottom of the stack under mxene and graphene
for x in range(-5, 1):
    for y in range(-HALF_Y, HALF_Y):
        for z in range(-HALF_Z, -HALF_Z+1):
            v = Voxel(
                x=float(x) * size,
                y=float(y) * size,
                z=float(z) * size - size,  # below the stack
                size=size,
                color=GOLD.color,
            )
            v.material = GOLD
            v.temperature = 300.0
            vs.add_voxel(v)
for x in range(8, 12+5):
    for y in range(-HALF_Y, HALF_Y):
        for z in range(-HALF_Z, -HALF_Z+1):
            v = Voxel(
                x=float(x) * size,
                y=float(y) * size,
                z=float(z) * size - size,  # below the stack
                size=size,
                color=GOLD.color,
            )
            v.material = GOLD
            v.temperature = 300.0
            vs.add_voxel(v)
#add electrolyte in the middle of the gold
for x in range(1, 8):
    for y in range(-HALF_Y, HALF_Y):
        for z in range(-HALF_Z, -HALF_Z+1):
            v = Voxel(
                x=float(x) * size,
                y=float(y) * size,
                z=float(z) * size - size,  # below the stack
                size=size,
                color=H2SO4_ELECTROLYTE.color,
            )
            v.material = H2SO4_ELECTROLYTE
            v.temperature = 300.0
            v.ion_concentration = 300.0  # 1M
            vs.add_voxel(v)
# ---------------------------------------------------------------------------
# Oscillating E-field along X drives ions between H₂SO₄ ↔ MXene
# Period (200 µs) is twice the rendered frame duration (100 µs) so the
# field/current arrows visibly flip direction between frames.
# ---------------------------------------------------------------------------
vs.add_oscillating_electric(1e5, 0.0, 0.0, frequency=1, phase=0.0)

# ---------------------------------------------------------------------------
# Simulation parameters
# ---------------------------------------------------------------------------
vs.set_time_step(1e-6)        # 1 µs per sub-step
vs.set_steps_per_frame(100)   # 100 sub-steps per rendered frame

# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
sim_time_gui = vs.server.gui.add_markdown("Simulation time: **0.000 s**")
conc_stats_gui = vs.server.gui.add_markdown("Ion conc: **---**")

vs.setup_gui()
vs.set_layer(VoxSym.LAYER_ION_CONCENTRATION, True)
vs.set_layer(VoxSym.LAYER_CURRENT, True)
vs.auto_camera()
vs.opacity = 0.4

print("MXene Memristor demo.  Open http://localhost:8080")
print("Graphene (dark) | H₂SO₄ (green) | Ti₃C₂ MXene (teal)")
print("H⁺ ions oscillate between electrolyte and MXene under AC field.")


@vs.on_gui_update
def _update_display():
    sim_time_gui.content = f"Simulation time: **{_fmt_time(vs.elapsed_time)}**"
    c_min, c_max, c_mean = vs.concentration_stats()
    conc_stats_gui.content = f"Ion conc: **{c_min:.0f} → {c_max:.0f}** mol/m³"
    

vs.run_simulation()