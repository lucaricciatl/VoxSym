"""
14 — Coupled mechanics, optics and induced magnetism
====================================================
A silicon block is heated on one side, hit by a laser beam, and placed
in an external magnetic field.  The new
``MechanicsOpticsMagnetism`` solver uses the material properties
that already existed on ``Material``:

* Mechanical: Young's modulus, Poisson ratio, density and thermal
  expansion → thermo-elastic stress waves and displacement.
* Optical: refractive index and absorption coefficient → Beer-Lambert
  attenuation along rays.
* Magnetic: magnetic susceptibility and permeability → induced
  magnetisation M = χ_m · H, with a thermal roll-off near the Curie
  temperature.

The block is fixed at the bottom (zero-displacement boundary) so a
thermal stress wave propagates upward.  A red laser enters from the
−z face and is absorbed most strongly in silicon.  A uniform B-field
along +x induces magnetisation in the silicon and any ferromagnetic
voxels.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import SILICON, IRON

vs = VoxSym()

GRID_X = 8
GRID_Y = 8
GRID_Z = 16
HALF_X = GRID_X // 2
HALF_Y = GRID_Y // 2
HALF_Z = GRID_Z // 2

# Build a silicon block with a small iron inclusion to show ferromagnetism
for x in range(-HALF_X, HALF_X):
    for y in range(-HALF_Y, HALF_Y):
        for z in range(-HALF_Z, HALF_Z):
            if x**2 + y**2 <= 2 and z == 0:
                mat = IRON
            else:
                mat = SILICON
            v = Voxel(x=float(x), y=float(y), z=float(z), size=1.0, color=mat.color)
            v.material = mat
            v.temperature = 300.0
            vs.add_voxel(v)

# Heat the top face to drive a downward thermal stress wave
for v in vs.get_voxels():
    if v.z == HALF_Z - 1:
        v.temperature = 500.0

# Optical source from −z toward +z
vs.add_optical_source(
    origin=(0.0, 0.0, -HALF_Z - 2.0),
    direction=(0.0, 0.0, 1.0),
    intensity=1.0,
)

# External magnetic field B = 0.5 T along +x
vs.set_external_magnetic_field((0.5, 0.0, 0.0))

vs.setup_gui()
vs.set_layer(VoxSym.LAYER_MATERIAL, True)

print(f"Coupled mechanics / optics / magnetism demo.")
print(f"Open http://{vs.server.host}:{vs.server.port}")
print("Heated top, laser from −z, B-field along +x.")


@vs.on_gui_update
def _update_display():
    m_min, m_max, m_mean = vs.magnetization_stats()
    print(
        f"Max stress: {vs.max_stress():.2e} Pa  |  "
        f"Absorbed power: {vs.total_absorbed_optical_power():.3f} a.u.  |  "
        f"|M|: {m_min:.2e} → {m_max:.2e} A/m"
    )


@vs.on_update
def _voxsym_step():
    if not vs.simulation_paused:
        # Coupled MOM step
        vs.step_mechanics_optics_magnetism(dt=1e-6)
        # Heat diffusion sub-steps
        for _ in range(10):
            vs.step_and_update(dt=1e-4)


vs.run_simulation()
