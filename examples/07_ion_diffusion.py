"""
07 — Ion diffusion under oscillating field
==========================================
MXene (bottom) / Electrolyte (top) stack with an AC electric field
driving Li⁺ ions into and out of the MXene layer via the
Nernst–Planck migration term.

Standard GUI: layer toggles, cross-section, opacity.
"""

import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import Material


def _fmt_time(t: float) -> str:
    if t >= 1.0:
        return f"{t:.3f} s"
    elif t >= 1e-3:
        return f"{t*1e3:.2f} ms"
    elif t >= 1e-6:
        return f"{t*1e6:.2f} µs"
    else:
        return f"{t*1e9:.2f} ns"

# Demo-friendly materials with higher diffusivities so ion pumping is visible
DEMO_MXENE = Material(
    name="mxene_demo",
    conductivity=2.4e5,
    thermal_conductivity=10.0,
    specific_heat=900.0,
    density=4500.0,
    ion_diffusivity=1e-6,        # boosted for visibility
    ionic_valence=1,
    ion_conc_max=15000.0,
    color=(80, 160, 180),
)

DEMO_ELECTROLYTE = Material(
    name="electrolyte_demo",
    conductivity=1.0,
    thermal_conductivity=0.6,
    specific_heat=4180.0,
    density=1100.0,
    ion_diffusivity=1e-5,        # boosted for visibility
    ionic_valence=1,
    ion_conc_max=1000.0,
    color=(100, 200, 100),
)


# ---------------------------------------------------------------------------
# Build MXene / Electrolyte stack
# ---------------------------------------------------------------------------
vs = VoxSym()

GRID = 10
HALF = GRID // 2
for x in range(-HALF, HALF):
    for y in range(-HALF, HALF):
        for z in range(-HALF, HALF):
            if z >= 0:
                mat = DEMO_ELECTROLYTE
            else:
                mat = DEMO_MXENE

            v = Voxel(x=float(x), y=float(y), z=float(z), size=1, color=mat.color)
            v.material = mat
            v.ion_concentration = 0.0
            vs.add_voxel(v)

# Initial ion concentration: high in electrolyte, zero in MXene
vs.set_region_concentration((0.0, 0.0, 2.0), radius=3.0, concentration=500.0)

# ---------------------------------------------------------------------------
# Oscillating electric field along Z (drives ions vertically)
# ---------------------------------------------------------------------------
vs.add_oscillating_electric(0.0, 0.0, 50.0, frequency=0.2, phase=0.0)

# ---------------------------------------------------------------------------
# Simulation parameters
# ---------------------------------------------------------------------------
vs.set_time_step(50.0)          # 50 s per sub-step
vs.set_steps_per_frame(50)     # 50 sub-steps per rendered frame

# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
vs.setup_gui()

sim_time_gui = vs.server.gui.add_markdown("Simulation time: **0.0 s**")
conc_stats_gui = vs.server.gui.add_markdown("Ion conc: **---**")

# Start with ion concentration layer active
vs.set_layer(VoxSym.LAYER_ION_CONCENTRATION, True)

vs.field_subsample = 3
vs.field_arrow_scale = 0.6

print("Ion diffusion under oscillating field.  Open http://localhost:8080")
print("Blue = low ion conc, yellow = high ion conc.")
print("Watch ions pump into the MXene (bottom) under the AC field.")


@vs.on_gui_update
def _update_display():
    sim_time_gui.content = f"Simulation time: **{_fmt_time(vs.elapsed_time)}**"
    c_min, c_max, c_mean = vs.concentration_stats()
    conc_stats_gui.content = f"Ion conc: **{c_min:.0f} \u2192 {c_max:.0f}** mol/m\u00b3"


vs.run_simulation()