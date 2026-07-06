"""WebGL render backend for VoxSym.

This backend does not draw locally.  It builds a compact JSON frame
payload from the current voxel state and exposes it to a WebGLServer
which streams it to browser clients over WebSocket.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from voxsym.visualization.backends.base import RenderBackend
from voxsym.web.protocol import FramePayload


class WebGLBackend(RenderBackend):
    """RenderBackend that serializes the current frame for browser rendering.

    Parameters
    ----------
    voxsym : VoxSym
        The simulation object whose voxels will be rendered.
    server : WebGLServer
        Tornado WebSocket server that broadcasts frames to clients.
    render_scale : float, optional
        Scale applied to all positions and sizes before encoding.
    """

    def __init__(self, voxsym, server, render_scale: float = 1.0):
        self.voxsym = voxsym
        self.server = server
        self.render_scale = float(render_scale)
        self._latest_frame: Dict[str, Any] = FramePayload.empty().encode()
        self._latest_payload: FramePayload = FramePayload.empty()
        self._opacity: float = 1.0
        self._handle: Optional[object] = server
        self._arrow_points = np.zeros((0, 2, 3), dtype=np.float32)
        self._arrow_colors = np.zeros((0, 3), dtype=np.uint8)

    # ------------------------------------------------------------------
    # RenderBackend API
    # ------------------------------------------------------------------

    def render(self, positions, scales, colors, opacities):
        """Store the current voxel frame as a serialized JSON payload."""
        positions = np.asarray(positions, dtype=np.float32)
        scales = np.asarray(scales, dtype=np.float32)
        colors = np.asarray(colors, dtype=np.uint8)
        # Preserve per-voxel opacity values as-is; backend set_opacity applies
        # the global multiplier when broadcasting updates.
        self._per_voxel_opacities = np.asarray(opacities, dtype=np.float32)
        opacities = self._per_voxel_opacities * self._opacity

        n = positions.shape[0]
        if n == 0:
            payload = FramePayload.empty(time=float(self.voxsym.elapsed_time))
        else:
            sizes = scales[:, 0] if scales.ndim == 2 else np.full(n, scales[0])
            payload = FramePayload(
                type="frame",
                time=float(self.voxsym.elapsed_time),
                frame_index=int(self.voxsym.frame_index),
                opacity=float(self._opacity),
                playing=bool(self.voxsym.is_playing()),
                voxels={
                    "count": int(n),
                    "positions": positions.ravel().tolist(),
                    "sizes": sizes.ravel().tolist(),
                    "colors": colors.ravel().tolist(),
                    "opacities": opacities.ravel().tolist(),
                },
                arrows=self._build_arrows(),
                active_layers=self._active_layers(),
            )

        self._latest_payload = payload
        self._latest_frame = payload.encode()
        if self.server is not None:
            self.server.set_latest_frame(payload)
            self.server.broadcast_frame(payload)

    def get_latest_payload(self) -> FramePayload:
        return self._latest_payload

    def get_latest_frame(self) -> Dict[str, Any]:
        return self._latest_frame

    def set_opacity(self, value: float):
        self._opacity = float(value)

    def add_arrows(self, points, colors, shaft_radius, head_radius, head_length, direction=None):
        """Store arrow data so the next frame encodes it.

        The raw arrow geometry (points, colors) is cached as numpy arrays.
        Actual shaft/head geometry is reconstructed in the browser from the
        compact ``points`` array.  Optional ``direction`` gives the normalized
        vector so the client can render unambiguous orientation even when the
        tail→head length is very small.
        """
        self._arrow_points = np.asarray(points, dtype=np.float32)
        self._arrow_colors = np.asarray(colors, dtype=np.uint8)
        self._arrow_shaft_radius = float(shaft_radius)
        self._arrow_head_radius = float(head_radius)
        self._arrow_head_length = float(head_length)
        if direction is not None:
            self._arrow_directions = np.asarray(direction, dtype=np.float32)
        else:
            n = self._arrow_points.shape[0]
            self._arrow_directions = np.zeros((n, 3), dtype=np.float32)

    def set_opacity(self, opacity: float):
        """Set the global opacity multiplier for rendered voxels and broadcast immediately."""
        self._opacity = float(opacity)
        payload = self._latest_payload
        payload.opacity = self._opacity
        if payload.voxels.get("count", 0) > 0:
            per_voxel = getattr(self, "_per_voxel_opacities", None)
            if per_voxel is not None and len(per_voxel) == payload.voxels["count"]:
                payload.voxels["opacities"] = [
                    min(1.0, max(0.0, self._opacity * float(o))) for o in per_voxel
                ]
            else:
                payload.voxels["opacities"] = [
                    min(1.0, max(0.0, self._opacity)) for _ in range(payload.voxels["count"])
                ]
        self._latest_frame = payload.encode()
        if self.server is not None:
            self.server.set_latest_frame(payload)
            self.server.broadcast_frame(payload)

    def clear(self):
        """Reset the stored frame to empty."""
        self._latest_frame = FramePayload.empty().encode()
        self._latest_payload = FramePayload.empty()
        self._arrow_points = np.zeros((0, 2, 3), dtype=np.float32)
        self._arrow_colors = np.zeros((0, 3), dtype=np.uint8)
        self._arrow_directions = np.zeros((0, 3), dtype=np.float32)

    @property
    def handle(self) -> Optional[object]:
        """Returns the attached WebGLServer handle."""
        return self._handle

    def encode(self) -> str:
        """Return the latest serialized frame payload."""
        return self._latest_frame

    def get_latest_payload(self) -> FramePayload:
        """Return the latest frame payload as a dataclass instance."""
        return self._latest_payload

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_arrows(self) -> Dict[str, Any]:
        points = getattr(self, "_arrow_points", None)
        if points is None or points.size == 0:
            return {"count": 0, "points": [], "colors": [], "directions": [], "base_size": 1.0}
        n = points.shape[0]
        base_size = 1.0
        if self.voxsym.voxels:
            try:
                base_size = float(self.voxsym.voxels[0].size * self.render_scale)
            except Exception:
                base_size = 1.0
        directions = getattr(self, "_arrow_directions", None)
        if directions is None or directions.size == 0:
            directions = np.zeros((n, 3), dtype=np.float32)
        return {
            "count": int(n),
            "points": points.reshape(n, 6).tolist(),
            "colors": self._arrow_colors.reshape(n, 3).tolist(),
            "directions": directions.reshape(n, 3).tolist(),
            "base_size": base_size,
        }

    def _active_layers(self) -> List[str]:
        visualizer = getattr(self.voxsym, "_visualizer", None)
        if visualizer is None:
            return ["voxel_color"]
        return sorted(getattr(visualizer, "_active", {"voxel_color"}))
