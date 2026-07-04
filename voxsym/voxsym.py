import os
import sys
import inspect
import datetime
import time
import threading

import numpy as np
from typing import Optional

from voxsym.physics.topology import GridTopology


def _decode_name(name) -> str:
    """Handle both str and bytes stored in .npz arrays."""
    if isinstance(name, bytes):
        return name.decode("utf-8")
    return str(name)


def _material_color(name: str) -> tuple[int, int, int]:
    """Return a material color from its name, falling back to gray."""
    from voxsym.material import MATERIALS
    name = _decode_name(name)
    if name in MATERIALS:
        return tuple(int(c) for c in MATERIALS[name].color)
    return (200, 200, 200)


class VoxSym:
    """Main class for voxel-based physics simulation and visualization.

    Owns the voxel grid, all physics solvers (heat, ion, EM), the
    optional renderer/visualizer/GUI, and the WebGL server.  The user
    only needs to instantiate this class.

    The render scale is inferred automatically from voxel sizes so
    that nanoscale grids are visible without manual scaling.

    Args:
        port: Port for the internal WebGL server (default 8080).
        host: Host to bind the server to (default "0.0.0.0").
        backend: "webgl" for the browser-based WebGL backend, or None
            for headless simulation (no renderer/GUI). Defaults to "webgl".
        enable_recorder: Whether to enable the simulation recorder.
        enable_player: Whether to enable the legacy external player.
    """

    # Layer name constants (mirror visualizer.Layer for convenience)
    LAYER_VOXEL_COLOR = "voxel_color"
    LAYER_ELECTRIC_FIELD = "electric_field"
    LAYER_MAGNETIC_FIELD = "magnetic_field"
    LAYER_CURRENT = "current"
    LAYER_TEMPERATURE = "temperature"
    LAYER_MATERIAL = "material"
    LAYER_ION_CONCENTRATION = "ion_concentration"

    def __init__(self, port: int = 8080, *, host: str = "0.0.0.0",
                 backend: Optional[str] = "webgl",
                 enable_recorder: bool = True,
                 enable_player: bool = True):
        self.voxels = []
        self.space_resolution = 1.0
        self.time_step = 0.1

        # Explicit time-step safety factor.  ``max_stable_dt()`` returns
        # the raw CFL cap; every call to ``step_and_update(dt)`` compares
        # against ``dt_safety_factor * max_stable_dt()`` and warns/clamps.
        self.dt_safety_factor = 0.5

        # Render scale — auto-computed from voxel sizes on first use.
        # Set manually to override:  vs.render_scale = 1e9
        self._render_scale = None

        # Backend selection (WebGL or headless)
        self._backend_name = backend
        self._server = None
        self._webgl_server = None
        if backend == "viser":
            raise RuntimeError(
                "The Viser backend has been removed. "
                "Use backend='webgl' (default) for the browser-based viewer, "
                "or backend=None for headless simulation."
            )
        elif backend == "webgl":
            try:
                from voxsym.web.server import WebGLServer
                from voxsym.visualization.backends.webgl_backend import WebGLBackend
            except ImportError as exc:
                raise RuntimeError(
                    "WebGL backend requires tornado and websockets. "
                    "Install them with 'pip install tornado websockets'."
                ) from exc
            self._webgl_server = WebGLServer(self, host=host, port=port)
            self._webgl_server.start()
            self._server = self._webgl_server
            self._webgl_backend = WebGLBackend(self, self._webgl_server, self.render_scale)
        elif backend is not None:
            raise ValueError(f"Unknown backend: {backend!r}. Use 'webgl' or None.")

        # Internal components (lazy initialization)
        self._heat_solver = None
        self._ion_solver = None
        self._em_solver = None
        self._poisson_solver = None
        self._renderer = None
        self._visualizer = None
        self._gui = None

        # Poisson solver control
        self._enable_poisson = False

        # Pending simulation state (compute → update two-phase pattern)
        self._pending_temps: Optional[np.ndarray] = None
        self._pending_conc: Optional[np.ndarray] = None
        self._pending_charge: Optional[np.ndarray] = None

        # Recording (on by default)
        self._recorder = None
        self._recording_enabled = enable_recorder
        if enable_recorder:
            from voxsym.io.recorder import Recorder
            self._recorder = Recorder(self)

        # Player (on by default) — lazy-instantiated after the voxel grid
        # is finalized so it can load recorded data.  Uses the next port to
        # avoid conflicting with the main simulation server.
        self._player = None
        self._player_enabled = enable_player
        self._player_port = port + 1
        self._player_data: Optional[dict] = None  # precomputed frames for replay
        self._player_steps_per_frame = 1          # how many sim steps per recorded frame
        self._player_frame_counter = 0

        # Elapsed simulation time (used for recording timestamps)
        self._elapsed_time = 0.0
        self._frame_index = 0

        # Callback hooks for the simulation loop
        self._on_start_callbacks: list = []
        self._on_update_callbacks: list = []
        self._on_gui_update_callbacks: list = []

        # Number of simulation sub-steps per rendered frame
        self._steps_per_frame = 1

        # Playback state (loaded simulations replay in the main window)
        self._playback_mode = False
        self._playback_data: Optional[dict] = None
        self._playback_num_frames = 0
        self._playback_num_voxels = 0
        self._playback_current_frame = 0
        self._playback_playing = False
        self._playback_speed = 1.0
        self._playback_speed_value = 1.0
        self._playback_frame_accum = 0.0
        self._playback_last_time = 0.0

        self._voxels_lock = threading.Lock()

        # Shared voxel-grid topology cache.  Solvers keep their own
        # references, but the canonical topology lives here and is rebuilt
        # whenever voxels are added/removed or the grid is loaded.
        self._topology: Optional[GridTopology] = None
        self._topology_voxel_count = 0

        # Simulation control flags (driven by GUI play/pause/stop buttons)
        self._simulation_running = True
        self._simulation_paused = True

        # Snapshot of initial voxel state for reset
        self._initial_state: Optional[dict] = None

        # Keep the last recorder's data even after stop_recording()
        self._last_recorder = None

    # ==================================================================
    # Callback hooks for the simulation loop
    # ==================================================================

    def on_start(self, func):
        """Decorator: register a callback run once when ``run_simulation()`` starts.

        Example::

            @vs.on_start
            def init():
                print("Simulation started")
        """
        self._on_start_callbacks.append(func)
        return func

    def on_update(self, func):
        """Decorator: register a callback run every frame in ``run_simulation()``.

        Multiple callbacks can be registered; they run in registration order.
        If no ``on_update`` callback is registered, ``run_simulation()`` falls
        back to a single ``step_and_update(dt)`` per frame.

        Example::

            @vs.on_update
            def step():
                for _ in range(25):
                    vs.step_and_update(dt=200.0)
        """
        self._on_update_callbacks.append(func)
        return func

    def on_gui_update(self, func):
        """Decorator: register a callback run every frame after simulation stepping.

        Unlike ``on_update``, this callback is called even when the default
        fallback loop is used (no ``on_update`` registered).  It receives no
        arguments — use ``vs.elapsed_time`` and other properties to read state.

        Example::

            @vs.on_gui_update
            def update_display():
                sim_time_gui.content = f"Time: {vs._fmt_time(vs.elapsed_time)}"
        """
        self._on_gui_update_callbacks.append(func)
        return func

    # ==================================================================
    # Simulation control
    # ==================================================================

    @property
    def simulation_running(self) -> bool:
        """True while the simulation loop should continue."""
        return self._simulation_running

    @property
    def simulation_paused(self) -> bool:
        """True when the simulation loop should render but not step."""
        return self._simulation_paused

    def play(self):
        """Resume stepping in the simulation loop."""
        self._simulation_paused = False
        if self._playback_mode:
            self._playback_playing = True

    def pause(self):
        """Pause stepping in the simulation loop (rendering continues)."""
        self._simulation_paused = True
        if self._playback_mode:
            self._playback_playing = False

    def is_playing(self) -> bool:
        """Return True if the simulation is currently stepping."""
        return not self._simulation_paused

    def stop(self):
        """Signal the simulation loop to exit."""
        self._simulation_running = False

    def is_playing(self) -> bool:
        """Return whether the simulation is currently playing (not paused)."""
        return self._simulation_running and not self._simulation_paused

    def reset_simulation(self):
        """Reset simulation control flags to their initial state."""
        self._simulation_running = True
        self._simulation_paused = True

    def snapshot_initial_state(self):
        """Capture the current voxel properties as the initial state for reset."""
        with self._voxels_lock:
            self._initial_state = {
                "temperature": [v.temperature for v in self.voxels],
                "ion_concentration": [v.ion_concentration for v in self.voxels],
                "interface_concentration": [v.interface_concentration for v in self.voxels],
                "charge": [v.charge for v in self.voxels],
                "pressure": [v.pressure for v in self.voxels],
                "electric_field": [v.electric_field.copy() for v in self.voxels],
                "magnetic_field": [v.magnetic_field.copy() for v in self.voxels],
                "current_density": [v.current_density.copy() for v in self.voxels],
                "polarization": [v.polarization.copy() for v in self.voxels],
                "magnetization": [v.magnetization.copy() for v in self.voxels],
                "displacement": [v.displacement.copy() for v in self.voxels],
                "velocity": [v.velocity.copy() for v in self.voxels],
                "stress": [v.stress.copy() for v in self.voxels],
                "optical_intensity": [v.optical_intensity for v in self.voxels],
            }

    def reset_to_initial(self):
        """Restore all voxels to their initial state."""
        if self._initial_state is None:
            return
        state = self._initial_state
        with self._voxels_lock:
            for i, v in enumerate(self.voxels):
                v.temperature = state["temperature"][i]
                v.ion_concentration = state["ion_concentration"][i]
                v.interface_concentration = state["interface_concentration"][i]
                v.charge = state["charge"][i]
                v.pressure = state["pressure"][i]
                v.electric_field[:] = state["electric_field"][i]
                v.magnetic_field[:] = state["magnetic_field"][i]
                v.current_density[:] = state["current_density"][i]
                v.polarization[:] = state["polarization"][i]
                v.magnetization[:] = state["magnetization"][i]
                v.displacement[:] = state["displacement"][i]
                v.velocity[:] = state["velocity"][i]
                v.stress[:] = state["stress"][i]
                v.optical_intensity = state["optical_intensity"][i]
        # Reset elapsed time and clear pending state
        self._elapsed_time = 0.0
        self._frame_index = 0
        self._pending_temps = None
        self._pending_conc = None

    # ==================================================================
    # Run simulation / playback loop
    # ==================================================================

    def run_simulation(self, dt: Optional[float] = None, sleep: float = 0.05):
        """Run the main loop: simulation or playback.

        In simulation mode (default), the loop calls all registered
        ``on_update`` callbacks once per frame.  If no callback is
        registered, it falls back to ``step_and_update(dt)``.

        In playback mode (after ``load_simulation()``), the loop replays
        the loaded frames using the **Simulation Control** buttons.

        The loop exits on ``stop()`` or ``KeyboardInterrupt`` and
        automatically calls ``autosave()`` if any frames were recorded.

        Args:
            dt: Simulation time-step for the default fallback step.
            sleep: Real-time delay between frames [s].
        """
        self._simulation_running = True
        self._simulation_paused = True
        self._playback_last_time = time.perf_counter()

        # Snapshot current state so reset_to_initial() can restore it.
        self.snapshot_initial_state()

        # Ensure EM fields are populated before the first render so that
        # E/B-field arrow overlays are visible even while the simulation
        # starts paused.
        if self._em_solver is not None and self.voxels:
            self.apply_em_fields(t=self._elapsed_time)

        for cb in self._on_start_callbacks:
            try:
                cb()
            except Exception as exc:
                print(f"[on_start] {exc}")

        try:
            while self._simulation_running:
                if not self._simulation_paused:
                    if self._playback_mode:
                        self._advance_playback()
                    else:
                        if self._on_update_callbacks:
                            for cb in self._on_update_callbacks:
                                try:
                                    cb()
                                except Exception as exc:
                                    print(f"[on_update] {exc}")
                        else:
                            # Default loop: apply EM fields, sub-step, update GUI
                            step_dt = dt if dt is not None else self.time_step
                            for _ in range(self._steps_per_frame):
                                self.apply_em_fields(t=self._elapsed_time)
                                self.step_and_update(step_dt)
                        self._frame_index += 1

                        # GUI update callbacks run after every frame
                        for cb in self._on_gui_update_callbacks:
                            try:
                                cb()
                            except Exception as exc:
                                print(f"[on_gui_update] {exc}")

                self.render()
                time.sleep(sleep)
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            self.stop()
            if not self._playback_mode:
                npz_path, csv_path = self.autosave()
                if npz_path:
                    print(f"Saved: {npz_path}")
                    print(f"Saved: {csv_path}")

    # ==================================================================
    # Server access
    # ==================================================================

    @property
    def server(self):
        """The internal ``WebGLServer`` instance.

        Use this to access the HTTP/WebSocket server (for example, to
        print the viewer URL).  Custom GUI controls should be added in the
        browser-side JavaScript instead of here.
        """
        return self._server

    # ==================================================================
    # Render scale  (auto-inferred, overridable)
    # ==================================================================

    @property
    def render_scale(self) -> float:
        """Scale factor applied to all positions and sizes before rendering.

        Auto-computed as ``1.0 / min(voxel.size)`` so the smallest voxel
        is 1 unit wide in the viewer.  Set manually to override.
        """
        if self._render_scale is not None:
            return self._render_scale
        if not self.voxels:
            return 1.0
        min_size = min(v.size for v in self.voxels)
        return 1.0 / min_size if min_size > 0 else 1.0

    @render_scale.setter
    def render_scale(self, value: float):
        self._render_scale = float(value)

    # ==================================================================
    # Internal component accessors (lazy init)
    # ==================================================================

    def _ensure_heat_solver(self):
        if self._heat_solver is None:
            from voxsym.physics.heat_diffusion import HeatDiffusion
            self._heat_solver = HeatDiffusion(self)
        return self._heat_solver

    def _ensure_ion_solver(self):
        if self._ion_solver is None:
            from voxsym.physics.ion_diffusion import IonDiffusion
            self._ion_solver = IonDiffusion(self)
        return self._ion_solver

    def _ensure_em_solver(self):
        if self._em_solver is None:
            from voxsym.physics.electric_field import ElectromagneticSolver
            self._em_solver = ElectromagneticSolver()
        return self._em_solver

    def _ensure_poisson_solver(self):
        if self._poisson_solver is None:
            from voxsym.physics import poisson as _poisson_module
            self._poisson_solver = _poisson_module
        return self._poisson_solver

    def solve_poisson(self, max_iter: int = 500, tol: float = 1e-6):
        """Solve Poisson's equation from current voxel charges.

        Computes the electric potential φ from  ∇²φ = −ρ/ε  and stores
        the resulting electric field ``E = −∇φ`` on every voxel, plus the
        scalar potential as ``voxel.phi``.  The solver uses Neumann boundary
        conditions (zero normal derivative) on the outer surface of the
        voxel cloud.

        Args:
            max_iter: Maximum Jacobi iterations.
            tol: Convergence tolerance on max |Δφ|.
        """
        self._ensure_poisson_solver().solve_potential_from_charge(
            self, max_iter=max_iter, tol=tol,
        )

    def set_enable_poisson(self, enabled: bool = True):
        """Enable / disable automatic Poisson solve per step.

        When enabled, ``step_and_update()`` solves ∇²φ = −ρ/ε from the
        current voxel charges and overwrites ``voxel.electric_field`` with
        ``E = −∇φ`` *before* the ion transport step.  This couples ionic
        charge density to the electric field self-consistently.

        Disabled by default so existing examples keep their prescribed
        fields.
        """
        self._enable_poisson = bool(enabled)

    @property
    def enable_poisson(self) -> bool:
        """True if the Poisson solver is automatically run each step."""
        return self._enable_poisson

    def _ensure_renderer(self):
        if self._renderer is None:
            from voxsym.visualization.renderer import Renderer
            backend = getattr(self, "_webgl_backend", None)
            self._renderer = Renderer(self, backend=backend, render_scale=self.render_scale)
        return self._renderer

    def _ensure_visualizer(self):
        if self._visualizer is None:
            from voxsym.visualization.visualizer import Visualizer
            # Visualizer is still useful for scalar layer logic and arrow computation.
            self._visualizer = Visualizer(
                self._webgl_server, self, self._ensure_renderer()
            )
        return self._visualizer

    # ==================================================================
    # Simulation lifecycle  (compute → update)
    # ==================================================================

    def step_simulation(self, dt: Optional[float] = None):
        """Compute the next state for all voxels (heat + ions).

        This is a **read-only** phase: current voxel properties are used
        to calculate fluxes, but no voxel is mutated.  The results are
        stored internally and applied later by calling ``update()``.

        Args:
            dt: Simulation time-step [s].  Uses ``self.time_step`` if None.
        """
        # Optional Poisson solve: compute E from charge density before ions move.
        if self._enable_poisson:
            self.solve_poisson()

        self._ensure_heat_solver()
        self._ensure_ion_solver()
        self._pending_temps = self._heat_solver.compute_step(dt)
        self._pending_conc = self._ion_solver.compute_step(dt)

        # Optional charge conservation update from ionic flux.
        if self._ion_solver.conserve_charge:
            self._pending_charge = self._ion_solver.pending_charge_update(dt)
        else:
            self._pending_charge = None

    def update(self):
        """Write the computed temperatures and concentrations back to all voxels.

        Must be called after ``step_simulation()``.  Calling it twice in a
        row without a new step is a no-op.

        If recording is enabled (the default), this frame is also captured
        for later replay / export.
        """
        if self._pending_temps is not None:
            for i, v in enumerate(self.voxels):
                v.temperature = float(self._pending_temps[i])
            self._pending_temps = None

        if self._pending_conc is not None:
            for i, v in enumerate(self.voxels):
                v.ion_concentration = float(self._pending_conc[i])
            self._pending_conc = None

        if self._pending_charge is not None:
            for i, v in enumerate(self.voxels):
                v.charge = float(self._pending_charge[i])
            self._pending_charge = None

        # Record this updated state if recording is enabled.
        if self._recorder is not None:
            self._recorder.record(self._elapsed_time)

    def step_and_update(self, dt: Optional[float] = None):
        """Run ``step_simulation(dt)`` followed immediately by ``update()``.

        Also increments the elapsed clock used for recording timestamps.

        If *dt* exceeds the stable time-step cap multiplied by
        ``self.dt_safety_factor``, a ``RuntimeWarning`` is emitted and *dt*
        is clamped to the safe value.  Set ``dt_safety_factor = 1.0`` if you
        want to allow the raw CFL cap.
        """
        if dt is None:
            dt = self.time_step
        dt = self._clamp_dt(dt)
        self.step_simulation(dt)
        self._elapsed_time += dt
        self.update()

    def _clamp_dt(self, dt: float) -> float:
        """Warn and clamp *dt* if it exceeds the safe limit."""
        dt = float(dt)
        if dt <= 0:
            return dt
        try:
            cap = self.max_stable_dt()
        except Exception:
            # If solvers are not yet built or max_stable_dt fails for any
            # reason, fall back to the user-provided value rather than crash.
            return dt
        if not np.isfinite(cap) or cap <= 0:
            return dt
        safe = self.dt_safety_factor * cap
        if dt > safe:
            import warnings
            warnings.warn(
                f"dt={dt:g} exceeds safe limit {safe:g} "
                f"(safety_factor={self.dt_safety_factor}, cap={cap:g}); "
                f"clamping to {safe:g}.",
                RuntimeWarning,
                stacklevel=3,
            )
            return safe
        return dt

    def max_stable_dt(self) -> float:
        """Return the most restrictive stable dt across enabled solvers.

        This is the raw CFL cap from ``stability.py``.  The safety factor
        is applied separately in ``step_and_update``.
        """
        from voxsym.physics.stability import (
            max_stable_dt_for_heat_solver,
            max_stable_dt_for_ion_solver,
        )

        self._ensure_heat_solver()
        self._ensure_ion_solver()

        # Make sure the solvers have built their internal material arrays from
        # the current voxel grid before asking for a stability cap.
        self._heat_solver._build_arrays()
        self._ion_solver._build_arrays()

        heat_dt = max_stable_dt_for_heat_solver(self._heat_solver)
        ion_dt = max_stable_dt_for_ion_solver(self._ion_solver)

        caps = [heat_dt, ion_dt]
        finite_caps = [c for c in caps if np.isfinite(c) and c > 0]
        if not finite_caps:
            return float("inf")
        return float(min(finite_caps))

    # ==================================================================
    # Heat source / boundary configuration
    # ==================================================================

    def add_heat_source(self, center, radius, power):
        self._ensure_heat_solver()
        self._heat_solver.add_heat_source(center, radius, power)

    def add_fixed_temperature(self, center, radius, temperature):
        self._ensure_heat_solver()
        self._heat_solver.add_fixed_temperature(center, radius, temperature)

    def clear_heat_sources(self):
        if self._heat_solver is not None:
            self._heat_solver.clear_sources()

    def set_region_temperature(self, center, radius, temperature):
        """Set an initial temperature region and pin it (Dirichlet)."""
        cx, cy, cz = center
        r2 = radius * radius
        for v in self.voxels:
            dx = v.x - cx
            dy = v.y - cy
            dz = v.z - cz
            if dx * dx + dy * dy + dz * dz <= r2:
                v.temperature = temperature
        self.add_fixed_temperature(center, radius, temperature)

    # ==================================================================
    # Ion concentration helpers
    # ==================================================================

    def set_ion_temperature(self, T: float):
        """Set the temperature used in the Nernst–Planck mobility term."""
        self._ensure_ion_solver()
        self._ion_solver.set_temperature(T)

    def set_region_concentration(self, center, radius, concentration):
        """Set initial ion concentration in a spherical region."""
        cx, cy, cz = center
        r2 = radius * radius
        for v in self.voxels:
            dx = v.x - cx
            dy = v.y - cy
            dz = v.z - cz
            if dx * dx + dy * dy + dz * dz <= r2:
                v.ion_concentration = concentration

    # ==================================================================
    # Coupled mechanics / optics / induced magnetism
    # ==================================================================

    def _ensure_mechanics_optics_magnetism_solver(self):
        if getattr(self, "_mechanics_optics_magnetism_solver", None) is None:
            from voxsym.physics.mechanics_optics_magnetism import MechanicsOpticsMagnetism
            self._mechanics_optics_magnetism_solver = MechanicsOpticsMagnetism(self)
        return self._mechanics_optics_magnetism_solver

    def add_optical_source(self, origin, direction, intensity):
        """Add a directed optical source (origin, direction, intensity)."""
        self._ensure_mechanics_optics_magnetism_solver().add_optical_source(
            origin, direction, intensity,
        )

    def set_external_magnetic_field(self, B):
        """Set a uniform applied B-field [T] for induced magnetisation."""
        self._ensure_mechanics_optics_magnetism_solver().set_external_magnetic_field(B)

    def set_external_magnetic_field_H(self, H):
        """Set a uniform applied H-field [A/m] for induced magnetisation."""
        self._ensure_mechanics_optics_magnetism_solver().set_external_magnetic_field_H(H)

    def step_mechanics_optics_magnetism(self, dt=None):
        """Advance the coupled mechanics/optics/magnetism solver by one step."""
        self._ensure_mechanics_optics_magnetism_solver().step(dt)

    def max_stress(self):
        """Return the largest absolute stress component in the grid."""
        solver = getattr(self, "_mechanics_optics_magnetism_solver", None)
        if solver is None:
            return 0.0
        return solver.max_stress_magnitude()

    def total_absorbed_optical_power(self):
        """Estimate absorbed optical power from Beer-Lambert intensities."""
        solver = getattr(self, "_mechanics_optics_magnetism_solver", None)
        if solver is None:
            return 0.0
        return solver.total_optical_power_absorbed()

    def magnetization_stats(self):
        """Return (min, max, mean) |magnetization| across voxels."""
        mags = [np.linalg.norm(v.magnetization) for v in self.voxels]
        if not mags:
            return 0.0, 0.0, 0.0
        return min(mags), max(mags), sum(mags) / len(mags)

    # ==================================================================
    # Electromagnetic field methods
    # ==================================================================

    def add_uniform_electric(self, ex: float, ey: float, ez: float):
        """Add a constant electric field (Ex, Ey, Ez) in V/m."""
        self._ensure_em_solver().add_uniform_electric(ex, ey, ez)

    def add_uniform_magnetic(self, bx: float, by: float, bz: float):
        """Add a constant magnetic field (Bx, By, Bz) in T."""
        self._ensure_em_solver().add_uniform_magnetic(bx, by, bz)

    def add_point_charge(self, charge: float, x: float, y: float, z: float):
        """Add a point charge [C] at (x, y, z)."""
        self._ensure_em_solver().add_point_charge(charge, x, y, z)

    def add_oscillating_electric(
        self, ax: float, ay: float, az: float,
        frequency: float, phase: float = 0.0,
    ):
        """Add an AC electric field: E(t) = A·sin(2π·f·t + φ)."""
        self._ensure_em_solver().add_oscillating_electric(
            ax, ay, az, frequency, phase,
        )

    def add_gradient_electric(self, offset, grad, axis: str = "x"):
        """Add a linear spatial gradient field: E = offset + grad·axis."""
        self._ensure_em_solver().add_gradient_electric(offset, grad, axis)

    def apply_em_fields(self, t: float = 0.0):
        """Evaluate all EM fields at time *t* and store on every voxel.

        Also computes current density J = σE for each voxel.
        """
        if self._em_solver is not None:
            self._em_solver.apply_to_voxels(self.voxels, t)
        self._compute_currents()

    def _compute_currents(self):
        """Compute current density J = σE for every voxel (Ohm's law)."""
        for v in self.voxels:
            if v.material is not None and v.material.conductivity > 0:
                v.current_density = v.material.conductivity * v.electric_field
            else:
                v.current_density = np.zeros(3)

    def clear_em_fields(self):
        """Remove all EM field sources."""
        if self._em_solver is not None:
            self._em_solver.clear()

    # ==================================================================
    # Camera  (scaling-aware)
    # ==================================================================

    def setup_gui(self):
        """Create standard GUI panels and callbacks.

        For the WebGL backend this is a no-op: controls live in the
        browser sidebar.  The method prints the viewer URL and ensures
        the renderer/visualizer are ready.

        Returns:
            VoxSymGUI instance (no-op, for backwards compatibility).
        """
        self._ensure_renderer()
        self._ensure_visualizer()
        from voxsym.visualization.gui import VoxSymGUI
        self._gui = VoxSymGUI(self, self._server)
        url = f"http://{self._server.host}:{self._server.port}" if self._server else None
        if url:
            print(f"WebGL viewer: {url}")
        return self._gui

    # ==================================================================
    # Rendering
    # ==================================================================

    def render(self):
        """Render the current state (voxels + active overlay layers).

        Reads GUI control values (cross-section, opacity) and applies
        them automatically.  Also advances the optional player replay
        if it has been launched.  Call once per frame in the main loop.
        """
        if self._gui is not None:
            self._gui.sync()
        # The visualizer still computes scalar layers and vector arrows; make sure it exists.
        if self._visualizer is None:
            self._ensure_visualizer()
        if self._visualizer is not None:
            self._visualizer.render()
        # For the WebGL backend, broadcast the rendered frame to clients.
        if self._backend_name == "webgl" and self._webgl_server is not None:
            payload = self._webgl_backend.get_latest_payload()
            self._webgl_server.broadcast_frame(payload)
        # Keep the player in sync with the running simulation.
        if self._player is not None:
            self._feed_player()

    def auto_camera(self, distance_factor: float = 1.5):
        """Position the camera to frame the entire voxel grid.

        Computes the bounding box of all voxels (in render-scale
        coordinates) and places the camera at
        ``distance_factor × diagonal`` from the centre, looking at
        the centre.  Call once after building the grid.

        Args:
            distance_factor: Multiplier for camera distance.
        """
        if self._server is None:
            return
        if not self.voxels:
            return

        scl = self.render_scale
        xs = [v.x * scl for v in self.voxels]
        ys = [v.y * scl for v in self.voxels]
        zs = [v.z * scl for v in self.voxels]
        sizes = [v.size * scl for v in self.voxels]

        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        cz = (min(zs) + max(zs)) / 2.0
        dx = max(xs) - min(xs) + max(sizes)
        dy = max(ys) - min(ys) + max(sizes)
        dz = max(zs) - min(zs) + max(sizes)
        diag = np.sqrt(dx * dx + dy * dy + dz * dz)
        dist = max(diag * distance_factor, 1e-6)

        if hasattr(self._server, "set_initial_camera"):
            self._server.set_initial_camera(
                position=(cx + dist * 0.6, cy + dist * 0.4, cz + dist * 0.6),
                look_at=(cx, cy, cz),
            )

    # ==================================================================
    # Layer management  (delegates to internal Visualizer)
    # ==================================================================

    def set_layer(self, name: str, active: bool = True):
        """Toggle a visualization layer on/off.

        Args:
            name: Layer name (use ``Layer.ELECTRIC_FIELD`` etc.).
            active: True to show, False to hide.
        """
        if self._visualizer is None:
            self._ensure_visualizer()
        if self._visualizer is not None:
            self._visualizer.set_layer(name, active)

    def toggle_layer(self, name: str) -> bool:
        """Flip a layer's state.  Returns the new state."""
        if self._visualizer is None:
            self._ensure_visualizer()
        if self._visualizer is not None:
            return self._visualizer.toggle_layer(name)
        return False

    def reset_layers(self):
        """Reset to base colour layer, removing all overlays."""
        if self._visualizer is None:
            self._ensure_visualizer()
        if self._visualizer is not None:
            self._visualizer.remove_all_overlays()

    # ==================================================================
    # Opacity
    # ==================================================================

    @property
    def opacity(self) -> float:
        """Global opacity value (0–1)."""
        if self._gui is not None:
            return self._gui.opacity
        backend = getattr(self, "_webgl_backend", None)
        if backend is not None:
            return getattr(backend, "_opacity", 1.0)
        return 1.0

    @opacity.setter
    def opacity(self, value: float):
        """Set the global opacity slider value."""
        if self._gui is not None:
            self._gui.set_opacity(value)
        backend = getattr(self, "_webgl_backend", None)
        if backend is not None and hasattr(backend, "set_opacity"):
            backend.set_opacity(value)

    # ==================================================================
    # Visualizer settings  (convenience properties)
    # ==================================================================

    @property
    def field_subsample(self) -> int:
        """Stride for vector-field arrow display (every Nth voxel)."""
        if self._visualizer is not None:
            return self._visualizer.field_subsample
        return 4

    @field_subsample.setter
    def field_subsample(self, value: int):
        if self._visualizer is not None:
            self._visualizer.field_subsample = value

    @property
    def field_arrow_scale(self) -> float:
        """Length scale for field arrows."""
        if self._visualizer is not None:
            return self._visualizer.field_arrow_scale
        return 0.8

    @field_arrow_scale.setter
    def field_arrow_scale(self, value: float):
        if self._visualizer is not None:
            self._visualizer.field_arrow_scale = value

    @property
    def temp_range(self):
        """(min, max) temperature range for the temperature colormap."""
        if self._visualizer is not None:
            return self._visualizer.temp_range
        return (250.0, 400.0)

    @temp_range.setter
    def temp_range(self, value):
        if self._visualizer is not None:
            self._visualizer.temp_range = value

    # ==================================================================
    # Diagnostics
    # ==================================================================

    def temperature_stats(self):
        temps = [v.temperature for v in self.voxels]
        if not temps:
            return 0.0, 0.0, 0.0
        return min(temps), max(temps), sum(temps) / len(temps)

    def concentration_stats(self):
        concs = [v.ion_concentration for v in self.voxels]
        if not concs:
            return 0.0, 0.0, 0.0
        return min(concs), max(concs), sum(concs) / len(concs)

    # ==================================================================
    # Elapsed simulation time (used by recorder and player)
    # ==================================================================

    @property
    def elapsed_time(self) -> float:
        """Elapsed simulation time [s] for the current session."""
        return self._elapsed_time

    @property
    def frame_index(self) -> int:
        """Number of rendered frames since start/reset."""
        return getattr(self, "_frame_index", 0)

    def reset_elapsed_time(self):
        """Reset the elapsed simulation clock (and player frame counter)."""
        self._elapsed_time = 0.0
        self._player_frame_counter = 0
        self._frame_index = 0

    # ==================================================================
    # Player integration (legacy: opens a second port)
    # ==================================================================

    def set_player_steps_per_frame(self, n: int):
        """Set how many simulation steps are captured per player frame.

        Default is 1.  Increase this to keep replay frame counts reasonable
        for very fine simulation loops.
        """
        self._player_steps_per_frame = max(1, int(n))

    def _ensure_player(self):
        """Lazy-create the internal Player once recorded data is available."""
        if self._player is None and self._player_enabled and self._player_data is not None:
            from voxsym.io.player import Player
            self._player = Player(self._player_data, port=self._player_port)

    def _feed_player(self):
        """Advance the internal Player by one frame if it exists."""
        if self._player is not None:
            self._player.render()

    def launch_player(self):
        """Create the Player window from currently recorded frames.

        Deprecated: use ``load_simulation()`` to replay recordings in the
        main window.  Kept for backwards compatibility.
        """
        if not self._player_enabled:
            raise RuntimeError("Player is disabled (enable_player=False).")

        if self._recorder is None or self._recorder.frame_count == 0:
            raise RuntimeError("No recorded frames to play back.")

        self._player_data = {
            "positions": np.array([[v.x, v.y, v.z] for v in self.voxels], dtype=np.float32),
            "sizes": np.array([v.size for v in self.voxels], dtype=np.float32),
            "colors": np.array([v.color for v in self.voxels], dtype=np.uint8),
            "material_names": np.array(
                [v.material.name if v.material else "none" for v in self.voxels],
                dtype=str,
            ),
            "times": np.array(self._recorder._times, dtype=np.float64),
            "temperatures": np.array(self._recorder._temperatures, dtype=np.float32),
            "pressures": np.array(self._recorder._pressures, dtype=np.float32),
            "ion_concentrations": np.array(self._recorder._ion_concentrations, dtype=np.float32),
            "charges": np.array(self._recorder._charges, dtype=np.float32),
            "electric_fields": np.array(self._recorder._electric_fields, dtype=np.float32),
            "magnetic_fields": np.array(self._recorder._magnetic_fields, dtype=np.float32),
            "current_densities": np.array(self._recorder._current_densities, dtype=np.float32),
            "polarizations": np.array(self._recorder._polarizations, dtype=np.float32),
            "magnetizations": np.array(self._recorder._magnetizations, dtype=np.float32),
        }
        self._ensure_player()
        return self._player

    # ==================================================================
    # Playback in the main window
    # ==================================================================

    def load_simulation(self, data, refresh_gui: bool = True):
        """Load a recorded simulation and switch the main window to playback mode.

        Accepts:
        * A dict / NpzFile as returned by ``Recorder.load()`` or
          ``Recorder.from_csv()``.
        * A file path (``.npz`` or ``.csv``) — loaded automatically.

        The current voxel grid is replaced by the recorded grid and the
        first frame is shown immediately.

        Args:
            data: Recording data or path.
            refresh_gui: If True and a GUI exists, refresh the playback
                slider.  Set to False when calling from a background thread
                and refresh the GUI manually on the event loop.
        """
        # Accept file paths for convenience.
        if isinstance(data, (str, os.PathLike)):
            path = os.fspath(data)
            from voxsym.io.recorder import Recorder
            if path.lower().endswith(".csv"):
                data = Recorder.from_csv(path)
            else:
                data = Recorder.load(path)

        # Materialise NpzFile into a plain dict so lazy-loading / threading
        # cannot break playback later.
        if hasattr(data, "files") and hasattr(data, "__getitem__"):
            data = {key: np.array(data[key]) for key in data.files}

        required_keys = [
            "positions", "sizes", "colors", "material_names", "times",
            "temperatures", "ion_concentrations", "electric_fields",
            "magnetic_fields", "current_densities",
        ]
        missing = [k for k in required_keys if k not in data]
        if missing:
            raise ValueError(f"Recording missing required keys: {missing}")

        self._playback_data = data
        self._playback_num_frames = len(data["times"])
        self._playback_num_voxels = len(data["positions"])
        self._playback_current_frame = 0
        self._playback_playing = False
        self._playback_frame_accum = 0.0

        if self._playback_num_frames == 0 or self._playback_num_voxels == 0:
            raise ValueError("Recording has no frames or no voxels.")

        positions = np.asarray(data["positions"], dtype=np.float32)
        sizes = np.asarray(data["sizes"], dtype=np.float32)
        colors = np.asarray(data["colors"], dtype=np.uint8)
        mat_names = data["material_names"]
        temps = np.asarray(data["temperatures"], dtype=np.float32)
        ion_concs = np.asarray(data["ion_concentrations"], dtype=np.float32)
        e_fields = np.asarray(data["electric_fields"], dtype=np.float32)
        b_fields = np.asarray(data["magnetic_fields"], dtype=np.float32)
        j_fields = np.asarray(data["current_densities"], dtype=np.float32)
        pressures = np.asarray(data["pressures"], dtype=np.float32) if "pressures" in data else None
        charges = np.asarray(data["charges"], dtype=np.float32) if "charges" in data else None
        pols = np.asarray(data["polarizations"], dtype=np.float32) if "polarizations" in data else None
        mags = np.asarray(data["magnetizations"], dtype=np.float32) if "magnetizations" in data else None
        interface_concs = np.asarray(data["interface_concentrations"], dtype=np.float32) if "interface_concentrations" in data else None
        displacements = np.asarray(data["displacements"], dtype=np.float32) if "displacements" in data else None
        velocities = np.asarray(data["velocities"], dtype=np.float32) if "velocities" in data else None
        stresses = np.asarray(data["stresses"], dtype=np.float32) if "stresses" in data else None
        optical_intensities = np.asarray(data["optical_intensities"], dtype=np.float32) if "optical_intensities" in data else None

        from voxsym.material import MATERIALS
        from voxsym.voxel import Voxel

        # Build the new voxel list once, outside the lock, using frame 0 data
        # directly so we don't need a second full iteration to apply it.
        new_voxels = []
        for i in range(self._playback_num_voxels):
            v = Voxel(
                x=float(positions[i, 0]),
                y=float(positions[i, 1]),
                z=float(positions[i, 2]),
                size=float(sizes[i]),
                color=tuple(int(c) for c in colors[i]),
                temperature=float(temps[0, i]),
                ion_concentration=float(ion_concs[0, i]),
                electric_field=e_fields[0, i].copy(),
                magnetic_field=b_fields[0, i].copy(),
                current_density=j_fields[0, i].copy(),
                pressure=float(pressures[0, i]) if pressures is not None else 101.3,
                charge=float(charges[0, i]) if charges is not None else 0.0,
                polarization=pols[0, i].copy() if pols is not None else np.zeros(3),
                magnetization=mags[0, i].copy() if mags is not None else np.zeros(3),
                interface_concentration=float(interface_concs[0, i]) if interface_concs is not None else 0.0,
                displacement=displacements[0, i].copy() if displacements is not None else np.zeros(3),
                velocity=velocities[0, i].copy() if velocities is not None else np.zeros(3),
                stress=stresses[0, i].copy() if stresses is not None else np.zeros(6),
                optical_intensity=float(optical_intensities[0, i]) if optical_intensities is not None else 0.0,
            )
            name = _decode_name(mat_names[i])
            if name in MATERIALS:
                v.material = MATERIALS[name]
            new_voxels.append(v)

        # Swap the grid and reset the renderer under a brief lock.
        with self._voxels_lock:
            self.voxels = new_voxels
            self._topology = None
            self._topology_voxel_count = len(new_voxels)
            if self._renderer is not None:
                if self._renderer.backend is not None:
                    self._renderer.backend.clear()
            if self._visualizer is not None:
                self._visualizer.remove_all_overlays()

        # Enter playback mode and update camera.
        self._playback_mode = True
        self.auto_camera()

        # Choose a scalar layer that actually changes during the recording so
        # the user sees the playback instead of a static mesh.
        if self._visualizer is not None:
            self._select_playback_layer()

    def _select_playback_layer(self):
        """Activate a scalar layer that changes across the loaded recording."""
        from voxsym.visualization.visualizer import Layer

        temps = np.asarray(self._playback_data["temperatures"], dtype=np.float32)
        ion_concs = np.asarray(
            self._playback_data["ion_concentrations"], dtype=np.float32
        )
        materials = self._playback_data["material_names"]

        t_min, t_max = float(temps.min()), float(temps.max())
        ion_min, ion_max = float(ion_concs.min()), float(ion_concs.max())
        has_multiple_materials = len(set(str(m) for m in materials)) > 1

        # Prefer the field with the largest relative variation.
        t_span = t_max - t_min
        ion_span = ion_max - ion_min

        if t_span > 1e-3:
            self._visualizer.temp_range = (t_min, t_max)
            self._visualizer.set_layer(Layer.TEMPERATURE, True)
        elif ion_span > 1e-6:
            self._visualizer.set_layer(Layer.ION_CONCENTRATION, True)
        elif has_multiple_materials:
            self._visualizer.set_layer(Layer.MATERIAL, True)
        else:
            # Nothing varies visually beyond the base colours.
            self._visualizer.set_layer(Layer.VOXEL_COLOR, True)

    def _apply_playback_frame(self, idx: int):
        """Write frame *idx* of the loaded recording into the voxels."""
        if self._playback_data is None or self._playback_num_frames == 0:
            return

        idx = max(0, min(self._playback_num_frames - 1, idx))
        self._playback_current_frame = idx
        data = self._playback_data

        with self._voxels_lock:
            for i, v in enumerate(self.voxels):
                v.temperature = float(data["temperatures"][idx, i])
                v.ion_concentration = float(data["ion_concentrations"][idx, i])
                v.electric_field = np.array(data["electric_fields"][idx, i], dtype=np.float32).copy()
                v.magnetic_field = np.array(data["magnetic_fields"][idx, i], dtype=np.float32).copy()
                v.current_density = np.array(data["current_densities"][idx, i], dtype=np.float32).copy()

                if "pressures" in data:
                    v.pressure = float(data["pressures"][idx, i])
                if "charges" in data:
                    v.charge = float(data["charges"][idx, i])
                if "polarizations" in data:
                    v.polarization = np.array(data["polarizations"][idx, i], dtype=np.float32).copy()
                if "magnetizations" in data:
                    v.magnetization = np.array(data["magnetizations"][idx, i], dtype=np.float32).copy()
                if "interface_concentrations" in data:
                    v.interface_concentration = float(data["interface_concentrations"][idx, i])
                if "displacements" in data:
                    v.displacement = np.array(data["displacements"][idx, i], dtype=np.float32).copy()
                if "velocities" in data:
                    v.velocity = np.array(data["velocities"][idx, i], dtype=np.float32).copy()
                if "stresses" in data:
                    v.stress = np.array(data["stresses"][idx, i], dtype=np.float32).copy()
                if "optical_intensities" in data:
                    v.optical_intensity = float(data["optical_intensities"][idx, i])

    def _advance_playback(self):
        """Advance the loaded playback by one frame if playing."""
        if not self._playback_mode or self._playback_num_frames == 0:
            return

        now = time.perf_counter()
        dt_real = now - self._playback_last_time
        self._playback_last_time = now

        if self._playback_playing:
            # Read the speed from the GUI slider value (synced via on_update).
            speed = self._playback_speed_value
            self._playback_frame_accum += speed
            advance = int(self._playback_frame_accum)
            self._playback_frame_accum -= advance
            self._playback_current_frame = min(
                self._playback_num_frames - 1,
                self._playback_current_frame + advance,
            )
            self._apply_playback_frame(self._playback_current_frame)
            if self._playback_current_frame >= self._playback_num_frames - 1:
                self._playback_playing = False

    def _fmt_time(self, t: float) -> str:
        """Human-readable time formatting."""
        if t >= 1.0:
            return f"{t:.3f} s"
        elif t >= 1e-3:
            return f"{t * 1e3:.2f} ms"
        elif t >= 1e-6:
            return f"{t * 1e6:.2f} µs"
        else:
            return f"{t * 1e9:.2f} ns"

    # ==================================================================
    # Recording
    # ==================================================================

    def start_recording(self):
        """Begin (or restart) recording voxel state at each ``update()``.

        Recording is on by default; this method is useful after a prior
        ``stop_recording()`` call.
        """
        from voxsym.io.recorder import Recorder
        self._recorder = Recorder(self)
        return self._recorder

    def record(self, t: float):
        """Manually capture the current voxel state.

        Normally the recorder fires automatically from ``update()``.  This
        method allows extra snapshots at arbitrary times.
        """
        if self._recorder is not None:
            self._recorder.record(t)

    def stop_recording(self):
        """Stop automatic recording.

        The already-captured frames remain available for the Player.
        """
        rec = self._recorder
        self._recorder = None
        if rec is not None and rec.frame_count > 0:
            self._last_recorder = rec
        return rec

    def _default_results_path(self, ext: str) -> str:
        """Return a default save path: ./results/<script>/DDMMYYYY.<ext>."""
        # Determine the calling script's basename.  Prefer the deepest
        # caller outside of voxsym.py / player.py / recorder.py.
        script_name = None
        try:
            for frame_info in inspect.stack():
                fname = os.path.basename(frame_info.filename)
                if fname not in ("voxsym.py", "player.py", "recorder.py",
                                  "gui.py", "viewer.py", "visualizer.py"):
                    script_name = fname
                    break
        except Exception:
            pass

        if not script_name:
            script_name = os.path.basename(sys.argv[0])
        if script_name.endswith(".py"):
            script_name = script_name[:-3]
        if script_name in ("", "-c", "python", "python3"):
            script_name = "voxsym_simulation"

        today = datetime.datetime.now().strftime("%d%m%Y")
        results_dir = os.path.join(".", "results", script_name)
        os.makedirs(results_dir, exist_ok=True)
        return os.path.join(results_dir, f"{today}.{ext}")

    def save_recording(self, path: Optional[str] = None):
        """Stop recording and save directly to *path* (.npz).

        If *path* is omitted, writes to
        ``./results/<script_name>/DDMMYYYY.npz``.
        """
        if path is None:
            path = self._default_results_path("npz")
        rec = self._recorder if self._recorder is not None else self._last_recorder
        if rec is not None:
            if self._recorder is not None:
                self.stop_recording()
            rec.save(path)
        return path

    def save_recording_csv(self, path: Optional[str] = None):
        """Stop recording and export directly to *path* (.csv).

        If *path* is omitted, writes to
        ``./results/<script_name>/DDMMYYYY.csv``.
        """
        if path is None:
            path = self._default_results_path("csv")
        rec = self._recorder if self._recorder is not None else self._last_recorder
        if rec is not None:
            if self._recorder is not None:
                self.stop_recording()
            rec.save_csv(path)
        return path

    def autosave(self):
        """Save the current recording to the default results folder.

        Writes both ``.npz`` (replay) and ``.csv`` (analysis) using the
        naming convention ``./results/<script_name>/DDMMYYYY.*``.
        """
        # Use the current recorder, or fall back to the last one if
        # recording was already stopped by the user.
        rec = self._recorder if self._recorder is not None else self._last_recorder
        if rec is None or rec.frame_count == 0:
            return None, None

        npz_path = self._default_results_path("npz")
        csv_path = self._default_results_path("csv")
        rec.save(npz_path)
        rec.save_csv(csv_path)

        # Restart recording so the simulation can continue.
        if self._recorder is None:
            self.start_recording()
        return npz_path, csv_path

    # ==================================================================
    # Geometry
    # ==================================================================

    def set_space_resolution(self, resolution):
        self.space_resolution = resolution

    def set_time_step(self, time_step):
        self.time_step = time_step

    def set_steps_per_frame(self, n: int):
        """Set how many simulation sub-steps are taken per rendered frame.

        The default is 1.  Increase this when the simulation time-step is
        much smaller than the display frame rate (e.g. 100 sub-steps of
        1\u00b5s per frame).
        """
        self._steps_per_frame = max(1, int(n))

    def add_voxel(self, voxel):
        with self._voxels_lock:
            self.voxels.append(voxel)
        self._invalidate_topology()

    def remove_voxel(self, voxel):
        """Remove the first occurrence of *voxel* from the live grid."""
        with self._voxels_lock:
            try:
                self.voxels.remove(voxel)
            except ValueError:
                return
        self._invalidate_topology()

    def build_grid(self, voxels):
        """Replace the entire voxel grid with *voxels* (a list of Voxel).

        This is the preferred way to load geometry in scripts that do not
        call ``add_voxel`` one-by-one.  It also invalidates the shared
        topology cache.
        """
        with self._voxels_lock:
            self.voxels = list(voxels)
        self._invalidate_topology()

    def _invalidate_topology(self):
        """Mark the shared topology cache as stale.

        The next physics step will rebuild the solvers' internal arrays.
        Calling this after every ``add_voxel`` is inexpensive because the
        actual arrays are built lazily inside ``compute_step``.
        """
        self._topology = None
        self._topology_voxel_count = 0
        if self._heat_solver is not None:
            self._heat_solver._built = False
            self._heat_solver._topology_voxel_count = -1
        if self._ion_solver is not None:
            self._ion_solver._built = False
            self._ion_solver._topology_voxel_count = -1

    def get_topology(self):
        """Return the cached ``GridTopology`` for the current voxel grid.

        The topology is rebuilt automatically if the voxel count changed.
        """
        n = len(self.get_voxels())
        if self._topology is None or self._topology_voxel_count != n:
            self._topology = GridTopology(self.voxels, connectivity=6)
            self._topology_voxel_count = n
        return self._topology

    def get_voxels(self):
        """Return the live voxel list (snapshot under lock)."""
        with self._voxels_lock:
            return list(self.voxels)

    def get_space_resolution(self):
        return self.space_resolution

    def get_time_step(self):
        return self.time_step
