"""Automated UI / WebSocket smoke tests for the WebGL viewer."""

import json
import os
import subprocess
import sys
import time
import urllib.request

import numpy as np
import pytest

# Add repo root to path so examples can import the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from voxsym import VoxSym, Voxel
from voxsym.web.protocol import CommandPayload, FramePayload
from voxsym.web.server import WebGLServer
from voxsym.visualization.backends.webgl_backend import WebGLBackend
from voxsym.material import COPPER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 0))
        return s.getsockname()[1]


def _wait_for_server(port, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://0.0.0.0:{port}/", timeout=0.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.1)
    return False


def _read_first_ws_frame(port, timeout=5.0):
    """Open the WebSocket and return the first frame payload as a dict."""
    try:
        import websockets.sync.client
    except ImportError as exc:  # pragma: no cover
        pytest.skip(f"websockets package not available: {exc}")

    url = f"ws://0.0.0.0:{port}/ws"
    ws = websockets.sync.client.connect(url, open_timeout=timeout)
    try:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = ws.recv(timeout=0.5)
            except TimeoutError:
                continue
            data = json.loads(msg)
            if data.get("type") == "frame":
                return data
    finally:
        ws.close()
    return None


def _ensure_first_frame(port, timeout=5.0):
    """Keep rendering until a WebSocket client receives a frame payload."""
    import threading
    import queue
    result = queue.Queue()

    def _wait():
        try:
            frame = _read_first_ws_frame(port, timeout=timeout)
            result.put(("frame", frame))
        except Exception as exc:
            result.put(("error", exc))

    t = threading.Thread(target=_wait, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        return None
    status, value = result.get_nowait()
    if status == "error":
        raise value
    return value


# ---------------------------------------------------------------------------
# Protocol / payload tests
# ---------------------------------------------------------------------------

def test_frame_payload_includes_playing():
    payload = FramePayload(playing=False, time=0.0)
    obj = json.loads(payload.encode())
    assert obj["playing"] is False
    assert obj["type"] == "frame"

    decoded = FramePayload.decode(payload.encode())
    assert decoded.playing is False


def test_voxsym_is_playing_defaults():
    vs = VoxSym(backend=None)
    # A fresh VoxSym starts paused (simulation_paused=True)
    assert vs.is_playing() is False
    vs.play()
    assert vs.is_playing() is True
    vs.pause()
    assert vs.is_playing() is False


def test_webgl_backend_frame_has_playing_flag():
    """Build a tiny grid, render once, and verify the payload carries playing."""
    port = _free_port()
    vs = VoxSym(port=port, host="0.0.0.0", backend="webgl")
    try:
        v = Voxel(x=0.0, y=0.0, z=0.0, size=1.0, color=(255, 0, 0))
        v.material = COPPER
        vs.add_voxel(v)
        vs._ensure_visualizer()
        vs.render()

        payload = vs._webgl_backend.get_latest_payload()
        assert isinstance(payload, FramePayload)
        assert payload.playing == vs.is_playing()
        assert payload.voxels["count"] == 1
    finally:
        vs.stop()


# ---------------------------------------------------------------------------
# WebSocket command propagation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmd,kwargs", [
    ("play", {}),
    ("pause", {}),
    ("stop", {}),
    ("reset", {}),
    ("set_layer", {"layer": "temperature", "active": True}),
    ("set_opacity", {"value": 0.5}),
    ("set_cross_section", {"axis": "x", "pos": 0.0}),
    ("set_arrow_scale", {"value": 1.2}),
    ("set_time_scale", {"value": 2.0}),
])
def test_websocket_commands_propagate(cmd, kwargs):
    """Start a small example server and send every supported command."""
    port = _free_port()
    vs = VoxSym(port=port, host="0.0.0.0", backend="webgl")
    try:
        # Add a single voxel so the visualizer has something to render.
        v = Voxel(x=0.0, y=0.0, z=0.0, size=1.0, color=COPPER.color)
        v.material = COPPER
        vs.add_voxel(v)
        vs._ensure_visualizer()
        assert _wait_for_server(port, timeout=10.0), "server did not come up"

        # Read the initial frame so the connection is alive.  Force a render
        # if the server's cached latest frame is still empty.
        frame = _read_first_ws_frame(port)
        if frame is None:
            vs.render()
            frame = _ensure_first_frame(port)
        assert frame is not None, "no frame received over WebSocket"
        assert frame["type"] == "frame"

        try:
            import websockets.sync.client
        except ImportError as exc:  # pragma: no cover
            pytest.skip(f"websockets package not available: {exc}")

        ws = websockets.sync.client.connect(f"ws://0.0.0.0:{port}/ws")
        try:
            msg = CommandPayload(cmd=cmd, **kwargs).encode()
            ws.send(msg)
            time.sleep(0.2)
            # The command must not crash; receive at least one more frame.
            ws.send(CommandPayload(cmd="pause").encode())
            deadline = time.time() + 5.0
            while time.time() < deadline:
                data = json.loads(ws.recv(timeout=0.5))
                if data.get("type") == "frame":
                    assert "playing" in data
                    break
            else:
                pytest.fail("no further frame after command")
        finally:
            ws.close()
    finally:
        vs.stop()


