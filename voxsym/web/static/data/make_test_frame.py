#!/usr/bin/env python3
"""Generate a small 3x3x3 test JSON frame for the WebGL viewer."""
import json
from pathlib import Path

out = Path(__file__).resolve().parent / "test_frame.json"

voxels = []
for x in range(-1, 2):
    for y in range(-1, 2):
        for z in range(-1, 2):
            voxels.append({
                "x": float(x),
                "y": float(y),
                "z": float(z),
                "size": 0.9,
                "r": int(128 + x * 40),
                "g": int(128 + y * 40),
                "b": int(128 + z * 40),
                "a": 0.9,
            })

payload = {
    "type": "frame",
    "time": 0.0,
    "count": len(voxels),
    "opacity": 0.9,
    "voxels": voxels,
}

out.write_text(json.dumps(payload, indent=2))
print(f"wrote {out}")
