"""
Simulation player — replay recorded voxel simulations with WebGL viewer.

Provides play/pause/stop, step forward/backward, timeline scrubbing,
speed control, per-voxel inspection on click, and drag-and-drop upload
of both .npz and .csv simulation files.
"""

import io
import os
import time
import numpy as np
from typing import Optional
from voxsym.voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import MATERIALS


def _fmt_time(t: float) -> str:
    if t >= 1.0:
        return f"{t:.3f} s"
    elif t >= 1e-3:
        return f"{t * 1e3:.2f} ms"
    elif t >= 1e-6:
        return f"{t * 1e6:.2f} µs"
    else:
        return f"{t * 1e9:.2f} ns"


def _decode_name(name) -> str:
    """Handle both str and bytes stored in .npz arrays."""
    if isinstance(name, bytes):
        return name.decode("utf-8")
    return str(name)


def _material_color(name: str) -> tuple[int, int, int]:
    name = _decode_name(name)
    if name in MATERIALS:
        return tuple(int(c) for c in MATERIALS[name].color)
    return (200, 200, 200)


class Player:
    """Replay a recorded simulation with interactive controls.

    Accepts either a pre-loaded data dict, or ``None`` to start an empty
    viewer and upload a simulation through the web GUI.

    Usage::

        data = Recorder.load("simulation.npz")
        player = Player(data)
        while True:
            player.render()
            time.sleep(0.05)

    Empty viewer::

        player = Player()  # upload .npz or .csv in the browser
    """

    def __init__(
        self,
        data: Optional[dict[str, np.ndarray]] = None,
        port: int = 8080,
        host: str = "0.0.0.0",
    ):
        self._empty_data = data is None

        # Internal state
        self._data: dict[str, np.ndarray] = {}
        self._num_frames = 0
        self._num_voxels = 0

        self.current_frame = 0
        self._playing = False
        self._play_speed = 1.0
        self._frame_accum = 0.0
        self._last_step_time = 0.0
        self._selected_voxel: int | None = None

        # Build voxsym with the WebGL backend.
        # Disable nested recorder/player; this window only visualizes.
        self.voxsym = VoxSym(port=port, host=host, enable_recorder=False, enable_player=False)

        # Create playback GUI handles (no-op on WebGL, but kept for compatibility).
        self._create_gui()

        # Load initial data if provided
        if data is not None:
            self._load_data(data)
        else:
            self._show_empty_state()

    # ------------------------------------------------------------------
    # Data loading / reloading
    # ------------------------------------------------------------------

    def _load_data(self, data: dict[str, np.ndarray]):
        """Replace the current simulation data and rebuild voxels."""
        self._data = data
        self._num_frames = len(data["times"])
        self._num_voxels = len(data["positions"])

        # Reset player state
        self.current_frame = 0
        self._playing = False
        self._frame_accum = 0.0
        self._selected_voxel = None

        # Rebuild voxel grid
        self.voxsym.voxels.clear()
        self._build_voxels()

        # Initialize standard VoxSym GUI (layers, cross-section, opacity)
        # on first load.  The renderer and visualizer are created here.
        if self.voxsym._gui is None:
            self.voxsym.setup_gui()

        # Frame the grid for newly-connecting clients.
        self.voxsym.auto_camera()

        # Reset renderer so batched mesh is recreated with correct size
        if self.voxsym._renderer is not None:
            if self.voxsym._renderer.handle is not None:
                try:
                    self.voxsym._renderer.handle.remove()
                except Exception:
                    pass
            self.voxsym._renderer._handle = None

        # Reset visualizer overlays if any exist
        if self.voxsym._visualizer is not None:
            self.voxsym._visualizer.remove_all_overlays()

        # Update timeline range
        self._timeline_min = 0
        self._timeline_max = max(0, self._num_frames - 1)

        # Apply initial frame
        self._apply_frame(0)

    def _show_empty_state(self):
        """Display instructions before any data is loaded."""
        self._num_frames = 0
        self._num_voxels = 0
        self._timeline_min = 0
        self._timeline_max = 0

    # ------------------------------------------------------------------
    # Build voxels from recorded data
    # ------------------------------------------------------------------

    def _build_voxels(self):
        positions = self._data["positions"]
        sizes = self._data["sizes"]
        colors = self._data["colors"]
        mat_names = self._data["material_names"]

        for i in range(self._num_voxels):
            v = Voxel(
                x=float(positions[i, 0]),
                y=float(positions[i, 1]),
                z=float(positions[i, 2]),
                size=float(sizes[i]),
                color=tuple(int(c) for c in colors[i]),
            )
            name = _decode_name(mat_names[i])
            if name in MATERIALS:
                v.material = MATERIALS[name]
            self.voxsym.add_voxel(v)

    # ------------------------------------------------------------------
    # GUI
    # ------------------------------------------------------------------

    def _create_gui(self):
        # Browser-side controls are used instead of Python-side GUI panels.
        # Keep simple state attributes for backwards compatibility.
        self._timeline_min = 0
        self._timeline_max = 0
        self._timeline_value = 0

    # ------------------------------------------------------------------
    # Frame application
    # ------------------------------------------------------------------

    def _apply_frame(self, idx: int):
        """Write frame *idx* data into all voxels."""
        if self._num_frames == 0:
            return

        idx = max(0, min(self._num_frames - 1, idx))
        self.current_frame = idx

        voxels = self.voxsym.get_voxels()
        data = self._data

        def _get_array(name: str):
            return data.get(name)

        for i, v in enumerate(voxels):
            v.temperature = float(data["temperatures"][idx, i])
            v.ion_concentration = float(data["ion_concentrations"][idx, i])
            v.electric_field = data["electric_fields"][idx, i].copy()
            v.magnetic_field = data["magnetic_fields"][idx, i].copy()
            v.current_density = data["current_densities"][idx, i].copy()

            # Backwards-compatible optional fields
            pressures = _get_array("pressures")
            if pressures is not None:
                v.pressure = float(pressures[idx, i])

            charges = _get_array("charges")
            if charges is not None:
                v.charge = float(charges[idx, i])

            polarizations = _get_array("polarizations")
            if polarizations is not None:
                v.polarization = polarizations[idx, i].copy()

            magnetizations = _get_array("magnetizations")
            if magnetizations is not None:
                v.magnetization = magnetizations[idx, i].copy()

            interface_concentrations = _get_array("interface_concentrations")
            if interface_concentrations is not None:
                v.interface_concentration = float(interface_concentrations[idx, i])

            displacements = _get_array("displacements")
            if displacements is not None:
                v.displacement = displacements[idx, i].copy()

            velocities = _get_array("velocities")
            if velocities is not None:
                v.velocity = velocities[idx, i].copy()

            stresses = _get_array("stresses")
            if stresses is not None:
                v.stress = stresses[idx, i].copy()

            optical_intensities = _get_array("optical_intensities")
            if optical_intensities is not None:
                v.optical_intensity = float(optical_intensities[idx, i])

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self):
        """Advance playback and render the current frame."""
        now = time.perf_counter()
        dt_real = now - self._last_step_time
        self._last_step_time = now

        if self._playing and self._num_frames > 0:
            self._play_speed = self._play_speed
            # Use an accumulator so fractional speeds (e.g. 0.25x) work smoothly.
            self._frame_accum += self._play_speed
            advance = int(self._frame_accum)
            self._frame_accum -= advance
            self.current_frame = min(
                self._num_frames - 1,
                self.current_frame + advance,
            )
            self._apply_frame(self.current_frame)
            if self.current_frame >= self._num_frames - 1:
                self._playing = False

        self.voxsym.render()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def goto_frame(self, idx: int):
        """Jump to a specific frame."""
        self._playing = False
        self._frame_accum = 0.0
        self._apply_frame(idx)

    def play(self):
        self._playing = True

    def pause(self):
        self._playing = False


