"""Tests for the WebGL JSON wire protocol."""

import json

import numpy as np
import pytest

from voxsym.web.protocol import CommandPayload, FramePayload


def test_frame_payload_empty_encode_decode():
    payload = FramePayload.empty(time=1.5)
    encoded = payload.encode()
    assert isinstance(encoded, str)
    obj = json.loads(encoded)
    assert obj["type"] == "frame"
    assert obj["time"] == 1.5
    assert obj["voxels"]["count"] == 0

    decoded = FramePayload.decode(encoded)
    assert decoded.type == "frame"
    assert decoded.time == 1.5
    assert decoded.voxels["count"] == 0


def test_frame_payload_with_voxels():
    payload = FramePayload(
        type="frame",
        time=0.0,
        voxels={
            "count": 2,
            "positions": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            "sizes": [1.0, 1.0],
            "colors": [255, 0, 0, 0, 255, 0],
            "opacities": [1.0, 0.5],
        },
        arrows={"count": 0, "points": [], "colors": []},
        active_layers=["material"],
    )
    encoded = payload.encode()
    obj = json.loads(encoded)
    assert obj["voxels"]["count"] == 2
    assert obj["voxels"]["colors"] == [255, 0, 0, 0, 255, 0]
    assert obj["active_layers"] == ["material"]


def test_command_payload_decode():
    raw = json.dumps({"cmd": "play"})
    cmd = CommandPayload.decode(raw)
    assert cmd.cmd == "play"
    assert cmd.layer is None


def test_command_payload_with_args():
    raw = json.dumps({"cmd": "set_layer", "layer": "temperature", "active": True})
    cmd = CommandPayload.decode(raw)
    assert cmd.cmd == "set_layer"
    assert cmd.layer == "temperature"
    assert cmd.active is True


def test_command_payload_encode():
    cmd = CommandPayload(cmd="set_opacity", value=0.5)
    encoded = cmd.encode()
    obj = json.loads(encoded)
    assert obj == {"cmd": "set_opacity", "value": 0.5}


def test_command_payload_roundtrip():
    original = CommandPayload(cmd="set_cross_section", axis="x", pos=0.5)
    encoded = original.encode()
    decoded = CommandPayload.decode(encoded)
    assert decoded.cmd == "set_cross_section"
    assert decoded.axis == "x"
    assert decoded.pos == 0.5


def test_frame_payload_lists_are_serializable():
    payload = FramePayload(
        voxels={
            "count": 1,
            "positions": np.array([0.0, 0.0, 0.0]).tolist(),
            "sizes": [1.0],
            "colors": [128, 128, 128],
            "opacities": [1.0],
        }
    )
    encoded = payload.encode()
    assert isinstance(encoded, str)
    assert json.loads(encoded)["voxels"]["count"] == 1
