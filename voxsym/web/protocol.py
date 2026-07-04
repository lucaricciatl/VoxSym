"""JSON wire protocol for the VoxSym WebGL streaming server."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FramePayload:
    """Server → client frame message."""

    type: str = "frame"
    time: float = 0.0
    frame_index: int = 0
    opacity: float = 1.0
    playing: bool = True
    voxels: Dict[str, Any] = field(default_factory=dict)
    arrows: Dict[str, Any] = field(default_factory=dict)
    active_layers: List[str] = field(default_factory=lambda: ["voxel_color"])

    @classmethod
    def empty(cls, time: float = 0.0) -> "FramePayload":
        return cls(
            type="frame",
            time=time,
            frame_index=0,
            opacity=1.0,
            playing=True,
            voxels={"count": 0, "positions": [], "sizes": [], "colors": [], "opacities": []},
            arrows={"count": 0, "points": [], "colors": [], "base_size": 1.0},
            active_layers=["voxel_color"],
        )

    def encode(self) -> str:
        """Serialize to a JSON string suitable for WebSocket text frames."""
        return json.dumps(asdict(self))

    @classmethod
    def decode(cls, data: str) -> "FramePayload":
        """Parse a JSON frame payload."""
        obj = json.loads(data)
        return cls(
            type=obj.get("type", "frame"),
            time=obj.get("time", 0.0),
            frame_index=obj.get("frame_index", 0),
            playing=obj.get("playing", True),
            voxels=obj.get("voxels", {}),
            arrows=obj.get("arrows", {}),
            active_layers=obj.get("active_layers", ["voxel_color"]),
        )


@dataclass
class CommandPayload:
    """Client → server control command.

    Supported commands:
        play|pause|reset|stop
        set_layer {layer, active}
        set_opacity {value}
        set_cross_section {axis, pos}
        set_arrow_scale {value}
        set_time_scale {value}
        seek {frame}
        playback {filename}
    """

    cmd: str
    layer: Optional[str] = None
    active: Optional[bool] = None
    value: Optional[float] = None
    axis: Optional[str] = None
    pos: Optional[float] = None
    frame: Optional[int] = None
    filename: Optional[str] = None

    @classmethod
    def decode(cls, data: str) -> "CommandPayload":
        obj = json.loads(data)
        return cls(
            cmd=obj.get("cmd", ""),
            layer=obj.get("layer"),
            active=obj.get("active"),
            value=obj.get("value"),
            axis=obj.get("axis"),
            pos=obj.get("pos"),
            frame=obj.get("frame"),
            filename=obj.get("filename"),
        )

    def encode(self) -> str:
        return json.dumps({k: v for k, v in asdict(self).items() if v is not None})
