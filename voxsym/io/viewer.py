#!/usr/bin/env python3
"""
Simulation viewer — upload and replay .npz / .csv recordings.

Usage::

    python viewer.py                # empty viewer, upload in browser
    python viewer.py sim.npz        # preload a recording
    python viewer.py sim.csv        # preload a CSV export
    python viewer.py --port 9000    # use a different port
"""

import argparse
import os
import time

from voxsym.io.player import Player
from voxsym.io.recorder import Recorder


def main():
    parser = argparse.ArgumentParser(
        description="Visualize a recorded VoxSym simulation.",
    )
    parser.add_argument(
        "file", nargs="?", default=None,
        help="Optional .npz or .csv simulation file to preload",
    )
    parser.add_argument(
        "--port", type=int, default=8080,
        help="Port for the viser viewer server (default: 8080)",
    )
    args = parser.parse_args()

    if args.file is not None:
        ext = os.path.splitext(args.file)[1].lower()
        if ext == ".csv":
            data = Recorder.from_csv(args.file)
        elif ext == ".npz":
            data = Recorder.load(args.file)
        else:
            raise ValueError(f"Unsupported file extension '{ext}'. Use .npz or .csv")
        player = Player(data, port=args.port)
    else:
        player = Player(port=args.port)

    print(f"Viewer open at http://localhost:{args.port}")
    if args.file is None:
        print("Drag & drop or click 'Upload .npz / .csv' in the browser.")
    print("Controls: ▶ Play / ⏸ Pause / ⏹ Stop / ◀▶ Step / Timeline / Speed")
    print("Click any voxel in the scene to inspect its values.")

    while True:
        player.render()
        time.sleep(0.05)


if __name__ == "__main__":
    main()
