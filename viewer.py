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
        help="Port for the WebGL viewer server (default: 8080)",
    )
    parser.add_argument(
        "--host", type=str, default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)",
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
        player = Player(data, port=args.port, host=args.host)
    else:
        player = Player(port=args.port, host=args.host)

    print(f"Viewer open at http://{args.host}:{args.port}")
    if args.file is None:
        print("Drag & drop or use the browser upload zone to load a recording.")
    print("Controls: ▶ Play / ⏸ Pause / ⏹ Stop / Timeline / Speed")

    while True:
        player.render()
        time.sleep(0.05)


if __name__ == "__main__":
    main()
