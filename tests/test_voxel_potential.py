"""Test user-defined voxel potentials and Poisson field propagation."""

import numpy as np
import pytest

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import Material


def test_fixed_voxel_potential_propagates_field():
    """A 1x1x5 line with two fixed potentials produces a linear E field."""
    vs = VoxSym(backend=None)
    m = Material(name="vac", conductivity=1e-9, dielectric_constant=1.0)
    for i in range(5):
        v = Voxel(x=float(i) * 1e-5, y=0.0, z=0.0, size=1e-5)
        v.material = m
        vs.add_voxel(v)

    # Fix ends to 1 V and 0 V
    vs.set_voxel_potential(0, 1.0, fixed=True)
    vs.set_voxel_potential(4, 0.0, fixed=True)

    vs.set_enable_poisson(True)
    vs.solve_poisson()

    # Potential should decrease monotonically from left to right
    potentials = [v.potential for v in vs.voxels]
    assert np.all(np.diff(potentials) <= 1e-6)

    # E field should point roughly along -x with magnitude ~1 V / 4e-5 m
    E0 = vs.voxels[1].electric_field
    assert E0[0] > 1e4
    assert abs(E0[1]) < 1e-6
    assert abs(E0[2]) < 1e-6


def test_region_potential_overrides_voltage_boundary():
    """set_region_potential sets fixed-potential nodes in a sphere."""
    vs = VoxSym(backend=None)
    m = Material(name="vac", conductivity=1e-9, dielectric_constant=1.0)
    for i in range(10):
        v = Voxel(x=float(i) * 1e-5, y=0.0, z=0.0, size=1e-5)
        v.material = m
        vs.add_voxel(v)

    vs.set_region_potential(center=(0.0, 0.0, 0.0), radius=1.5e-5, potential=0.5, fixed=True)
    vs.set_enable_poisson(True)
    vs.solve_poisson()

    fixed_count = sum(1 for v in vs.voxels if v.potential_fixed)
    assert fixed_count >= 1
    # Fixed voxel potential should remain exactly 0.5 V after solve
    for v in vs.voxels:
        if v.potential_fixed:
            assert v.potential == pytest.approx(0.5, abs=1e-6)
