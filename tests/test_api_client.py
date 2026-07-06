"""Tests for the callable WebSocket API client."""

import socket

import pytest

from voxsym import VoxSym, Voxel
from voxsym.material import COPPER
from voxsym.web.test_api import VoxSymTestClient


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 0))
        return s.getsockname()[1]


def test_api_set_layer_changes_active_layers():
    port = _free_port()
    vs = VoxSym(port=port, host="0.0.0.0", backend="webgl")
    try:
        v = Voxel(x=0, y=0, z=0, size=1, color=COPPER.color)
        v.material = COPPER
        v.temperature = 350.0
        vs.add_voxel(v)
        vs._ensure_visualizer()
        vs.render()

        client = VoxSymTestClient(port=port)
        assert client.wait_for_server()
        client.connect()
        frame = client.receive_frame()
        assert frame["active_layers"] == ["voxel_color"]

        vs.set_layer("temperature", True)
        vs.render()
        frame = client.receive_frame()
        assert "temperature" in frame["active_layers"]
        colors = frame["voxels"]["colors"]
        assert colors != list(COPPER.color) * (len(colors) // 3)
    finally:
        client.close()
        vs.stop()


def test_api_opacity_updates_in_real_time():
    port = _free_port()
    vs = VoxSym(port=port, host="0.0.0.0", backend="webgl")
    try:
        v = Voxel(x=0, y=0, z=0, size=1, color=COPPER.color)
        vs.add_voxel(v)
        vs._ensure_visualizer()
        vs.render()

        client = VoxSymTestClient(port=port)
        client.wait_for_server()
        client.connect()
        client.receive_frame()

        vs.opacity = 0.25
        vs.render()
        client.receive_frame()  # drain stale frame
        frame = client.receive_frame()
        assert frame["opacity"] == pytest.approx(0.25, abs=1e-3)
        colors_before = frame["voxels"]["colors"][:3]

        vs.opacity = 0.75
        vs.render()
        client.receive_frame()
        frame = client.receive_frame()
        assert frame["opacity"] == pytest.approx(0.75, abs=1e-3)
        assert frame["voxels"]["colors"][:3] == colors_before
    finally:
        client.close()
        vs.stop()
