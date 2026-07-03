"""
11 — Viewer: upload and inspect any recording
===============================================
Start an empty viewer and upload a `.npz` or `.csv` simulation file
through the web GUI.  The viewer supports play/pause/stop, timeline
scrubbing, speed control, and click-to-inspect on any voxel.

You can also preload a file from the command line::

    python examples/11_viewer.py my_simulation.npz
    python examples/11_viewer.py my_simulation.csv
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
from voxsym.io.viewer import main

if __name__ == "__main__":
    main()
    # main() contains its own render loop, so we never reach here.