# ----------------------------------------------------------------------
# CLI:  python player.py [simulation.npz] [--port 8080]
# ----------------------------------------------------------------------

def main():
    import argparse

    from voxsym.io.recorder import Recorder

    parser = argparse.ArgumentParser(
        description="Replay a recorded VoxSym simulation.",
    )
    parser.add_argument(
        "npz", nargs="?", default=None,
        help="Optional path to a simulation .npz or .csv file",
    )
    parser.add_argument(
        "--port", type=int, default=8080,
        help="Port for the WebGL playback server (default: 8080)",
    )
    parser.add_argument(
        "--host", type=str, default="0.0.0.0",
        help="Host to bind the playback server to (default: 0.0.0.0)",
    )
    args = parser.parse_args()

    if args.npz is not None:
        ext = os.path.splitext(args.npz)[1].lower()
        if ext == ".csv":
            data = Recorder.from_csv(args.npz)
        else:
            data = Recorder.load(args.npz)
        player = Player(data, port=args.port, host=args.host)
    else:
        player = Player(port=args.port, host=args.host)

    print(f"Playback open at http://{args.host}:{args.port}")
    if args.npz is None:
        print("Upload a .npz or .csv simulation file in the browser.")
    print("Controls: ▶ Play / ⏸ Pause / ⏹ Stop / ◀▶ Step / Timeline / Speed")

    while True:
        player.render()
        time.sleep(0.05)


if __name__ == "__main__":
    main()
