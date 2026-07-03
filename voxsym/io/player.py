"""
Simulation player — replay recorded voxel simulations with GUI controls.

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


def _ray_box_intersect(ray_origin, ray_direction, center, half_size):
    """Return the entry distance for a ray vs axis-aligned box, or None."""
    t_min = -np.inf
    t_max = np.inf
    for i in range(3):
        d = ray_direction[i]
        o = ray_origin[i]
        c = center[i]
        h = half_size[i]
        if abs(d) < 1e-12:
            if abs(o - c) > h:
                return None
            continue
        t1 = (c - h - o) / d
        t2 = (c + h - o) / d
        if t1 > t2:
            t1, t2 = t2, t1
        t_min = max(t_min, t1)
        t_max = min(t_max, t2)
        if t_min > t_max:
            return None
    if t_max < 0:
        return None
    return t_min if t_min >= 0 else t_max


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

        # Build voxsym (server is created here)
        # Disable nested recorder/player; this window only visualizes.
        self.voxsym = VoxSym(port=port, enable_recorder=False, enable_player=False)

        # Register click-to-inspect before creating GUI callbacks
        self._register_click_handler()

        # Create playback GUI (handles are created even when empty)
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
        self._timeline.min = 0
        self._timeline.max = max(0, self._num_frames - 1)
        self._timeline.value = 0

        # Apply initial frame
        self._apply_frame(0)
        self._update_inspector()

    def _show_empty_state(self):
        """Display instructions before any data is loaded."""
        self._num_frames = 0
        self._num_voxels = 0
        self._timeline.min = 0
        self._timeline.max = 0
        self._timeline.value = 0
        self._frame_label.content = "No simulation loaded — upload .npz or .csv"
        self._voxel_info.content = "Upload a simulation file to begin"

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
    # Click-to-inspect
    # ------------------------------------------------------------------

    def _register_click_handler(self):
        @self.voxsym.server.scene.on_click()
        def _(event):
            self._on_scene_click(event)

    def _on_scene_click(self, event):
        """Find the closest voxel hit by the click ray."""
        if self._num_voxels == 0:
            return

        origin = np.array(event.ray_origin, dtype=float)
        direction = np.array(event.ray_direction, dtype=float)
        norm = np.linalg.norm(direction)
        if norm < 1e-12:
            return
        direction /= norm

        scl = self.voxsym.render_scale
        best_idx = None
        best_t = np.inf

        voxels = self.voxsym.get_voxels()
        for i, v in enumerate(voxels):
            center = np.array([v.x * scl, v.y * scl, v.z * scl], dtype=float)
            half_size = np.full(3, v.size * scl * 0.5, dtype=float)
            t = _ray_box_intersect(origin, direction, center, half_size)
            if t is not None and t < best_t:
                best_t = t
                best_idx = i

        if best_idx is not None:
            self._selected_voxel = best_idx
            self._update_inspector()

    # ------------------------------------------------------------------
    # GUI
    # ------------------------------------------------------------------

    def _create_gui(self):
        with self.voxsym.server.gui.add_folder("Upload"):
            self._upload_btn = self.voxsym.server.gui.add_upload_button(
                "Upload .npz / .csv",
                mime_type=".npz,.csv",
                hint="Load a recorded simulation",
            )
            self._upload_status = self.voxsym.server.gui.add_markdown(
                "Drag & drop or click to upload"
            )

        with self.voxsym.server.gui.add_folder("Playback"):
            self._play_btn = self.voxsym.server.gui.add_button(
                "⏸ Pause" if self._playing else "▶ Play"
            )
            self._stop_btn = self.voxsym.server.gui.add_button("⏹ Stop")
            self._step_back_btn = self.voxsym.server.gui.add_button("◀ Step")
            self._step_fwd_btn = self.voxsym.server.gui.add_button("Step ▶")
            self._timeline = self.voxsym.server.gui.add_slider(
                "Frame",
                min=0,
                max=0,
                step=1,
                initial_value=0,
            )
            self._speed_slider = self.voxsym.server.gui.add_slider(
                "Speed",
                min=0.1,
                max=10.0,
                step=0.1,
                initial_value=1.0,
            )
            self._frame_label = self.voxsym.server.gui.add_markdown("")

        with self.voxsym.server.gui.add_folder("Voxel Inspector"):
            self._voxel_info = self.voxsym.server.gui.add_markdown(
                "Click a voxel to inspect"
            )

        # Callbacks
        @self._upload_btn.on_upload
        def _(event):
            self._on_upload(event)

        @self._play_btn.on_click
        def _(_):
            self._playing = not self._playing
            self._play_btn.label = "⏸ Pause" if self._playing else "▶ Play"

        @self._stop_btn.on_click
        def _(_):
            self._playing = False
            self._play_btn.label = "▶ Play"
            self.goto_frame(0)
            self._frame_accum = 0.0

        @self._step_back_btn.on_click
        def _(_):
            self._playing = False
            self._play_btn.label = "▶ Play"
            self._frame_accum = 0.0
            self.current_frame = max(0, self.current_frame - 1)
            self._apply_frame(self.current_frame)

        @self._step_fwd_btn.on_click
        def _(_):
            self._playing = False
            self._play_btn.label = "▶ Play"
            self._frame_accum = 0.0
            self.current_frame = min(self._num_frames - 1, self.current_frame + 1)
            self._apply_frame(self.current_frame)

        @self._timeline.on_update
        def _(_):
            if not self._playing and self._num_frames > 0:
                self._frame_accum = 0.0
                self.current_frame = int(np.clip(
                    self._timeline.value, 0, self._num_frames - 1
                ))
                self._apply_frame(self.current_frame)

    def _on_upload(self, event):
        """Handle an uploaded .npz or .csv file."""
        from voxsym.io.recorder import Recorder

        uploaded = event.target.value
        if uploaded is None:
            return

        name = uploaded.name.lower()
        content = uploaded.content

        try:
            if name.endswith(".npz"):
                # viser uploads give bytes; numpy can load from BytesIO
                data = np.load(io.BytesIO(content), allow_pickle=False)
            elif name.endswith(".csv"):
                data = Recorder.from_csv(content)
            else:
                self._upload_status.content = (
                    f"**Unsupported file:** {uploaded.name}\n\n"
                    "Please upload a `.npz` or `.csv` simulation file."
                )
                return

            self._load_data(data)
            self._upload_status.content = (
                f"**Loaded:** {uploaded.name}\n\n"
                f"Frames: **{self._num_frames}**  —  Voxels: **{self._num_voxels}**"
            )
        except Exception as exc:
            self._upload_status.content = (
                f"**Failed to load {uploaded.name}**\n\n"
                f"```\n{exc}\n```"
            )

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

        t = float(data["times"][idx])
        self._frame_label.content = (
            f"Frame **{idx + 1}** / {self._num_frames}  —  "
            f"t = **{_fmt_time(t)}**"
        )
        self._timeline.value = idx

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self):
        """Advance playback and render the current frame."""
        now = time.perf_counter()
        dt_real = now - self._last_step_time
        self._last_step_time = now

        if self._playing and self._num_frames > 0:
            self._play_speed = self._speed_slider.value
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
                self._play_btn.label = "▶ Play"

        self.voxsym.render()

        # Only update inspector text when something is selected
        if self._selected_voxel is not None:
            self._update_inspector()

    # ------------------------------------------------------------------
    # Voxel inspector
    # ------------------------------------------------------------------

    def _update_inspector(self):
        """Show properties of the currently selected voxel."""
        idx = self._selected_voxel
        if idx is None:
            self._voxel_info.content = "Click a voxel to inspect"
            return
        if idx < 0 or idx >= self._num_voxels:
            return

        v = self.voxsym.get_voxels()[idx]
        mat_name = v.material.name if v.material else "none"
        ef = v.electric_field
        bf = v.magnetic_field
        cd = v.current_density
        pol = v.polarization
        mag = v.magnetization

        self._voxel_info.content = (
            f"**Voxel #{idx}**  ({v.x:.2e}, {v.y:.2e}, {v.z:.2e})\n\n"
            f"Material: **{mat_name}**\n"
            f"Size: **{v.size:.2e} m**\n"
            f"Temperature: **{v.temperature:.1f} K**\n"
            f"Pressure: **{v.pressure:.2f} Pa**\n"
            f"Ion conc: **{v.ion_concentration:.2f} mol/m³**\n"
            f"Charge: **{v.charge:.2e} C**\n"
            f"E-field: **({ef[0]:.2e}, {ef[1]:.2e}, {ef[2]:.2e}) V/m**\n"
            f"B-field: **({bf[0]:.2e}, {bf[1]:.2e}, {bf[2]:.2e}) T**\n"
            f"Current J: **({cd[0]:.2e}, {cd[1]:.2e}, {cd[2]:.2e}) A/m²**\n"
            f"Polarization: **({pol[0]:.2e}, {pol[1]:.2e}, {pol[2]:.2e}) C/m²**\n"
            f"Magnetization: **({mag[0]:.2e}, {mag[1]:.2e}, {mag[2]:.2e}) A/m**"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def goto_frame(self, idx: int):
        """Jump to a specific frame."""
        self._playing = False
        self._play_btn.label = "▶ Play"
        self._frame_accum = 0.0
        self._apply_frame(idx)

    def play(self):
        self._playing = True
        self._play_btn.label = "⏸ Pause"

    def pause(self):
        self._playing = False
        self._play_btn.label = "▶ Play"


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
        help="Port for the viser playback server (default: 8080)",
    )
    args = parser.parse_args()

    if args.npz is not None:
        ext = os.path.splitext(args.npz)[1].lower()
        if ext == ".csv":
            data = Recorder.from_csv(args.npz)
        else:
            data = Recorder.load(args.npz)
        player = Player(data, port=args.port)
    else:
        player = Player(port=args.port)

    print(f"Playback open at http://localhost:{args.port}")
    if args.npz is None:
        print("Upload a .npz or .csv simulation file in the browser.")
    print("Controls: ▶ Play / ⏸ Pause / ⏹ Stop / ◀▶ Step / Timeline / Speed")
    print("Click any voxel in the scene to inspect its values.")

    while True:
        player.render()
        time.sleep(0.05)


if __name__ == "__main__":
    main()
