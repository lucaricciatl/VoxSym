"""Shared fixtures and session setup for VoxSym tests."""
import os
import subprocess
import sys

import pytest

from voxsym import VoxSym, Voxel
from voxsym.material import COPPER, WATER

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(REPO_ROOT, "voxsym", "web", "frontend")
DIST_INDEX = os.path.join(FRONTEND_DIR, "dist", "index.html")


@pytest.fixture(scope="session", autouse=True)
def ensure_frontend_built():
    """Build the Vite frontend once before any test that needs the dist bundle."""
    if not os.path.exists(DIST_INDEX):
        subprocess.check_call(
            ["npm", "run", "build"],
            cwd=FRONTEND_DIR,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )


@pytest.fixture(scope="function")
def copper_cube_3x3x3():
    """A 3x3x3 copper cube centered at the origin."""
    vs = VoxSym(backend=None)
    for x in range(-1, 2):
        for y in range(-1, 2):
            for z in range(-1, 2):
                v = Voxel(float(x), float(y), float(z), size=1.0, color=COPPER.color)
                v.material = COPPER
                vs.add_voxel(v)
    yield vs
    vs.stop()


@pytest.fixture(scope="function")
def water_cube_3x3x3():
    """A 3x3x3 water cube centered at the origin with unit concentration."""
    vs = VoxSym(backend=None)
    for x in range(-1, 2):
        for y in range(-1, 2):
            for z in range(-1, 2):
                v = Voxel(float(x), float(y), float(z), size=1.0, color=WATER.color)
                v.material = WATER
                v.ion_concentration = 1.0
                vs.add_voxel(v)
    yield vs
    vs.stop()
