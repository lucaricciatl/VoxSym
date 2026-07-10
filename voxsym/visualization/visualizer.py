"""Connects to Renderer and adds optional overlay layers (fields, temperature, etc.)."""

import numpy as np
from typing import Dict, List, Set, Callable, Optional

from voxsym.voxel import Voxel
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
    EFFECTIVE_CONDUCTIVITY = "effective_conductivity"


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
        voxsym,
        renderer: Renderer,
    ):
        self.server = server
        self.voxsym = voxsym
        self.renderer = renderer
        self._active: Set[str] = {Layer.MATERIAL}
        self._handles: Dict[str, Optional[object]] = {}

        self._callbacks: Dict[str, Callable] = {
            Layer.ELECTRIC_FIELD: self._render_electric_field,
            Layer.MAGNETIC_FIELD: self._render_magnetic_field,
            Layer.CURRENT: self._render_current,
        }
        # Snapshot of original voxel colors so we can restore them when a
        # scalar overlay layer is switched off.
        self._base_colors: Dict[int, tuple] = {}
        # Layer parameters
        self.field_arrow_scale = 1.2      # length scale for arrow display
        self.field_subsample = 4            # show every 4th arrow per axis
        self.field_color_mode = "direction"  # "direction" | "magnitude"

        # Cross-section (mobile slicing plane)
        self.cross_section_axis: Optional[str] = None  # None, 'x', 'y', 'z'
        self.cross_section_pos: float = 0.0

        # Per-layer scalar normalization range and raw values for colorbar/probe UI.
        self._scalar_range: Dict[str, Tuple[float, float]] = {}
        self._scalar_values: Dict[str, List[float]] = {}
        self._active_scalar: str = Layer.MATERIAL

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

    def activate_scalar(self, name: str):
        """Activate a scalar layer and disable the other scalar layers."""
        self.set_layer(name, active=True)

    def set_layer(self, name: str, active: bool = True):
        """Toggle a visualization layer on/off.

        Scalar color layers (temperature, material, ion concentration,
        base colour, effective conductivity) are mutually exclusive: activating
        one deactivates the others.  Vector overlay layers (E/B-field, current)
        can coexist.
        """
        scalar_layers = {
            Layer.TEMPERATURE,
            Layer.MATERIAL,
            Layer.ION_CONCENTRATION,
            Layer.EFFECTIVE_CONDUCTIVITY,
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
            # Vector overlays are drawn by the renderer; do not mutate
            # scalar colors or EM state here.
        else:
            self._active.discard(name)
            if name in self._handles and self._handles[name] is not None:
                self._handles[name].visible = False
        # Ensure the material layer is active by default
        if not self._active.intersection(scalar_layers):
            self._active.add(Layer.MATERIAL)
            self._base_colors_restored = False

    def set_layers_from_message(self, active: List[str]):
        """Bulk-update active layers from a client message and re-render."""
        self._active = set(active)
        if not self._active:
            self._active.add(Layer.MATERIAL)

    def toggle_layer(self, name: str) -> bool:
        """Flip layer state. Returns new state."""
        is_active = name in self._active
        self.set_layer(name, not is_active)
        return not is_active

    def is_active(self, name: str) -> bool:
        return name in self._active

    def render(self):
        """Render base voxels + all active overlay layers."""
        backend = getattr(self.renderer, "backend", None)
        if backend is not None and hasattr(backend, "clear_arrows"):
            backend.clear_arrows()

        # Compute vector overlays first so their arrow data is available to
        # the backend when we serialize the frame below.
        # Snapshot the set in case another thread mutates it via set_layer().
        active = list(self._active)
        for name in active:
            if name in self._callbacks:
                self._callbacks[name]()

        # If no vector layer is active, hide the arrow mesh handles entirely.
        for layer_name in (Layer.ELECTRIC_FIELD, Layer.MAGNETIC_FIELD, Layer.CURRENT):
            if layer_name not in self._active:
                self._hide_handle(layer_name)

        # Serialize the merged frame through the renderer backend.
        self._encode_latest_frame()

    def maybe_skip_frame(self) -> bool:
        """Return True if we should skip this render to save bandwidth.

        Uses a target frame interval so the WebSocket is not flooded when
        the simulation loop runs faster than the browser can render.
        """
        import time
        now = time.perf_counter()
        target = getattr(self, "_target_frame_interval", 1.0 / 30.0)
        last = getattr(self, "_last_render_time", 0.0)
        if now - last < target:
            return True
        self._last_render_time = now
        return False

    def request_render(self):
        """Schedule a frame render + broadcast, skipping only the throttle gate."""
        if not self.maybe_skip_frame():
            self.render()

    def reset_layers(self):
        """Return to default material visualization."""
        self._active = {Layer.MATERIAL}
        self._restore_base_colors()
        for name in (Layer.ELECTRIC_FIELD, Layer.MAGNETIC_FIELD, Layer.CURRENT):
            self._hide_handle(name)

    # ------------------------------------------------------------------
    # Frame encoding
    # ------------------------------------------------------------------

    def _encode_latest_frame(self):
        self._apply_scalar_colors()
        self.renderer.render()

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
        self._active = {Layer.MATERIAL}
        self._base_colors_restored = False

    # ------------------------------------------------------------------
    # Scalar layers – applied by mutating voxel.color before render()
    # ------------------------------------------------------------------

    def _apply_scalar_colors(self):
        """If a scalar layer is active, compute colors and write them to voxels."""
        scalar_priority = [
            Layer.ION_CONCENTRATION,
            Layer.EFFECTIVE_CONDUCTIVITY,
            Layer.TEMPERATURE,
            Layer.MATERIAL,
            Layer.VOXEL_COLOR,
        ]
        for layer in scalar_priority:
            if layer in self._active:
                self._active_scalar = layer
                if layer == Layer.ION_CONCENTRATION:
                    self._snapshot_base_colors()
                    vals = [v.ion_concentration for v in self.voxsym.get_voxels()]
                    self._record_scalar(layer, vals)
                    self._color_by_ion_concentration()
                elif layer == Layer.EFFECTIVE_CONDUCTIVITY:
                    self._snapshot_base_colors()
                    vals = [v.effective_conductivity for v in self.voxsym.get_voxels()]
                    self._record_scalar(layer, vals)
                    self._color_by_effective_conductivity()
                elif layer == Layer.TEMPERATURE:
                    self._snapshot_base_colors()
                    vals = [v.temperature for v in self.voxsym.get_voxels()]
                    self._record_scalar(layer, vals)
                    self._color_by_temperature()
                elif layer == Layer.MATERIAL:
                    self._snapshot_base_colors()
                    self._scalar_range.pop(layer, None)
                    self._color_by_material()
                elif layer == Layer.VOXEL_COLOR:
                    self._restore_base_colors()
                break

    def _record_scalar(self, layer, values):
        if values:
            self._scalar_values[layer] = [float(v) for v in values]
            v_min = float(min(values))
            v_max = float(max(values))
            self._scalar_range[layer] = [v_min, v_max]
        else:
            self._scalar_values[layer] = []
            self._scalar_range[layer] = [0.0, 1.0]

    @staticmethod
    def _normalize(values, colormap):
        """Normalize *values* to [0, 1] and map them through *colormap*."""
        if not values:
            return []
        v_min = float(min(values))
        v_max = float(max(values))
        span = v_max - v_min
        if span < 1e-12:
            return [colormap(0.0) for _ in values]
        return [colormap((v - v_min) / span) for v in values]

    def _color_by_temperature(self):
        """Map voxel temperatures to colors using a normalized plasma colormap."""
        voxels = self.voxsym.get_voxels()
        if not voxels:
            return
        colors = self._normalize(
            [v.temperature for v in voxels], self._colormap_plasma
        )
        for voxel, color in zip(voxels, colors):
            voxel.color = color

    def _color_by_material(self):
        voxels = self.voxsym.get_voxels()
        for voxel in voxels:
            if voxel.material is not None:
                voxel.color = voxel.material.color
            else:
                voxel.color = (180, 180, 180)

    def _color_by_ion_concentration(self):
        """Map ion concentration to a normalized plasma heatmap."""
        voxels = self.voxsym.get_voxels()
        if not voxels:
            return
        colors = self._normalize(
            [v.ion_concentration for v in voxels], self._colormap_plasma
        )
        for voxel, color in zip(voxels, colors):
            voxel.color = color

    def _color_by_effective_conductivity(self):
        """Map ion-intercalation dependent conductivity to viridis."""
        voxels = self.voxsym.get_voxels()
        if not voxels:
            return
        sigmas = [v.effective_conductivity for v in voxels]
        colors = self._normalize(sigmas, self._colormap_viridis)
        for voxel, color in zip(voxels, colors):
            voxel.color = color

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
        head_radius = 0.06 * base_size
        head_length = 0.10 * base_size * self.field_arrow_scale

        for i, (voxel, vec, mag) in enumerate(vecs):
            direction = vec / mag if mag > 1e-12 else np.zeros(3)
            directions[i] = direction.astype(np.float32)
            # Relative strength in [0, 1].
            strength = mag / max_mag
            # Arrow length in rendered units: at least a fraction of the voxel
            # size (so orientation is always readable) and up to ~1 voxel size.
            length = (
                base_size
                * self.field_arrow_scale
                * (0.25 + 0.55 * strength)
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
    def _colormap_viridis(t: float) -> tuple:
        """Matplotlib-style viridis: dark purple -> teal -> yellow."""
        t = np.clip(t, 0.0, 1.0)
        if t < 0.25:
            r = int(68 + (59 - 68) * (t / 0.25))
            g = int(1 + (76 - 1) * (t / 0.25))
            b = int(84 + (192 - 84) * (t / 0.25))
        elif t < 0.5:
            r = int(59 + (33 - 59) * ((t - 0.25) / 0.25))
            g = int(76 + (144 - 76) * ((t - 0.25) / 0.25))
            b = int(192 + (140 - 192) * ((t - 0.25) / 0.25))
        elif t < 0.75:
            r = int(33 + (93 - 33) * ((t - 0.5) / 0.25))
            g = int(144 + (201 - 144) * ((t - 0.5) / 0.25))
            b = int(140 + (99 - 140) * ((t - 0.5) / 0.25))
        else:
            r = int(93 + (252 - 93) * ((t - 0.75) / 0.25))
            g = int(201 + (229 - 201) * ((t - 0.75) / 0.25))
            b = int(99 + (30 - 99) * ((t - 0.75) / 0.25))
        return (r, g, b)

    @staticmethod
    def _colormap_plasma(t: float) -> tuple:
        """Matplotlib-style plasma: dark purple -> magenta -> orange → yellow-white."""
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
