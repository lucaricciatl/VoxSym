"""Tornado-based WebSocket + static-file server for the VoxSym WebGL viewer."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, Optional, Set

import tornado.ioloop
import tornado.web
from tornado.ioloop import IOLoop
import tornado.websocket
import tornado.httpserver


from voxsym.web.protocol import CommandPayload, FramePayload

STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
FRONTEND_DIST_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "frontend", "dist")
)


def _resolve_static_dir(static_dir: Optional[str]) -> str:
    """Use the Vite-built frontend when available, otherwise fall back to static."""
    if static_dir:
        return static_dir
    if os.path.isdir(FRONTEND_DIST_DIR) and os.path.exists(
        os.path.join(FRONTEND_DIST_DIR, "index.html")
    ):
        return FRONTEND_DIST_DIR
    return STATIC_DIR


class _StaticFileHandler(tornado.web.StaticFileHandler):
    """Static file handler that sets aggressive no-cache headers."""

    def set_extra_headers(self, path: str) -> None:
        self.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.set_header("Pragma", "no-cache")
        self.set_header("Expires", "0")


class _WebSocketHandler(tornado.websocket.WebSocketHandler):
    """WebSocket endpoint at ``/ws``.

    Registers each connection in the shared client registry and forwards
    control commands to the attached ``VoxSym`` instance.
    """

    def initialize(self, server: "WebGLServer") -> None:
        self._server = server

    def open(self) -> None:
        self._server.add_client(self)
        # Send the most recent frame immediately so the viewer isn't blank.
        payload = self._server.get_latest_frame()
        if payload is not None:
            try:
                self.write_message(payload)
            except Exception:
                pass
        self._server.broadcast_config()

    def on_message(self, message) -> None:
        try:
            if isinstance(message, (bytes, bytearray)):
                message = message.decode("utf-8")
            cmd = CommandPayload.decode(message)
        except Exception as exc:
            logging.warning("Ignoring malformed WebSocket message: %s", exc)
            return
        self._server.handle_command(cmd, self)

    def on_close(self) -> None:
        self._server.remove_client(self)

    def check_origin(self, origin: str) -> bool:
        # Allow connections from any origin for local development.
        return True


class WebGLServer:
    """HTTP + WebSocket server that streams voxel frames to the static viewer.

    Parameters
    ----------
    voxsym : VoxSym
        The simulation instance commands are applied to.
    host : str, optional
        Interface to bind to. Default ``0.0.0.0``.
    port : int, optional
        TCP port to listen on. Default ``8080``.
    static_dir : str, optional
        Directory served at ``/``. Defaults to ``voxsym/web/static``.
    """

    def __init__(
        self,
        voxsym,
        host: str = "0.0.0.0",
        port: int = 8080,
        static_dir: Optional[str] = None,
    ):
        self.voxsym = voxsym
        self.host = host
        self.port = int(port)
        self.static_dir = _resolve_static_dir(static_dir)

        self._clients: Set[_WebSocketHandler] = set()
        self._latest_frame: Optional[str] = None
        self._lock = threading.Lock()

        self._app = tornado.web.Application(
            [
                (r"/ws", _WebSocketHandler, {"server": self}),
                (r"/(.*)", _StaticFileHandler, {"path": self.static_dir, "default_filename": "index.html"}),
            ]
        )
        self._http_server: Optional[tornado.httpserver.HTTPServer] = None
        self._ioloop: Optional[tornado.ioloop.IOLoop] = None
        self._thread: Optional[threading.Thread] = None

    def _make_server(self) -> tornado.httpserver.HTTPServer:
        """Build an HTTP server that allows rapid port re-use."""
        http_server = tornado.httpserver.HTTPServer(self._app)
        http_server.bind(self.port, self.host, reuse_port=False)
        return http_server

    # ------------------------------------------------------------------
    # Client registry
    # ------------------------------------------------------------------

    def add_client(self, client: _WebSocketHandler) -> None:
        with self._lock:
            self._clients.add(client)

    def broadcast_config(self) -> None:
        """Send current simulation configuration to every connected client."""
        if self.voxsym is None:
            return
        cfg = self.voxsym.get_config()
        data = json.dumps({"type": "config", **cfg})
        with self._lock:
            clients = list(self._clients)
        for c in clients:
            try:
                c.write_message(data)
            except Exception:
                with self._lock:
                    self._clients.discard(c)

    def _reply(self, client, kind: str, message: str) -> None:
        """Send a short toast/ack message to a single client on the IOLoop."""
        data = json.dumps({"type": "toast", "kind": kind, "message": message})
        def _write():
            try:
                client.write_message(data)
            except Exception:
                pass
        try:
            (self._ioloop or IOLoop.current()).add_callback(_write)
        except Exception:
            pass

    def broadcast_state_patch(self, **fields) -> None:
        """Send a lightweight, deduplicated state update to every client."""
        if not fields:
            return
        key = tuple(sorted(fields.items()))
        if getattr(self, "_last_state_patch", None) == key:
            return
        self._last_state_patch = key
        message = json.dumps({"type": "state", **fields})
        with self._lock:
            clients = list(self._clients)
        if not clients:
            return
        loop = self._ioloop or IOLoop.current()
        def _flush():
            for client in clients:
                try:
                    client.write_message(message)
                except Exception:
                    pass
        try:
            loop.add_callback(_flush)
        except Exception:
            pass

    def remove_client(self, client: _WebSocketHandler) -> None:
        with self._lock:
            self._clients.discard(client)

    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    # ------------------------------------------------------------------
    # Frame broadcast
    # ------------------------------------------------------------------

    def broadcast_frame(self, payload: FramePayload) -> None:
        """Serialize and cache the latest frame; the IOLoop flushes it."""
        message = payload.encode()
        with self._lock:
            self._latest_frame = message
            clients = list(self._clients)
        if not clients:
            return
        loop = self._ioloop or IOLoop.current()
        def _flush():
            for client in clients:
                try:
                    client.write_message(message)
                except Exception:
                    pass
        try:
            loop.add_callback(_flush)
        except Exception:
            pass

    def set_latest_frame(self, payload: FramePayload) -> None:
        """Cache the latest frame for newly connecting clients."""
        with self._lock:
            self._latest_frame = payload.encode()

    def get_latest_frame(self) -> Optional[str]:
        with self._lock:
            return self._latest_frame

    # ------------------------------------------------------------------
    # Command handling
    # ------------------------------------------------------------------

    def handle_command(self, cmd: CommandPayload, client: _WebSocketHandler) -> None:
        """Apply a control command to the attached VoxSym instance."""
        vs = self.voxsym
        try:
            # Fast path for play/pause/stop: they only touch threading.Event
            # flags and can be applied immediately with no blocking.
            if cmd.cmd == "play":
                vs.play()
                self.broadcast_state_patch(playing=bool(vs.is_playing()))
            elif cmd.cmd == "pause":
                vs.pause()
                self.broadcast_state_patch(playing=bool(vs.is_playing()))
            elif cmd.cmd == "stop":
                vs.stop()
                self.broadcast_state_patch(playing=False)
            elif cmd.cmd == "get_config":
                client.write_message(json.dumps({"type": "config", **vs.get_config()}))
            elif cmd.cmd == "inspect_voxel":
                try:
                    data = self._inspect_voxel(int(cmd.voxel_id))
                    client.write_message(json.dumps({"type": "voxel", "data": data}))
                except Exception as exc:
                    logging.warning("inspect_voxel failed: %s", exc)
                    self._reply(client, "error", f"Inspect voxel failed: {exc}")
            else:
                # Everything else is scheduled on the simulation thread so the
                # WebSocket IOLoop never blocks on physics/rendering work.
                payload = {k: v for k, v in vars(cmd).items() if v is not None and k != "cmd"}
                vs.schedule_command(cmd.cmd, **payload)
        except Exception as exc:
            logging.warning("Error handling command %r: %s", cmd.cmd, exc)
            self._reply(client, "error", f"Command failed: {exc}")

    # ------------------------------------------------------------------
    # Command handling (legacy synchronous helpers kept for tests / scripts)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    def _inspect_voxel(self, voxel_id: int) -> Dict[str, Any]:
        """Return a JSON-safe snapshot of a single voxel."""
        vs = self.voxsym
        voxel = vs.voxels[voxel_id]
        material_name = getattr(voxel.material, "name", "unknown") if voxel.material else "unknown"

        def _vec(name, default):
            arr = getattr(voxel, name, None)
            if arr is None:
                return list(default)
            return [float(v) for v in arr]

        return {
            "id": voxel_id,
            "index": voxel_id,
            "x": float(voxel.x),
            "y": float(voxel.y),
            "z": float(voxel.z),
            "size": float(voxel.size),
            "material": material_name,
            "temperature": float(voxel.temperature),
            "ion_concentration": float(voxel.ion_concentration),
            "anion_concentration": float(getattr(voxel, "anion_concentration", 0.0)),
            "effective_conductivity": float(getattr(voxel, "effective_conductivity", 0.0)),
            "potential": float(getattr(voxel, "phi", getattr(voxel, "potential", 0.0))),
            "charge": float(getattr(voxel, "charge", 0.0)),
            "electric_field": _vec("electric_field", [0.0, 0.0, 0.0]),
            "magnetic_field": _vec("magnetic_field", [0.0, 0.0, 0.0]),
            "current_density": _vec("current_density", [0.0, 0.0, 0.0]),
        }

    def start(self) -> None:
        """Start the server in a background thread and return immediately."""
        if self._thread is not None:
            return

        self._http_server = self._make_server()
        # Use a new IOLoop for the server thread instead of the current loop,
        # so tests and other callers can start multiple servers without
        # "event loop already running" errors.
        self._ioloop = tornado.ioloop.IOLoop()
        self._started = threading.Event()

        def _run():
            self._ioloop.make_current()
            self._http_server.start(1)
            self._ioloop.add_callback(self._started.set)
            self._ioloop.start()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        self._started.wait(timeout=5.0)
        # Give the new loop a moment to start accepting connections before returning.
        time.sleep(0.05)

    def stop(self) -> None:
        """Stop the background server."""
        if self._ioloop is None:
            return
        try:
            self._ioloop.add_callback(self._ioloop.stop)
        except Exception:
            pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._ioloop = None
        self._http_server = None

    def __del__(self) -> None:
        try:
            self.stop()
        except Exception:
            pass