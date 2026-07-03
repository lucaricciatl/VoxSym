"""
Heat generator — inject heat into voxel regions (vectorized).

All region operations use numpy boolean masks instead of per-voxel
Python loops.
"""

import numpy as np
from typing import Tuple, Optional
from voxsym.voxsym import VoxSym


class HeatGenerator:
    """Inject heat into specific voxels or regions of a VoxSym grid.

    Works alongside the HeatDiffusion solver.  All region operations
    are vectorized with numpy masks.

    Usage::

        gen = HeatGenerator(vs)
        gen.pulse_region((0, 0, 0), radius=2.0, delta_T=200.0)
        gen.pulse_voxel(42, delta_T=500.0)
    """

    def __init__(self, voxsym: VoxSym):
        self.voxsym = voxsym

    # ------------------------------------------------------------------
    # Position arrays (cached, rebuilt when voxels change)
    # ------------------------------------------------------------------

    def _positions(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (xs, ys, zs) arrays for all voxels."""
        voxels = self.voxsym.get_voxels()
        xs = np.array([v.x for v in voxels], dtype=np.float64)
        ys = np.array([v.y for v in voxels], dtype=np.float64)
        zs = np.array([v.z for v in voxels], dtype=np.float64)
        return xs, ys, zs

    # ------------------------------------------------------------------
    # Single-voxel operations
    # ------------------------------------------------------------------

    def pulse_voxel(self, index: int, delta_T: float):
        voxels = self.voxsym.get_voxels()
        if 0 <= index < len(voxels):
            voxels[index].temperature += delta_T

    def set_fixed_voxel(self, index: int, temperature: float):
        voxels = self.voxsym.get_voxels()
        if 0 <= index < len(voxels):
            v = voxels[index]
            v.temperature = temperature
            self.voxsym.add_fixed_temperature(
                (v.x, v.y, v.z), radius=0.1, temperature=temperature,
            )

    # ------------------------------------------------------------------
    # Region operations (vectorized)
    # ------------------------------------------------------------------

    def pulse_region(
        self,
        center: Tuple[float, float, float],
        radius: float,
        delta_T: float,
    ):
        """Raise temperature of all voxels inside a sphere."""
        xs, ys, zs = self._positions()
        cx, cy, cz = center
        r2 = radius * radius
        mask = (xs - cx) ** 2 + (ys - cy) ** 2 + (zs - cz) ** 2 <= r2
        if mask.any():
            voxels = self.voxsym.get_voxels()
            for i in np.where(mask)[0]:
                voxels[i].temperature += delta_T

    def set_fixed_region(
        self,
        center: Tuple[float, float, float],
        radius: float,
        temperature: float,
    ):
        self.voxsym.set_region_temperature(center, radius, temperature)

    # ------------------------------------------------------------------
    # Pattern operations (vectorized)
    # ------------------------------------------------------------------

    def pulse_plane(
        self,
        axis: str,
        value: float,
        delta_T: float,
        thickness: float = 1.0,
    ):
        """Heat all voxels near a plane."""
        xs, ys, zs = self._positions()
        half = thickness / 2.0
        coords = {"x": xs, "y": ys, "z": zs}
        if axis not in coords:
            raise ValueError(f"Unknown axis '{axis}'")
        mask = np.abs(coords[axis] - value) <= half
        if mask.any():
            voxels = self.voxsym.get_voxels()
            for i in np.where(mask)[0]:
                voxels[i].temperature += delta_T

    def pulse_line(
        self,
        start: Tuple[float, float, float],
        end: Tuple[float, float, float],
        radius: float,
        delta_T: float,
    ):
        """Heat voxels along a line segment (cylinder)."""
        xs, ys, zs = self._positions()
        start = np.array(start, dtype=np.float64)
        end = np.array(end, dtype=np.float64)
        direction = end - start
        length = float(np.linalg.norm(direction))
        if length < 1e-12:
            self.pulse_region(tuple(start), radius, delta_T)
            return
        direction /= length
        r2 = radius * radius

        # Vectorized point-to-segment distance
        points = np.column_stack([xs, ys, zs])
        t = np.clip(np.dot(points - start, direction), 0.0, length)
        closest = start + np.outer(t, direction)
        dist2 = np.sum((points - closest) ** 2, axis=1)
        mask = dist2 <= r2

        if mask.any():
            voxels = self.voxsym.get_voxels()
            for i in np.where(mask)[0]:
                voxels[i].temperature += delta_T

    # ------------------------------------------------------------------
    # Time-varying patterns
    # ------------------------------------------------------------------

    def pulse_oscillating(
        self,
        center: Tuple[float, float, float],
        radius: float,
        amplitude: float,
        frequency: float,
        time: float,
    ):
        """Sinusoidal heat pulse: ΔT = amplitude · sin(2π·f·t)."""
        delta = amplitude * np.sin(2.0 * np.pi * frequency * time)
        self.pulse_region(center, radius, delta)

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def reset_all(self, temperature: float = 300.0):
        """Set every voxel to the same temperature."""
        for v in self.voxsym.get_voxels():
            v.temperature = temperature

    def find_voxel_at(self, x: float, y: float, z: float) -> Optional[int]:
        """Return the index of the voxel closest to (x, y, z)."""
        xs, ys, zs = self._positions()
        d2 = (xs - x) ** 2 + (ys - y) ** 2 + (zs - z) ** 2
        idx = int(np.argmin(d2))
        return idx if d2[idx] < float("inf") else None