# ---------------------------------------------------------------------------
# Arrow direction sanity
# ---------------------------------------------------------------------------

def test_arrow_payload_has_direction():
    vs = VoxSym(backend=None)
    v = Voxel(x=0.0, y=0.0, z=0.0, size=1.0, color=COPPER.color)
    v.material = COPPER
    v.electric_field = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    vs.add_voxel(v)

    backend = WebGLBackend(vs, server=None, render_scale=1.0)
    backend.add_arrows(
        points=np.array([[-0.5, 0.0, 0.0, 0.5, 0.0, 0.0]], dtype=np.float32),
        colors=np.array([[255, 0, 0]], dtype=np.uint8),
        shaft_radius=0.05,
        head_radius=0.1,
        head_length=0.2,
        direction=np.array([[1.0, 0.0, 0.0]], dtype=np.float32),
    )
    backend.render(
        positions=np.array([[0.0, 0.0, 0.0]], dtype=np.float32),
        scales=np.array([[1.0]], dtype=np.float32),
        colors=np.array([[255, 0, 0]], dtype=np.uint8),
        opacities=np.array([1.0], dtype=np.float32),
    )

    payload = backend.get_latest_payload()
    arrows = payload.arrows
    assert arrows["count"] == 1
    pts = arrows["points"][0]
    assert len(pts) == 6
    tail = np.array(pts[:3])
    head = np.array(pts[3:])
    assert not np.allclose(tail, head)
    assert head[0] > tail[0]


# ---------------------------------------------------------------------------
# Example smoke tests
# ---------------------------------------------------------------------------

def _run_example_smoke(example_name, timeout=20.0):
    path = os.path.join(os.path.dirname(__file__), "..", "examples", example_name)
    proc = subprocess.Popen(
        [sys.executable, "-u", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        # Wait until the server reports its URL, then sleep briefly to let it boot.
        url_found = False
        deadline = time.time() + timeout
        while time.time() < deadline and proc.poll() is None:
            line = proc.stdout.readline()
            if line and "http://" in line:
                url_found = True
                break
        if not url_found:
            err = proc.stderr.read() if proc.stderr else ""
            proc.terminate()
            pytest.fail(f"{example_name} did not print viewer URL. stderr: {err}")
        time.sleep(1.5)
        assert proc.poll() is None, f"{example_name} exited early"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    return proc


@pytest.mark.skipif(os.environ.get("SKIP_EXAMPLE_SMOKE"), reason="SKIP_EXAMPLE_SMOKE set")
def test_example_01_basic_grid_smoke():
    _run_example_smoke("01_basic_grid.py")


@pytest.mark.skipif(os.environ.get("SKIP_EXAMPLE_SMOKE"), reason="SKIP_EXAMPLE_SMOKE set")
def test_example_09_mxene_memristor_smoke():
    _run_example_smoke("09_mxene_memristor.py")


@pytest.mark.skipif(os.environ.get("SKIP_EXAMPLE_SMOKE"), reason="SKIP_EXAMPLE_SMOKE set")
def test_example_04_electric_field_smoke():
    _run_example_smoke("04_electric_field.py")
