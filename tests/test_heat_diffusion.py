"""Tests for the heat-diffusion solver."""

import math

import numpy as np
import pytest

from voxsym import VoxSym, Voxel
from voxsym.material import COPPER, WATER
from voxsym.physics.stability import max_stable_dt_for_diffusion


def test_heat_diffusion_uniform_grid(copper_cube_3x3x3):
    vs = copper_cube_3x3x3
    dt = vs.max_stable_dt() * 0.5
    assert dt > 0 and np.isfinite(dt)

    for _ in range(10):
        vs.step_and_update(dt)

    temps = [v.temperature for v in vs.voxels]
    assert all(np.isfinite(t) and t >= 0 for t in temps)
    assert min(temps) < 500.0
    assert max(temps) <= 500.0 + 1e-6


def test_heat_diffusion_water_grid():
    vs = VoxSym(backend=None)
    for x in range(-1, 2):
        for y in range(-1, 2):
            for z in range(-1, 2):
                v = Voxel(float(x), float(y), float(z), 1.0, temperature=300.0)
                v.material = WATER
                vs.add_voxel(v)
    vs.set_region_temperature((0.0, 0.0, 0.0), 0.5, 500.0)

    dt = vs.max_stable_dt() * 0.5
    assert dt > 0 and np.isfinite(dt)

    for _ in range(10):
        vs.step_and_update(dt)

    temps = [v.temperature for v in vs.voxels]
    assert all(np.isfinite(t) and t >= 0 for t in temps)


def test_heat_solver_returns_finite_temps():
    vs = VoxSym(backend=None)
    for x in range(-1, 2):
        for y in range(-1, 2):
            for z in range(-1, 2):
                v = Voxel(float(x), float(y), float(z), 1.0, temperature=300.0)
                v.material = COPPER
                vs.add_voxel(v)

    new_temps = vs._ensure_heat_solver().compute_step(1.0)
    assert all(np.isfinite(t) and t >= 0 for t in new_temps)


def test_max_stable_dt_for_diffusion_helper():
    # Copper thermal diffusivity ≈ 401 / (8960 * 385) ≈ 1.16e-4 m²/s
    D = 401.0 / (8960.0 * 385.0)
    dt = max_stable_dt_for_diffusion(D, 1.0, dim=3)
    expected = 1.0 / (2.0 * 3.0 * D)
    assert math.isclose(dt, expected, rel_tol=1e-9)
    assert dt > 0 and np.isfinite(dt)


def test_max_stable_dt_for_zero_diffusivity():
    assert max_stable_dt_for_diffusion(0.0, 1.0, dim=3) == float("inf")
    assert max_stable_dt_for_diffusion(1.0, 0.0, dim=3) == float("inf")
