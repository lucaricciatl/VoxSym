"""VoxSym renderer that delegates to a pluggable backend."""

import numpy as np

from voxsym.visualization.backends.base import RenderBackend


class Renderer:
    """Takes all voxels from a VoxSym and draws all cubes via a render backend.

    Parameters
    ----------
    voxsym : VoxSym
    backend : RenderBackend or None
        Concrete backend that implements :class:`RenderBackend`.  If None,
        rendering is a no-op (headless mode).
    render_scale : float
        Multiply all positions and sizes by this factor before sending
        to the backend.  Use when physics coordinates are very small (e.g. µm)
        and you need the rendered geometry to be at a visible scale.
        Default 1.0 (no scaling).
    """

    def __init__(self, voxsym, backend=None, render_scale: float = 1.0):
        self.voxsym = voxsym
        self.render_scale = float(render_scale)
        self.backend: RenderBackend = backend
        self._handle = None

    @property
    def handle(self):
        """Read-only access to the backend scene handle (None for headless)."""
        if self.backend is None:
            return None
        return self.backend.handle

    def _build_arrays(self):
        """Build per-voxel position/scale/color/opacity arrays."""
        voxels = self.voxsym.get_voxels()
        n = len(voxels)
        if n == 0:
            return (
                np.zeros((0, 3), dtype=np.float32),
                np.zeros((0, 3), dtype=np.float32),
                np.zeros((0, 3), dtype=np.uint8),
                np.ones((0,), dtype=np.float32),
            )

        scl = self.render_scale
        positions = np.zeros((n, 3), dtype=np.float32)
        scales = np.zeros((n, 3), dtype=np.float32)
        colors = np.zeros((n, 3), dtype=np.uint8)
        opacities = np.ones((n,), dtype=np.float32)

        # Cross-section slicing: if the visualizer requests a slice plane,
        # hide voxels on one side of it by setting opacity to zero.
        viz = getattr(self.voxsym, "_visualizer", None)
        cs_axis = getattr(viz, "cross_section_axis", None)
        cs_pos = getattr(viz, "cross_section_pos", 0.0)
        axis_index = {"x": 0, "y": 1, "z": 2}.get(cs_axis) if cs_axis else None

        for i, voxel in enumerate(voxels):
            positions[i] = [voxel.x * scl, voxel.y * scl, voxel.z * scl]
            s = voxel.size * scl
            scales[i] = [s, s, s]
            colors[i] = voxel.color
            opacities[i] = getattr(voxel, "opacity", 1.0)
            if axis_index is not None and positions[i, axis_index] > cs_pos:
                opacities[i] = 0.0

        return positions, scales, colors, opacities

    def render(self):
        """Build arrays and delegate to the backend."""
        if self.backend is None:
            return
        positions, scales, colors, opacities = self._build_arrays()
        self.backend.render(positions, scales, colors, opacities)
