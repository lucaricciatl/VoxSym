"""Tests for ion diffusion and charge conservation."""

import numpy as np
import pytest

from voxsym import VoxSym, Voxel
from voxsym.material import WATER


def test_ion_diffusion_charge_conservation(water_cube_3x3x3):
    vs = water_cube_3x3x3
    vs._ensure_ion_solver().set_conserve_charge(enabled=True, conserved_total=True)

    total_before = sum(v.charge for v in vs.voxels)

    dt = vs.max_stable_dt() * 0.5
    if not np.isfinite(dt) or dt <= 0:
        dt = 1e-6

    for _ in range(50):
        vs.step_and_update(dt)

    concs = [v.ion_concentration for v in vs.voxels]
    assert all(np.isfinite(c) and c >= 0 for c in concs)

    total_after = sum(v.charge for v in vs.voxels)
    assert abs(total_after - total_before) < 1e-12
    assert all(np.isfinite(v.charge) for v in vs.voxels)


def test_ion_diffusion_small_grid():
    vs = VoxSym(backend=None)
    v1 = Voxel(0.0, 0.0, 0.0, 1.0, ion_concentration=100.0)
    v1.material = WATER
    v2 = Voxel(1.0, 0.0, 0.0, 1.0, ion_concentration=0.0)
    v2.material = WATER
    vs.add_voxel(v1)
    vs.add_voxel(v2)

    dt = 1e-6
    for _ in range(20):
        vs.step_and_update(dt)

    assert v1.ion_concentration >= 0 and np.isfinite(v1.ion_concentration)
    assert v2.ion_concentration >= 0 and np.isfinite(v2.ion_concentration)
    assert v1.ion_concentration + v2.ion_concentration > 0


def test_ion_solver_without_charge_conservation():
    vs = VoxSym(backend=None)
    for x in range(-1, 2):
        for y in range(-1, 2):
            for z in range(-1, 2):
                v = Voxel(float(x), float(y), float(z), 1.0, ion_concentration=100.0)
                v.material = WATER
                vs.add_voxel(v)

    conc_before = [v.ion_concentration for v in vs.voxels]
    dt = 1e-6
    for _ in range(10):
        vs.step_and_update(dt)
    conc_after = [v.ion_concentration for v in vs.voxels]

    assert all(np.isfinite(c) and c >= 0 for c in conc_after)
    # Total concentration should not increase without sources.
    assert sum(conc_after) <= sum(conc_before) + 1e-6
