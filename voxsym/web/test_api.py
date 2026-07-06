"""Callable API for testing the VoxSym WebSocket server."""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any, Dict, Optional

import websockets.sync.client


class VoxSymTestClient:
    """Synchronous WebSocket client for the VoxSym backend.

    Parameters
    ----------
    port : int
        HTTP/WebSocket port (default 8080).
    host : str
        Host to connect to (default ``0.0.0.0``).
    """

    def __init__(self, port: int = 8080, host: str = "0.0.0.0"):
        self.url = f"http://{host}:{port}"
        self.ws_url = f"ws://{host}:{port}/ws"
        self.ws: Optional[websockets.sync.client.ClientConnection] = None

    def wait_for_server(self, timeout: float = 10.0) -> bool:
        """Poll HTTP until the server returns 200."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(self.url, timeout=0.5) as resp:
                    return resp.status == 200
            except Exception:
                time.sleep(0.1)
        return False

    def connect(self) -> None:
        """Open a WebSocket connection."""
        self.ws = websockets.sync.client.connect(self.ws_url, open_timeout=5.0)

    def close(self) -> None:
        if self.ws:
            self.ws.close()
            self.ws = None

    def send(self, cmd: str, **kwargs: Any) -> None:
        """Send a JSON command to the server."""
        if self.ws is None:
            self.connect()
        payload = {"cmd": cmd, **kwargs}
        self.ws.send(json.dumps(payload))

    def receive_frame(self, timeout: float = 2.0) -> Dict[str, Any]:
        """Wait for a frame-typed WebSocket message and return it as a dict."""
        if self.ws is None:
            self.connect()
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = self.ws.recv(timeout=0.5)
            except TimeoutError:
                continue
            data = json.loads(msg)
            if data.get("type") == "frame":
                return data
        raise TimeoutError("no frame received")

    def get_frame_after(self, cmd: str, **kwargs: Any) -> Dict[str, Any]:
        """Send a command and return the next frame."""
        self.send(cmd, **kwargs)
        time.sleep(0.1)
        return self.receive_frame()

    def __enter__(self) -> "VoxSymTestClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
