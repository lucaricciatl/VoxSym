"""Test two-species Nernst-Planck + electroneutrality constraint."""

import numpy as np
import pytest

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import Material
from voxsym.constants import ELEMENTARY_CHARGE


def test_initial_electroneutrality():
    """After update(), electrolyte voxels have anion = cation."""
    vs = VoxSym(backend=None)
    m = Material(
        name="salt",
        ion_diffusivity=1e-9,
        ionic_valence=1,
        anion_diffusivity=1e-9,
        anion_valence=-1,
        ion_conc_max=1000.0,
    )
    for i in range(5):
        v = Voxel(x=float(i) * 1e-5, y=0.0, z=0.0, size=1e-5)
        v.material = m
        v.ion_concentration = 100.0
        vs.add_voxel(v)
    vs.update()
    for v in vs.voxels:
        assert v.anion_concentration == pytest.approx(100.0, abs=1e-6)


def test_anion_diffuses_with_cation():
    """A salt concentration step diffuses; anion front follows cation front."""
    vs = VoxSym(backend=None)
    m = Material(
        name="salt",
        ion_diffusivity=1e-9,
        ionic_valence=1,
        anion_diffusivity=1e-9,
        anion_valence=-1,
        ion_conc_max=1000.0,
    )
    for i in range(10):
        v = Voxel(x=float(i) * 1e-5, y=0.0, z=0.0, size=1e-5)
        v.material = m
        v.ion_concentration = 200.0 if i < 5 else 0.0
        v.anion_concentration = 200.0 if i < 5 else 0.0
        vs.add_voxel(v)

    vs.disable_heat()
    vs.dt_safety_factor = 1.0
    vs.step_and_update(1e-4)

    cat = np.array([v.ion_concentration for v in vs.voxels])
    an = np.array([v.anion_concentration for v in vs.voxels])

    # Both species moved outward; net charge density tiny
    assert cat[5] > 0.0 and an[5] > 0.0
    rho = ELEMENTARY_CHARGE * (cat + an * (-1.0))
    assert np.abs(rho).max() < 1e-6

