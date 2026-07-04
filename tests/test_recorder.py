"""Tests for the simulation recorder save/load paths."""

import os
import tempfile

import numpy as np
import pytest

from voxsym import VoxSym, Voxel
from voxsym.io.recorder import Recorder
from voxsym.material import COPPER


@pytest.fixture
def recorded_vs():
    """Return a headless VoxSym with a few recorded frames."""
    vs = VoxSym(backend=None)
    for x in range(-1, 2):
        for y in range(-1, 2):
            for z in range(-1, 2):
                v = Voxel(float(x), float(y), float(z), 1.0, temperature=300.0)
                v.material = COPPER
                vs.add_voxel(v)
    vs.set_region_temperature((0.0, 0.0, 0.0), 0.5, 500.0)

    dt = vs.max_stable_dt() * 0.5
    if not np.isfinite(dt) or dt <= 0:
        dt = 1e-3

    for i in range(5):
        vs.step_and_update(dt)

    return vs


def test_recorder_npz_roundtrip(recorded_vs, tmp_path):
    vs = recorded_vs
    npz_path = tmp_path / "rec.npz"
    vs._recorder.save(str(npz_path))

    assert npz_path.exists()
    data = Recorder.load(str(npz_path))
    assert "positions" in data
    assert "temperatures" in data
    assert len(data["times"]) == vs._recorder.frame_count
    assert len(data["positions"]) == len(vs.voxels)
    np.testing.assert_allclose(
        data["positions"], np.array([[v.x, v.y, v.z] for v in vs.voxels], dtype=np.float32)
    )


def test_recorder_csv_roundtrip(recorded_vs, tmp_path):
    vs = recorded_vs
    csv_path = tmp_path / "rec.csv"
    vs._recorder.save_csv(str(csv_path))

    assert csv_path.exists()
    data = Recorder.from_csv(str(csv_path))
    assert len(data["times"]) == vs._recorder.frame_count
    assert len(data["positions"]) == len(vs.voxels)


def test_recorder_load_into_simulation(recorded_vs, tmp_path):
    vs = recorded_vs
    npz_path = tmp_path / "rec.npz"
    vs._recorder.save(str(npz_path))

    data = Recorder.load(str(npz_path))
    vs2 = VoxSym(backend=None)
    vs2.load_simulation(data)

    assert len(vs2.voxels) == len(vs.voxels)
    for i, v in enumerate(vs2.voxels):
        assert np.isfinite(v.temperature)
        assert v.temperature >= 0
        assert v.x == vs.voxels[i].x
        assert v.y == vs.voxels[i].y
        assert v.z == vs.voxels[i].z
        assert v.size == vs.voxels[i].size


def test_recorder_frame_count(recorded_vs):
    assert recorded_vs._recorder.frame_count == 5
    assert len(recorded_vs._recorder._times) == 5
    assert len(recorded_vs._recorder._temperatures) == 5
