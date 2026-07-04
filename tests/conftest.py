"""Shared pytest fixtures and helpers for VoxSym."""

import pytest

from voxsym import VoxSym, Voxel
from voxsym.material import COPPER, WATER


@pytest.fixture
def empty_vs():
    """Headless VoxSym instance with no voxels."""
    return VoxSym(backend=None)


@pytest.fixture
def copper_cube_3x3x3():
    """3×3×3 copper grid with a hot center region, headless."""
    vs = VoxSym(backend=None)
    for x in range(-1, 2):
        for y in range(-1, 2):
            for z in range(-1, 2):
                v = Voxel(float(x), float(y), float(z), 1.0, temperature=300.0)
                v.material = COPPER
                vs.add_voxel(v)
    vs.set_region_temperature((0.0, 0.0, 0.0), 0.5, 500.0)
    return vs


@pytest.fixture
def water_cube_3x3x3():
    """3×3×3 water grid with uniform ion concentration, headless."""
    vs = VoxSym(backend=None)
    for x in range(-1, 2):
        for y in range(-1, 2):
            for z in range(-1, 2):
                v = Voxel(float(x), float(y), float(z), 1.0, ion_concentration=100.0)
                v.material = WATER
                vs.add_voxel(v)
    return vs
