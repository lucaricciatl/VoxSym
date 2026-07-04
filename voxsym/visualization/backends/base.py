"""Base interface for VoxSym render backends.

A render backend receives per-voxel geometry arrays and pushes them to a
concrete display implementation (Viser, WebGL, headless, ...).
"""

from abc import ABC, abstractmethod
from typing import Optional


class RenderBackend(ABC):
    """Abstract render backend for voxel-based visualization.

    Implementations must accept pre-built numpy arrays and draw/update the
    voxel scene. Optional vector overlays (arrows) are added separately.
    """

    @abstractmethod
    def render(self, positions, scales, colors, opacities):
        """Render or update the batched voxel mesh.

        Parameters
        ----------
        positions : array-like, shape (N, 3)
            Voxel center positions in the backend's display units.
        scales : array-like, shape (N, 3)
            Per-instance scale factors.
        colors : array-like, shape (N, 3)
            Per-instance RGB colors (uint8).
        opacities : array-like, shape (N,)
            Per-instance opacity values in [0, 1].
        """
        ...

    @abstractmethod
    def add_arrows(self, points, colors, shaft_radius, head_radius, head_length, direction=None):
        """Add or update a batch of arrow glyphs.

        Parameters
        ----------
        points : array-like, shape (N, 2, 3)
            Arrow tail/head points.
        colors : array-like, shape (N, 3)
            Per-arrow RGB colors.
        shaft_radius : float
        head_radius : float
        head_length : float
        direction : array-like, shape (N, 3), optional
            Normalized arrow direction vectors, explicit for unambiguous orientation.
        """
        ...

    @abstractmethod
    def set_opacity(self, opacity: float):
        """Set the global opacity multiplier for rendered voxels."""
        ...

    @abstractmethod
    def clear(self):
        """Remove all rendered geometry managed by this backend."""
        ...

    @property
    @abstractmethod
    def handle(self) -> Optional[object]:
        """Implementation-specific scene handle, if any."""
        ...
