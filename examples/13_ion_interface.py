"""
13 — Ion interfacial adsorption & partitioning
==============================================
Water cube with a central adsorbing membrane layer.
Ions diffuse into the membrane and adsorb at the water–membrane
interface according to Langmuir kinetics, while the partition
coefficient sets the equilibrium bulk concentration ratio between
the two materials.

Standard GUI: layer toggles, cross-section, opacity.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import Material

WATER_FAST = Material(
    name="water_fast",
    conductivity=0.01,
    dielectric_constant=80.1,
    thermal_conductivity=0.6,
    specific_heat=4186.0,
    density=1000.0,
    ion_diffusivity=1e-5,
    ionic_valence=1,
    ion_conc_max=1000.0,
    partition_coeff=1.0,
    interface_capacity=0.0,
    adsorption_rate=0.0,
    desorption_rate=0.0,
    color=(60, 120, 220),
)

MEMBRANE = Material(
    name="membrane",
    conductivity=0.0,
    dielectric_constant=2.0,
    thermal_conductivity=0.1,
    specific_heat=1000.0,
    density=1000.0,
    ion_diffusivity=1e-5,
    ionic_valence=1,
    ion_conc_max=1000.0,
    partition_coeff=2.0,       # ions prefer the membrane 2:1 at equilibrium
    interface_capacity=1e-4,   # Γ_max [mol/m²]
    adsorption_rate=1e1,       # k_a [m³/(mol·s)]
    desorption_rate=1e-2,      # k_d [1/s]
    color=(200, 100, 100),
)

vs = VoxSym()

GRID = 10
HALF = GRID // 2
for x in range(-HALF, HALF):
    for y in range(-HALF, HALF):
        for z in range(-HALF, HALF):
            v = Voxel(x=float(x), y=float(y), z=float(z), size=1.0)
            if z == 0:
                v.material = MEMBRANE
                v.color = MEMBRANE.color
                v.ion_concentration = 0.0
            else:
                v.material = WATER_FAST
                v.color = WATER_FAST.color
                v.ion_concentration = 100.0
            vs.add_voxel(v)

vs.setup_gui()
vs.set_layer(VoxSym.LAYER_ION_CONCENTRATION, True)
vs.temp_range = (0.0, 120.0)

print("Ion interface demo. Open http://localhost:8080")
print("Membrane (red) adsorbs ions; water (blue) supplies them.")


@vs.on_update
def _voxsym_step():
    if not vs.simulation_paused:
        for _ in range(25):
            vs.step_and_update(dt=0.1)


vs.run_simulation()
