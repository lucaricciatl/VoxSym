"""Tests for explicit time-step stability helpers."""

import math

import numpy as np
import pytest

from voxsym import VoxSym, Voxel
from voxsym.material import COPPER, WATER
from voxsym.physics.stability import max_stable_dt_for_diffusion


def test_max_stable_dt_for_copper_grid():
    vs = VoxSym(backend=None)
    for x in range(-1, 2):
        for y in range(-1, 2):
            for z in range(-1, 2):
                v = Voxel(float(x), float(y), float(z), 1.0, temperature=300.0)
                v.material = COPPER
                vs.add_voxel(v)

    dt = vs.max_stable_dt()
    assert np.isfinite(dt) and dt > 0
    # Copper thermal diffusivity ≈ 1.16e-4 m²/s → cap ≈ 1433 s for 1 m voxels
    D_copper = 401.0 / (8960.0 * 385.0)
    expected = max_stable_dt_for_diffusion(D_copper, 1.0, dim=3)
    assert math.isclose(dt, expected, rel_tol=1e-3)


def test_max_stable_dt_for_water_grid():
    vs = VoxSym(backend=None)
    for x in range(-1, 2):
        for y in range(-1, 2):
            for z in range(-1, 2):
                v = Voxel(float(x), float(y), float(z), 1.0, ion_concentration=100.0)
                v.material = WATER
                vs.add_voxel(v)

    dt = vs.max_stable_dt()
    assert np.isfinite(dt) and dt > 0
    # Water ionic diffusivity 1e-9 m²/s dominates and gives a large cap.
    assert dt > 1.0


def test_max_stable_dt_headless_empty():
    vs = VoxSym(backend=None)
    dt = vs.max_stable_dt()
    assert dt == float("inf")


def test_max_stable_dt_clamping():
    vs = VoxSym(backend=None)
    for x in range(-1, 2):
        for y in range(-1, 2):
            for z in range(-1, 2):
                v = Voxel(float(x), float(y), float(z), 1.0, temperature=300.0)
                v.material = COPPER
                vs.add_voxel(v)

    cap = vs.max_stable_dt()
    huge_dt = cap * 10.0
    with pytest.warns(RuntimeWarning, match="exceeds safe limit"):
        clamped = vs._clamp_dt(huge_dt)
    assert clamped == cap * vs.dt_safety_factor


def test_max_stable_dt_for_diffusion_zero_inputs():
    assert max_stable_dt_for_diffusion(0.0, 1.0, dim=3) == float("inf")
    assert max_stable_dt_for_diffusion(1.0, 0.0, dim=3) == float("inf")
    assert max_stable_dt_for_diffusion(1.0, 1.0, dim=0) == float("inf")
