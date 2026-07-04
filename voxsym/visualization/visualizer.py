"""Connects to Renderer and adds optional overlay layers (fields, temperature, etc.)."""

import numpy as np
from typing import Dict, List, Set, Callable, Optional

from voxsym.voxel import Voxel
from voxsym.voxsym import VoxSym
from voxsym.visualization.renderer import Renderer


class Layer:
    """Named visualization layers."""
    VOXEL_COLOR = "voxel_color"
    ELECTRIC_FIELD = "electric_field"
    MAGNETIC_FIELD = "magnetic_field"
    CURRENT = "current"
    TEMPERATURE = "temperature"
    MATERIAL = "material"
    ION_CONCENTRATION = "ion_concentration"


class Visualizer:
    """Connects to Renderer and adds optional overlay layers (fields, temperature, etc.).

    Usage:
        viz = Visualizer(server, voxsym, renderer)
        viz.set_layer(Layer.ELECTRIC_FIELD, True)
        viz.set_layer(Layer.TEMPERATURE, True)
        while True:
            viz.render()
    """

    def __init__(
        self,
        server,
        voxsym: VoxSym,
        renderer: Renderer,
    ):
        self.server = server
        self.voxsym = voxsym
        self.renderer = renderer
        self._active: Set[str] = {Layer.VOXEL_COLOR}
        self._handles: Dict[str, Optional[object]] = {}

        self._callbacks: Dict[str, Callable] = {
            Layer.VOXEL_COLOR: self._noop,
            Layer.ELECTRIC_FIELD: self._render_electric_field,
            Layer.MAGNETIC_FIELD: self._render_magnetic_field,
            Layer.CURRENT: self._render_current,
        }
        # Snapshot of original voxel colors so "Base colours" can restore them
        # after a scalar layer (temperature, material, ion conc) has changed them.
        self._base_colors: Dict[int, tuple] = {}
        # Layer parameters
        self.field_arrow_scale = 0.8      # length scale for arrow display
        self.field_subsample = 4            # show every Nth arrow per axis
        self.field_color_mode = "direction"  # "direction" | "magnitude"
        self.temp_colormap = "hot"        # "hot" | "cool" | "jet"
        self.temp_range = (250.0, 400.0)  # K

        # Cross-section (mobile slicing plane)
        self.cross_section_axis: Optional[str] = None  # None, 'x', 'y', 'z'
        self.cross_section_pos: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def auto_camera(self, distance_factor: float = 1.5, render_scale: float = 1.0):
        """Position the camera to frame the entire voxel grid.

        Computes the bounding box of all voxels and places the camera
        at ``distance_factor × diagonal`` from the centre, looking at
        the centre.  Call once after building the grid.

        Args:
            distance_factor: Multiplier for camera distance.
            render_scale: Must match the ``render_scale`` passed to
                :class:`Renderer` so the camera is positioned in the
                same coordinate space as the rendered geometry.
        """
        voxels = self.voxsym.get_voxels()
        if not voxels:
            return

        scl = float(render_scale)
        xs = [v.x * scl for v in voxels]
        ys = [v.y * scl for v in voxels]
        zs = [v.z * scl for v in voxels]
        sizes = [v.size * scl for v in voxels]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        cz = (min(zs) + max(zs)) / 2.0
        dx = max(xs) - min(xs) + max(sizes)
        dy = max(ys) - min(ys) + max(sizes)
        dz = max(zs) - min(zs) + max(sizes)
        diag = np.sqrt(dx * dx + dy * dy + dz * dz)
        dist = max(diag * distance_factor, 1e-6)

        # The WebGL server exposes an initial camera helper.
        if hasattr(self.server, "set_initial_camera"):
            self.server.set_initial_camera(
                position=(cx + dist * 0.6, cy + dist * 0.4, cz + dist * 0.6),
                look_at=(cx, cy, cz),
            )

    def set_layer(self, name: str, active: bool = True):
        """Toggle a visualization layer on/off.

        Scalar color layers (temperature, material, ion concentration,
        base colour) are mutually exclusive: activating one deactivates the
        others.  Vector overlay layers (E/B-field, current) can coexist.
        """
        scalar_layers = {
            Layer.VOXEL_COLOR,
            Layer.TEMPERATURE,
            Layer.MATERIAL,
            Layer.ION_CONCENTRATION,
        }
        if active:
            self._active.add(name)
            # Scalar layers are mutually exclusive
            if name in scalar_layers:
                for other in scalar_layers:
                    if other != name:
                        self._active.discard(other)
                if name == Layer.VOXEL_COLOR:
                    self._restore_base_colors()
            # Auto-refresh E/B/current data from the voxels so arrow
            # overlays are visible immediately when toggled on.
            if name in (Layer.ELECTRIC_FIELD, Layer.MAGNETIC_FIELD, Layer.CURRENT):
                self.voxsym.apply_em_fields(t=self.voxsym.elapsed_time)
        else:
            self._active.discard(name)
            if name in self._handles and self._handles[name] is not None:
                self._handles[name].visible = False
        # Ensure at least one base layer is active
        if not self._active:
            self._active.add(Layer.VOXEL_COLOR)
            self._restore_base_colors()

    def toggle_layer(self, name: str) -> bool:
        """Flip layer state. Returns new state."""
        is_active = name in self._active
        self.set_layer(name, not is_active)
        return not is_active

    def is_active(self, name: str) -> bool:
        return name in self._active

    def render(self):
        """Render base voxels + all active overlay layers."""
        # Compute vector overlays first so their arrow data is available to
        # the backend when we serialize the frame below.
        for name in self._active:
            if name in self._callbacks:
                self._callbacks[name]()

        # If no vector layer is active, hide the arrow mesh handles entirely.
        for layer_name in (Layer.ELECTRIC_FIELD, Layer.MAGNETIC_FIELD, Layer.CURRENT):
            if layer_name not in self._active:
                self._hide_handle(layer_name)

        # ---- Cross-section: move hidden voxels far away so they don't occlude ----
        saved_positions = None
        if self.cross_section_axis is not None:
            voxels = self.voxsym.get_voxels()
            saved_positions = [(v.x, v.y, v.z) for v in voxels]
            axis = self.cross_section_axis
            pos = self.cross_section_pos
            for v in voxels:
                if getattr(v, axis) > pos:
                    v.x = 1e6
                    v.y = 1e6
                    v.z = 1e6

        # Determine voxel colors based on active scalar layer
        self._apply_scalar_colors()
        self.renderer.render()

        # Restore original positions
        if saved_positions is not None:
            for v, (x, y, z) in zip(self.voxsym.get_voxels(), saved_positions):
                v.x = x
                v.y = y
                v.z = z

        # Hide handles for inactive layers
        for name, handle in list(self._handles.items()):
            if handle is not None and name not in self._active:
                handle.visible = False

    def remove_all_overlays(self):
        """Delete all overlay scene nodes and restore base voxel colors."""
        for name, handle in list(self._handles.items()):
            if handle is not None:
                try:
                    handle.remove()
                except Exception:
                    pass
            self._handles[name] = None
        self._active = {Layer.VOXEL_COLOR}
        self._restore_base_colors()

    # ------------------------------------------------------------------
    # Scalar layers – applied by mutating voxel.color before render()
    # ------------------------------------------------------------------

    def _apply_scalar_colors(self):
        """If a scalar layer is active, compute colors and write them to voxels."""
        scalar_priority = [
            Layer.ION_CONCENTRATION,
            Layer.TEMPERATURE,
            Layer.MATERIAL,
            Layer.VOXEL_COLOR,
        ]
        for layer in scalar_priority:
            if layer in self._active:
                if layer == Layer.ION_CONCENTRATION:
                    self._snapshot_base_colors()
                    self._color_by_ion_concentration()
                elif layer == Layer.TEMPERATURE:
                    self._snapshot_base_colors()
                    self._color_by_temperature()
                elif layer == Layer.MATERIAL:
                    self._snapshot_base_colors()
                    self._color_by_material()
                elif layer == Layer.VOXEL_COLOR:
                    self._restore_base_colors()
                break

    def _color_by_temperature(self):
        """Map voxel temperatures to colors using a fixed plasma colormap.

        The range is fixed (not adaptive) so absolute temperature changes
        are visible: as the hot centre cools, its colour shifts from
        yellow-white → orange → red → purple → black.
        """
        voxels = self.voxsym.get_voxels()
        if not voxels:
            return

        # Fixed range — must match the simulation's expected temperatures
        t_min, t_max = self.temp_range
        span = t_max - t_min
        if span < 1e-3:
            span = 1.0

        for voxel in voxels:
            t = voxel.temperature
            # Clamp to [0, 1] so out-of-range temps hit the colormap ends
            norm = (t - t_min) / span
            norm = np.clip(norm, 0.0, 1.0)
            voxel.color = self._colormap_plasma(norm)

    def _color_by_material(self):
        voxels = self.voxsym.get_voxels()
        for voxel in voxels:
            if voxel.material is not None:
                voxel.color = voxel.material.color
            else:
                voxel.color = (180, 180, 180)

    def _color_by_ion_concentration(self):
        """Map ion concentration to a blue-cyan-green-yellow colormap."""
        voxels = self.voxsym.get_voxels()
        if not voxels:
            return

        concs = [v.ion_concentration for v in voxels]
        c_min = float(min(concs))
        c_max = float(max(concs))
        span = c_max - c_min
        if span < 1e-6:
            span = 1.0

        for voxel in voxels:
            norm = (voxel.ion_concentration - c_min) / span
            norm = np.clip(norm, 0.0, 1.0)
            voxel.color = self._colormap_ion(norm)

    # ------------------------------------------------------------------
    # Vector overlays – drawn as arrows via the renderer backend
    # ------------------------------------------------------------------

    def _render_electric_field(self):
        self._render_vector_field(
            layer_name=Layer.ELECTRIC_FIELD,
            get_vector=lambda v: v.electric_field,
            base_color=(255, 30, 30),
            name="/layer_electric_field",
        )

    def _render_magnetic_field(self):
        self._render_vector_field(
            layer_name=Layer.MAGNETIC_FIELD,
            get_vector=lambda v: v.magnetic_field,
            base_color=(30, 100, 255),
            name="/layer_magnetic_field",
        )

    def _render_current(self):
        self._render_vector_field(
            layer_name=Layer.CURRENT,
            get_vector=lambda v: v.current_density,
            base_color=(255, 200, 30),
            name="/layer_current",
        )

    def _render_vector_field(
        self,
        layer_name: str,
        get_vector: Callable[[Voxel], np.ndarray],
        base_color: tuple,
        name: str,
    ):
        voxels = self.voxsym.get_voxels()
        if not voxels:
            return

        scl = self.renderer.render_scale

        # Subsample to avoid overwhelming the viewer
        stride = max(1, self.field_subsample)
        selected: List[Voxel] = []
        for i, v in enumerate(voxels):
            if i % stride == 0:
                vec = get_vector(v)
                if np.linalg.norm(vec) > 1e-12:
                    selected.append(v)

        if not selected:
            self._hide_handle(layer_name)
            return

        # Compute magnitudes and the layer's maximum magnitude so arrow
        # length and colour both encode relative field strength.
        vecs = []
        max_mag = 0.0
        for voxel in selected:
            vec = get_vector(voxel)
            mag = float(np.linalg.norm(vec))
            vecs.append((voxel, vec, mag))
            if mag > max_mag:
                max_mag = mag

        if max_mag < 1e-12:
            max_mag = 1.0

        n = len(selected)
        points = np.zeros((n, 2, 3), dtype=np.float32)
        colors = np.zeros((n, 3), dtype=np.uint8)
        directions = np.zeros((n, 3), dtype=np.float32)

        # Geometry parameters in *rendered* units (after render_scale).
        base_size = float(selected[0].size) * scl
        shaft_radius = 0.04 * base_size
        head_radius = 0.08 * base_size
        head_length = 0.12 * base_size * self.field_arrow_scale

        for i, (voxel, vec, mag) in enumerate(vecs):
            direction = vec / mag if mag > 1e-12 else np.zeros(3)
            directions[i] = direction.astype(np.float32)
            # Relative strength in [0, 1].
            strength = mag / max_mag
            # Arrow length in rendered units: at least a fraction of the voxel
            # size (so orientation is always readable) and up to ~1.5 voxel
            # sizes for strong fields.
            length = (
                base_size
                * self.field_arrow_scale
                * (0.3 + 0.9 * strength)
            )

            center = np.array(
                [voxel.x * scl, voxel.y * scl, voxel.z * scl], dtype=float
            )
            offset = 0.5 * length * direction
            points[i, 0] = center - offset  # tail
            points[i, 1] = center + offset  # head

            if self.field_color_mode == "magnitude":
                colors[i] = self._colormap_hot(strength)
            else:
                # Brighten with strength so the field type is always
                # identifiable but stronger fields pop more.
                mix = 0.5 + 0.5 * strength
                colors[i] = tuple(min(255, int(c * mix)) for c in base_color)

        backend = self.renderer.backend
        if backend is not None:
            backend.add_arrows(
                points, colors, shaft_radius, head_radius, head_length,
                direction=directions,
            )
            self._handles[layer_name] = backend.handle

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _hide_handle(self, layer_name: str):
        handle = self._handles.get(layer_name)
        if handle is not None:
            handle.visible = False

    def _noop(self):
        pass

    def _snapshot_base_colors(self):
        """Store the current voxel colors as the base palette (once)."""
        if self._base_colors:
            return
        for v in self.voxsym.get_voxels():
            self._base_colors[id(v)] = tuple(int(c) for c in v.color)

    def _restore_base_colors(self):
        """Restore the original voxel colors stored in _base_colors."""
        if not self._base_colors:
            return
        for v in self.voxsym.get_voxels():
            base = self._base_colors.get(id(v))
            if base is not None:
                v.color = base

    @staticmethod
    def _colormap_plasma(t: float) -> tuple:
        """Matplotlib-style plasma: dark purple → magenta → orange → yellow-white."""
        t = np.clip(t, 0.0, 1.0)
        # Piecewise-linear control points (r, g, b) in [0, 255]
        stops = [
            (0.00, 12, 7, 65),
            (0.20, 84, 16, 110),
            (0.40, 160, 40, 130),
            (0.60, 220, 80, 120),
            (0.80, 250, 160, 70),
            (1.00, 240, 249, 33),
        ]
        # Find bracket
        for i in range(len(stops) - 1):
            t0, r0, g0, b0 = stops[i]
            t1, r1, g1, b1 = stops[i + 1]
            if t0 <= t <= t1:
                if t1 == t0:
                    return (r0, g0, b0)
                frac = (t - t0) / (t1 - t0)
                r = int(r0 + frac * (r1 - r0))
                g = int(g0 + frac * (g1 - g0))
                b = int(b0 + frac * (b1 - b0))
                return (r, g, b)
        return (240, 249, 33)

    @staticmethod
    def _colormap_ion(t: float) -> tuple:
        """Blue → cyan → green → yellow for ion concentration."""
        t = np.clip(t, 0.0, 1.0)
        stops = [
            (0.00, 10, 20, 100),
            (0.25, 0, 150, 200),
            (0.50, 0, 200, 100),
            (0.75, 150, 220, 0),
            (1.00, 255, 240, 50),
        ]
        for i in range(len(stops) - 1):
            t0, r0, g0, b0 = stops[i]
            t1, r1, g1, b1 = stops[i + 1]
            if t0 <= t <= t1:
                if t1 == t0:
                    return (r0, g0, b0)
                frac = (t - t0) / (t1 - t0)
                r = int(r0 + frac * (r1 - r0))
                g = int(g0 + frac * (g1 - g0))
                b = int(b0 + frac * (b1 - b0))
                return (r, g, b)
        return (255, 240, 50)

    @staticmethod
    def _colormap_hot(t: float) -> tuple:
        """Simple hot colormap: black -> red -> yellow -> white."""
        t = np.clip(t, 0.0, 1.0)
        r = int(255 * min(1.0, t * 3.0))
        g = int(255 * max(0.0, min(1.0, (t - 0.33) * 3.0)))
        b = int(255 * max(0.0, min(1.0, (t - 0.66) * 3.0)))
        return (r, g, b)

    @staticmethod
    def _colormap_cool(t: float) -> tuple:
        """Blue -> cyan -> green -> yellow -> red."""
        t = np.clip(t, 0.0, 1.0)
        r = int(255 * np.sin(t * np.pi))
        g = int(255 * np.sin(t * np.pi + np.pi / 3))
        b = int(255 * np.cos(t * np.pi / 2))
        return (r, g, b)

    @staticmethod
    def _colormap_jet(t: float) -> tuple:
        """Approximate jet colormap."""
        t = np.clip(t, 0.0, 1.0)
        if t < 0.25:
            return (0, int(255 * (4 * t)), 255)
        elif t < 0.5:
            return (0, 255, int(255 * (2 - 4 * t)))
        elif t < 0.75:
            return (int(255 * (4 * t - 2)), 255, 0)
        else:
            return (255, int(255 * (4 - 4 * t)), 0)
