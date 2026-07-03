"""Standard GUI panels and callbacks for VoxSym visualization.

VoxSymGUI is the dedicated callback owner — all button clicks and
slider reads live here, not in the main loop.
"""

import io
import os
import asyncio

import numpy as np
import viser
from voxsym.visualization.visualizer import Layer


class VoxSymGUI:
    """Creates and manages standard GUI controls for a VoxSym instance.

    Provides
    --------
    * Layer toggle buttons (E-field, B-field, Ion conc, Temperature,
      Material, Base colours)
    * Cross-section controls (axis dropdown + position slider)
    * Global opacity slider

    All callbacks are methods of this class.  The main loop only needs
    to call ``voxsym.render()`` — the GUI state is read automatically
    via ``sync()``.
    """

    def __init__(self, voxsym, server: viser.ViserServer):
        self.voxsym = voxsym
        self.server = server
        self._opacity_value = 1.0

        # Compute grid bounds for slider ranges
        min_val, max_val, step = self._compute_bounds()
        self._bounds_min = min_val
        self._bounds_max = max_val
        self._bounds_step = step

        # Create all GUI elements
        self._create_simulation_controls()
        self._create_playback_controls()
        self._create_recording_controls()
        self._create_layer_buttons()
        self._create_cross_section()
        self._create_opacity()

    # ------------------------------------------------------------------
    # Bounds computation
    # ------------------------------------------------------------------

    def _compute_bounds(self):
        """Return (min, max, step) from the voxel grid for slider ranges."""
        voxels = self.voxsym.voxels
        if not voxels:
            return (-5.0, 5.0, 1.0)
        xs = [v.x for v in voxels]
        ys = [v.y for v in voxels]
        zs = [v.z for v in voxels]
        min_val = min(min(xs), min(ys), min(zs))
        max_val = max(max(xs), max(ys), max(zs))
        step = float(voxels[0].size) if voxels else 1.0
        # Subtract one step so the slider doesn't go past the last voxel
        return min_val, max_val - step, step

    # ------------------------------------------------------------------
    # GUI creation
    # ------------------------------------------------------------------

    def _create_layer_buttons(self):
        with self.server.gui.add_folder("Visualization Layers"):
            self._ef_btn = self.server.gui.add_button("Toggle E-field")
            self._bf_btn = self.server.gui.add_button("Toggle B-field")
            self._curr_btn = self.server.gui.add_button("Toggle Current")
            self._ion_btn = self.server.gui.add_button("Toggle Ion Conc")
            self._temp_btn = self.server.gui.add_button("Toggle Temperature")
            self._mat_btn = self.server.gui.add_button("Toggle Material")
            self._base_btn = self.server.gui.add_button("Base colours")

        # ---- Callbacks (all methods of this class) ----

        @self._ef_btn.on_click
        async def _(_):
            self.voxsym.toggle_layer(Layer.ELECTRIC_FIELD)

        @self._bf_btn.on_click
        async def _(_):
            self.voxsym.toggle_layer(Layer.MAGNETIC_FIELD)

        @self._curr_btn.on_click
        async def _(_):
            self.voxsym.toggle_layer(Layer.CURRENT)

        @self._ion_btn.on_click
        async def _(_):
            self.voxsym.toggle_layer(Layer.ION_CONCENTRATION)

        @self._temp_btn.on_click
        async def _(_):
            self.voxsym.toggle_layer(Layer.TEMPERATURE)

        @self._mat_btn.on_click
        async def _(_):
            self.voxsym.toggle_layer(Layer.MATERIAL)

        @self._base_btn.on_click
        async def _(_):
            self.voxsym.reset_layers()

    def _create_simulation_controls(self):
        with self.server.gui.add_folder("Simulation Control"):
            self._play_btn = self.server.gui.add_button("▶ Play")
            self._pause_btn = self.server.gui.add_button("⏸ Pause")
            self._stop_btn = self.server.gui.add_button("⏹ Stop")
            self._reset_btn = self.server.gui.add_button("↺ Reset")
            self._sim_status = self.server.gui.add_markdown("**Paused**")

        @self._play_btn.on_click
        async def _(_):
            self.voxsym.play()
            self._sim_status.content = "**Running**"

        @self._pause_btn.on_click
        async def _(_):
            self.voxsym.pause()
            self._sim_status.content = "**Paused**"

        @self._stop_btn.on_click
        async def _(_):
            self.voxsym.stop()
            self._sim_status.content = "**Stopped**"

        @self._reset_btn.on_click
        async def _(_):
            vs = self.voxsym
            vs.reset_to_initial()
            vs.reset_simulation()
            self._sim_status.content = "**Paused**"

    def _create_recording_controls(self):
        # Skip the recording folder entirely if recording is disabled.
        if not getattr(self.voxsym, "_recording_enabled", True):
            return

        with self.server.gui.add_folder("Recording / Playback"):
            self._record_btn = self.server.gui.add_button("⏺ Record")
            self._load_sim_btn = self.server.gui.add_upload_button(
                "Load Simulation",
                hint="Load a recorded .npz or .csv simulation",
            )
            self._load_status = self.server.gui.add_markdown(
                "Upload .npz / .csv to replay"
            )
            self._save_btn = self.server.gui.add_button("💾 Save")
            self._save_status = self.server.gui.add_markdown("")

        @self._record_btn.on_click
        async def _(_):
            vs = self.voxsym
            if vs._recorder is not None:
                vs.stop_recording()
                self._record_btn.label = "⏺ Record"
            else:
                vs.start_recording()
                self._record_btn.label = "⏹ Stop Recording"

        @self._load_sim_btn.on_upload
        async def _(event):
            try:
                from voxsym.io.recorder import Recorder
                uploaded = event.target.value
                print(f"[upload] file={uploaded.name if uploaded else 'None'}")
                if uploaded is None or not uploaded.name:
                    self._load_status.content = "**No file selected.**"
                    return

                name = uploaded.name.lower()
                content = uploaded.content
                print(f"[upload] name={name}, size={len(content)} bytes")

                self._load_status.content = "📂 **Reading file…**"

                def _read():
                    if name.endswith(".npz"):
                        import io, numpy as np
                        return np.load(io.BytesIO(content), allow_pickle=False)
                    elif name.endswith(".csv"):
                        return Recorder.from_csv(content)
                    else:
                        raise ValueError(f"Unsupported file: {uploaded.name}")

                # Run parsing / loading in a background thread so the GUI
                # event loop stays responsive during big uploads.
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, _read)

                await loop.run_in_executor(
                    None, self.voxsym.load_simulation, data, False
                )

                print(
                    f"[upload] loaded: {self.voxsym._playback_num_frames} frames, "
                    f"{self.voxsym._playback_num_voxels} voxels"
                )

                # GUI refresh must run on the event loop.
                self.voxsym._gui._refresh_playback_controls(
                    self.voxsym._playback_num_frames,
                    self.voxsym._playback_current_frame,
                )

                # Start playback immediately after a successful upload.
                self.voxsym.play()
                self._sim_status.content = "**Running**"

                self._load_status.content = (
                    f"**Loaded:** {uploaded.name}\n\n"
                    f"Frames: **{self.voxsym._playback_num_frames}**  —  "
                    f"Voxels: **{self.voxsym._playback_num_voxels}**"
                )
            except Exception as exc:
                import traceback
                traceback.print_exc()
                self._load_status.content = f"**Load error:** {exc}"

        @self._save_btn.on_click
        async def _(_):
            try:
                npz_path, csv_path = self.voxsym.autosave()
                if npz_path is None:
                    self._save_status.content = "No frames recorded yet."
                    return
                self._save_status.content = (
                    f"Saved:\n"
                    f"• `{os.path.basename(npz_path)}`\n"
                    f"• `{os.path.basename(csv_path)}`"
                )
            except Exception as exc:
                self._save_status.content = f"**Save error:** {exc}"

    def _create_playback_controls(self):
        self._playback_folder = self.server.gui.add_folder("Playback")
        with self._playback_folder:
            self._playback_status = self.server.gui.add_markdown(
                "No simulation loaded"
            )
            self._playback_timeline = self.server.gui.add_slider(
                "Frame",
                min=0,
                max=0,
                step=1,
                initial_value=0,
            )
            self._playback_speed = self.server.gui.add_slider(
                "Speed",
                min=0.1,
                max=10.0,
                step=0.1,
                initial_value=1.0,
            )
            self._playback_step_back = self.server.gui.add_button("◀ Step")
            self._playback_step_fwd = self.server.gui.add_button("Step ▶")

        @self._playback_speed.on_update
        def _(_):
            self.voxsym._playback_speed_value = self._playback_speed.value

        @self._playback_timeline.on_update
        def _(_):
            if (
                not self.voxsym._playback_playing
                and self.voxsym._playback_num_frames > 0
            ):
                idx = int(np.clip(
                    self._playback_timeline.value,
                    0,
                    self.voxsym._playback_num_frames - 1,
                ))
                self.voxsym._apply_playback_frame(idx)
                self._sync_playback_frame(
                    idx,
                    self.voxsym._playback_num_frames,
                    float(self.voxsym._playback_data["times"][idx])
                    if self.voxsym._playback_data is not None
                    else 0.0,
                )

        @self._playback_step_back.on_click
        async def _(_):
            idx = max(0, self.voxsym._playback_current_frame - 1)
            self.voxsym._playback_playing = False
            self.voxsym._playback_frame_accum = 0.0
            self.voxsym._apply_playback_frame(idx)

        @self._playback_step_fwd.on_click
        async def _(_):
            idx = min(
                self.voxsym._playback_num_frames - 1,
                self.voxsym._playback_current_frame + 1,
            )
            self.voxsym._playback_playing = False
            self.voxsym._playback_frame_accum = 0.0
            self.voxsym._apply_playback_frame(idx)

    def _refresh_playback_controls(self, num_frames: int, current_frame: int):
        """Update playback slider range after a simulation is loaded."""
        max_frame = max(0, num_frames - 1)
        print(
            f"[_refresh_playback_controls] num_frames={num_frames}, "
            f"current_frame={current_frame}, max_frame={max_frame}"
        )
        # Remove old slider and create a new one with the correct max.
        # viser slider handles don't expose a writable ``max`` property,
        # so we must recreate the element.
        self._playback_timeline.remove()
        with self._playback_folder:
            self._playback_timeline = self.server.gui.add_slider(
                "Frame",
                min=0,
                max=max_frame,
                step=1,
                initial_value=min(current_frame, max_frame),
            )

        @self._playback_timeline.on_update
        def _(_):
            if (
                not self.voxsym._playback_playing
                and self.voxsym._playback_num_frames > 0
            ):
                idx = int(np.clip(
                    self._playback_timeline.value,
                    0,
                    self.voxsym._playback_num_frames - 1,
                ))
                self.voxsym._apply_playback_frame(idx)
                self._sync_playback_frame(
                    idx,
                    self.voxsym._playback_num_frames,
                    float(self.voxsym._playback_data["times"][idx])
                    if self.voxsym._playback_data is not None
                    else 0.0,
                )

        self._sync_playback_frame(
            current_frame,
            num_frames,
            float(self.voxsym._playback_data["times"][current_frame])
            if self.voxsym._playback_data is not None
            else 0.0,
        )

    def _sync_playback_frame(self, idx: int, num_frames: int, t: float):
        """Update the playback status markdown and slider position."""
        print(f"[_sync_playback_frame] idx={idx}, num_frames={num_frames}, t={t}")
        if num_frames == 0:
            self._playback_status.content = "No simulation loaded"
            return
        self._playback_status.content = (
            f"Frame **{idx + 1}** / {num_frames}  —  "
            f"t = **{self.voxsym._fmt_time(t)}**"
        )
        self._playback_timeline.value = idx

    def _create_cross_section(self):
        with self.server.gui.add_folder("Cross Section"):
            self._cs_axis_dd = self.server.gui.add_dropdown(
                "Axis", options=("off", "x", "y", "z"), initial_value="off",
            )
            self._cs_pos_slider = self.server.gui.add_slider(
                "Position",
                min=self._bounds_min,
                max=self._bounds_max,
                step=self._bounds_step,
                initial_value=0.0,
            )

    def _create_opacity(self):
        self._opacity_slider = self.server.gui.add_slider(
            "Global opacity", min=0.0, max=1.0, step=0.01, initial_value=1.0,
        )

    # ------------------------------------------------------------------
    # Sync  (read GUI state → apply to visualizer)
    # ------------------------------------------------------------------

    def sync(self):
        """Read all GUI control values and apply them to the visualizer.

        Called automatically by ``VoxSym.render()`` — the user does not
        need to invoke this manually.
        """
        viz = self.voxsym._visualizer
        if viz is None:
            return

        # Cross-section
        axis_val = self._cs_axis_dd.value
        viz.cross_section_axis = None if axis_val == "off" else axis_val
        viz.cross_section_pos = self._cs_pos_slider.value

        # Opacity (stored, applied by VoxSym.render)
        self._opacity_value = self._opacity_slider.value

    @property
    def opacity(self) -> float:
        """Current global opacity value (0–1)."""
        return self._opacity_value

    def set_opacity(self, value: float):
        """Programmatically set the opacity slider value."""
        self._opacity_slider.value = float(value)
        self._opacity_value = float(value)
