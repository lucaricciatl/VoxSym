"""
09 — MXene Memristor
====================
Graphene | H₂SO₄ electrolyte | Ti₃C₂ MXene horizontal stack.
H⁺ ions in the electrolyte migrate into/out of the MXene under
an oscillating electric field along X, simulating memristive switching.

Geometry (10 µm voxels):
  [Gr] [Gr] [H₂SO₄] [H₂SO₄] [H₂SO₄] [MXene] [MXene] [MXene] [MXene] [MXene]
    2×10×10          3×10×10                    5×10×10
All layers sit flat on the grid floor (z = 0..GRID_Z-1).
"""

import time
import sys
import os
import numpy as np

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
    dielectric_constant=12.0,      # graphite-like
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
    dielectric_constant=80.0,    # water-like
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
    dielectric_constant=15.0,      # MXene-like
    thermal_conductivity=10.0,     # W/(m·K)
    specific_heat=900.0,           # J/(kg·K)
    density=4500.0,                # kg/m³
    ion_diffusivity=5e-10,         # m²/s  (intercalated H⁺)
    ionic_valence=1,
    ion_conc_max=800.0,          # mol/m³
    partition_coeff=2.0,           # H+ preferentially partitions into MXene
    color=(80, 160, 180),          # teal
)

GOLD = Material(
    name="gold",
    conductivity=4.1e7,            # S/m
    dielectric_constant=1e6,       # metal: effectively infinite permittivity
    thermal_conductivity=320.0,    # W/(m·K)
    specific_heat=130.0,           # J/(kg·K)
    density=19300.0,               # kg/m³
    ion_diffusivity=1e-15,         # impermeable to ions
    ionic_valence=0,
    ion_conc_max=0.0,
    color=(255, 215, 0),           # gold
)


GRID_X = 10
GRID_Y = 10
GRID_Z = 10


def build_memristor(backend="webgl", port=9000, host="0.0.0.0"):
    """Build the horizontal memristor geometry and return a VoxSym instance."""
    vs = VoxSym(backend=backend, port=port, host=host)

    HALF_Y = GRID_Y // 2
    size = 1e-5  # 10 µm

    # Stack along X, sitting on the base plane z = 0 .. (GRID_Z-1)*size
    for x_start, x_end, mat in [
        (0, 2, GRAPHENE),
        (2, 5, H2SO4_ELECTROLYTE),
        (5, GRID_X, TI3C2_MXENE),
    ]:
        for x in range(x_start, x_end):
            for y in range(-HALF_Y, HALF_Y):
                for z in range(0, GRID_Z):
                    v = Voxel(
                        x=float(x) * size,
                        y=float(y) * size,
                        z=float(z) * size,
                        size=size,
                        color=mat.color,
                    )
                    v.material = mat
                    v.temperature = 300.0
                    if mat is H2SO4_ELECTROLYTE:
                        v.ion_concentration = 300.0  # 1M
                    if mat is TI3C2_MXENE:
                        v.ion_concentration = 0.0
                    vs.add_voxel(v)

    # Bottom gold electrodes under the left (graphene) and right (MXene) ends
    for x in range(-2, 2):
        for y in range(-HALF_Y, HALF_Y):
            for z in range(-1, 0):
                v = Voxel(
                    x=float(x) * size,
                    y=float(y) * size,
                    z=float(z) * size,
                    size=size,
                    color=GOLD.color,
                )
                v.material = GOLD
                v.temperature = 300.0
                vs.add_voxel(v)

    for x in range(GRID_X, GRID_X + 4):
        for y in range(-HALF_Y, HALF_Y):
            for z in range(-1, 0):
                v = Voxel(
                    x=float(x) * size,
                    y=float(y) * size,
                    z=float(z) * size,
                    size=size,
                    color=GOLD.color,
                )
                v.material = GOLD
                v.temperature = 300.0
                vs.add_voxel(v)

    # Electrolyte bridge under the gap so the device sits on a continuous base
    for x in range(2, GRID_X):
        for y in range(-HALF_Y, HALF_Y):
            for z in range(-1, 0):
                v = Voxel(
                    x=float(x) * size,
                    y=float(y) * size,
                    z=float(z) * size,
                    size=size,
                    color=H2SO4_ELECTROLYTE.color,
                )
                v.material = H2SO4_ELECTROLYTE
                v.temperature = 300.0
                v.ion_concentration = 300.0  # 1M
                vs.add_voxel(v)

    return vs


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    vs = build_memristor()
    size = 1e-5  # 10 µm voxel size

    # Applied voltage waveform on the left (graphene) and right (MXene)
    # electrodes.  The gold blocks are held at Dirichlet potentials and drive
    # H+ migration/diffusion across the electrolyte/MXene stack.
    vs.set_voltage_boundary(
        x_range=(-2 * size, 1 * size),
        y_range=None,
        z_range=(-1 * size, GRID_Z * size),
        value=lambda t: 1.0 * np.sin(2.0 * np.pi * 1.0 * t),
    )
    vs.set_voltage_boundary(
        x_range=((GRID_X - 1) * size, (GRID_X + 2) * size),
        y_range=None,
        z_range=(-1 * size, GRID_Z * size),
        value=0.0,
    )

    # Small background magnetic field (Tesla) for visual B-field overlay.
    vs.add_uniform_magnetic(0.0, 0.0, 0.05)

    vs.disable_heat()             # isothermal memristor: avoid heat CFL bottleneck
    vs.set_time_step(1e-4)        # 100 µs per rendered frame; internally sub-stepped to CFL cap
    vs.set_steps_per_frame(1)     # one step_and_update() call per rendered frame
    vs.set_enable_poisson(True)   # self-consistent E from ρ/ε and boundary voltages
    vs.set_poisson_max_iter(200)  # fast enough per frame for this grid size

    vs.setup_gui()
    vs.set_layer(VoxSym.LAYER_ELECTRIC_FIELD, True)
    vs.set_layer(VoxSym.LAYER_CURRENT, True)
    vs.auto_camera()
    vs.opacity = 0.4

    print(f"MXene Memristor demo.  Open http://{vs.server.host}:{vs.server.port}")
    print("Graphene (dark) | H₂SO₄ (green) | Ti₃C₂ MXene (teal) | Gold (yellow)")
    print("H⁺ ions oscillate across the flat stack under AC field.")

    @vs.on_gui_update
    def _update_display():
        stats = vs.concentration_stats()
        print(f"Simulation time: {_fmt_time(vs.elapsed_time)}  |  Ion conc: {stats[0]:.0f} → {stats[1]:.0f} mol/m³")

    vs.run_simulation(sleep=0.02)
