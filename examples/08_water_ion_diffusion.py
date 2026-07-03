"""
08 — Ion oscillation under AC field in water (µ-scale)
========================================================
30×30×30 water cube, each voxel = 10 µm.
Ions start at the centre and oscillate left↔right under an AC
electric field via the Nernst–Planck migration term, while
Fickian diffusion slowly spreads the cloud.

Standard GUI: layer toggles, cross-section, opacity.
"""

import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import WATER


def _fmt_time(t: float) -> str:
    if t >= 1.0:
        return f"{t:.3f} s"
    elif t >= 1e-3:
        return f"{t*1e3:.2f} ms"
    elif t >= 1e-6:
        return f"{t*1e6:.2f} µs"
    else:
        return f"{t*1e9:.2f} ns"


# ---------------------------------------------------------------------------
# 30×30×30 water cube — each voxel = 10 µm
# ---------------------------------------------------------------------------
GRID = 30
HALF = GRID // 2
VOXEL_SIZE = 1          # 10 µm  (render scale auto-infers 1/1 = 1.0)

vs = VoxSym()

for x in range(-HALF, HALF):
    for y in range(-HALF, HALF):
        for z in range(-HALF, HALF):
            v = Voxel(
                x=float(x) * VOXEL_SIZE,
                y=float(y) * VOXEL_SIZE,
                z=float(z) * VOXEL_SIZE,
                size=10**-6,  # 10 µm
                color=WATER.color,
            )
            v.material = WATER
            v.ion_concentration = 0.0
            vs.add_voxel(v)

# ---------------------------------------------------------------------------
# Initial ion blob at the centre
# ---------------------------------------------------------------------------
R = 5  # radius in voxels
for v in vs.get_voxels():
    dx = v.x - 0.0
    dy = v.y - 0.0
    dz = v.z - 0.0
    if dx * dx + dy * dy + dz * dz <= (R * 10**-6) ** 2:
        v.ion_concentration = 100.0   # mol/m³

# ---------------------------------------------------------------------------
# Oscillating electric field along X
# ---------------------------------------------------------------------------
vs.add_oscillating_electric(5000.0, 0.0, 0.0, frequency=0.5, phase=0.0)

# ---------------------------------------------------------------------------
# Simulation parameters
# ---------------------------------------------------------------------------
vs.set_time_step(0.005)        # 5 ms per sub-step
vs.set_steps_per_frame(50)    # 50 sub-steps per rendered frame

# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
vs.setup_gui()

sim_time_gui = vs.server.gui.add_markdown("Simulation time: **0.000 s**")
conc_stats_gui = vs.server.gui.add_markdown("Ion conc: **---**")

# Auto-position the camera
vs.auto_camera()

# Start with ion concentration layer active
vs.set_layer(VoxSym.LAYER_ION_CONCENTRATION, True)

vs.field_subsample = 6
vs.field_arrow_scale = 0.3

print(f"30×30×30 water cube, 10 µm voxels.  Open http://localhost:8080")
print("Ion blob at centre oscillates left↔right under AC field (0.5 Hz).")
print("Blue = low conc, yellow = high conc.")


@vs.on_gui_update
def _update_display():
    sim_time_gui.content = f"Simulation time: **{_fmt_time(vs.elapsed_time)}**"
    c_min, c_max, c_mean = vs.concentration_stats()
    conc_stats_gui.content = f"Ion conc: **{c_min:.1f} → {c_max:.1f}** mol/m³"


vs.run_simulation()