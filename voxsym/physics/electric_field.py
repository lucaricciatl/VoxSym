"""
Electric & magnetic field solvers (vectorized).

Field evaluation is batched: all voxel positions are processed at once
with numpy array operations instead of per-voxel Python loops.

The module also exposes ``build_field_topology`` so that VoxSym can
share a single ``GridTopology`` cache with the diffusion solvers.
"""

import numpy as np
from typing import List, Tuple, Optional

from voxsym.physics.topology import GridTopology


def build_field_topology(voxels) -> Optional[GridTopology]:
    """Build a 6-connectivity topology for the given voxels, if any."""
    if not voxels:
        return None
    return GridTopology(voxels, connectivity=6)


class Field:
    """Base class for spatial vector fields."""

    def __init__(self, name: str = "Field"):
        self.name = name

    def evaluate_batch(
        self, xs: np.ndarray, ys: np.ndarray, zs: np.ndarray, t: float = 0.0,
    ) -> np.ndarray:
        """Return (N, 3) field vectors for N positions at time t."""
        raise NotImplementedError


class UniformField(Field):
    """Constant field in space and time."""

    def __init__(self, vector: Tuple[float, float, float], name: str = "Uniform"):
        super().__init__(name)
        self.vector = np.array(vector, dtype=np.float64)

    def evaluate_batch(
        self, xs: np.ndarray, ys: np.ndarray, zs: np.ndarray, t: float = 0.0,
    ) -> np.ndarray:
        n = len(xs)
        out = np.empty((n, 3), dtype=np.float64)
        out[:] = self.vector
        return out


class PointChargeField(Field):
    """Electric field from a point charge: E = k·q / r² · r_hat."""

    def __init__(
        self,
        charge: float,
        position: Tuple[float, float, float],
        name: str = "PointCharge",
        k: float = 8.9875517923e9,
    ):
        super().__init__(name)
        self.charge = charge
        self.pos = np.array(position, dtype=np.float64)
        self.k = k

    def evaluate_batch(
        self, xs: np.ndarray, ys: np.ndarray, zs: np.ndarray, t: float = 0.0,
    ) -> np.ndarray:
        rx = xs - self.pos[0]
        ry = ys - self.pos[1]
        rz = zs - self.pos[2]
        r2 = rx * rx + ry * ry + rz * rz
        r = np.sqrt(r2)
        # Avoid division by zero
        safe = np.where(r < 1e-12, 1.0, r)
        factor = self.k * self.charge / (safe * safe * safe)
        # Zero out singular points
        factor[r < 1e-12] = 0.0
        out = np.empty((len(xs), 3), dtype=np.float64)
        out[:, 0] = factor * rx
        out[:, 1] = factor * ry
        out[:, 2] = factor * rz
        return out


class OscillatingField(Field):
    """Field that oscillates sinusoidally in time."""

    def __init__(
        self,
        amplitude: Tuple[float, float, float],
        frequency: float,
        phase: float = 0.0,
        name: str = "Oscillating",
    ):
        super().__init__(name)
        self.amplitude = np.array(amplitude, dtype=np.float64)
        self.frequency = frequency
        self.phase = phase

    def evaluate_batch(
        self, xs: np.ndarray, ys: np.ndarray, zs: np.ndarray, t: float = 0.0,
    ) -> np.ndarray:
        factor = np.sin(2.0 * np.pi * self.frequency * t + self.phase)
        n = len(xs)
        out = np.empty((n, 3), dtype=np.float64)
        out[:] = self.amplitude * factor
        return out


class SpatialGradientField(Field):
    """Linear spatial gradient field, e.g. E = E0 + grad·axis."""

    def __init__(
        self,
        offset: Tuple[float, float, float],
        gradient: Tuple[float, float, float],
        axis: str = "x",
        name: str = "Gradient",
    ):
        super().__init__(name)
        self.offset = np.array(offset, dtype=np.float64)
        self.gradient = np.array(gradient, dtype=np.float64)
        self._axis_idx = {"x": 0, "y": 1, "z": 2}[axis]

    def evaluate_batch(
        self, xs: np.ndarray, ys: np.ndarray, zs: np.ndarray, t: float = 0.0,
    ) -> np.ndarray:
        coords = [xs, ys, zs]
        n = len(xs)
        out = np.empty((n, 3), dtype=np.float64)
        out[:] = self.offset
        out += np.outer(coords[self._axis_idx], self.gradient)
        return out


# ======================================================================
# Field managers
# ======================================================================

class FieldManager:
    """Manages multiple Field sources and applies them to voxels (vectorized)."""

    def __init__(self):
        self.fields: List[Field] = []

    def add_field(self, field: Field):
        self.fields.append(field)

    def clear_fields(self):
        self.fields.clear()

    def apply_to_voxels(self, voxels: List, t: float = 0.0):
        """Evaluate all fields on all voxels in a single vectorized pass."""
        n = len(voxels)
        if n == 0 or not self.fields:
            return

        # Extract positions
        xs = np.array([v.x for v in voxels], dtype=np.float64)
        ys = np.array([v.y for v in voxels], dtype=np.float64)
        zs = np.array([v.z for v in voxels], dtype=np.float64)

        # Sum all field contributions
        total = np.zeros((n, 3), dtype=np.float64)
        for field in self.fields:
            total += field.evaluate_batch(xs, ys, zs, t)

        # Write back to voxels
        self._store_batch(voxels, total)

    def _store_batch(self, voxels: List, values: np.ndarray):
        raise NotImplementedError


class ElectricFieldManager(FieldManager):
    def _store_batch(self, voxels: List, values: np.ndarray):
        for i, v in enumerate(voxels):
            v.electric_field = values[i]

    def compute_force(self, voxel) -> np.ndarray:
        return voxel.charge * voxel.electric_field

    def compute_potential_energy(self, voxel) -> float:
        return -voxel.charge * np.dot(
            voxel.electric_field, [voxel.x, voxel.y, voxel.z],
        )


class MagneticFieldManager(FieldManager):
    def _store_batch(self, voxels: List, values: np.ndarray):
        for i, v in enumerate(voxels):
            v.magnetic_field = values[i]

    def compute_lorentz_force(self, voxel, velocity: np.ndarray) -> np.ndarray:
        return voxel.charge * np.cross(velocity, voxel.magnetic_field)


# ======================================================================
# Combined solver
# ======================================================================

class ElectromagneticSolver:
    """Combined E + B manager with convenience methods."""

    def __init__(self):
        self.electric = ElectricFieldManager()
        self.magnetic = MagneticFieldManager()

    def add_uniform_electric(self, ex: float, ey: float, ez: float):
        self.electric.add_field(UniformField((ex, ey, ez), name="E_uniform"))

    def add_uniform_magnetic(self, bx: float, by: float, bz: float):
        self.magnetic.add_field(UniformField((bx, by, bz), name="B_uniform"))

    def add_point_charge(self, charge: float, x: float, y: float, z: float):
        self.electric.add_field(PointChargeField(charge, (x, y, z)))

    def add_oscillating_electric(
        self, ax: float, ay: float, az: float,
        frequency: float, phase: float = 0.0,
    ):
        self.electric.add_field(
            OscillatingField((ax, ay, az), frequency, phase, name="E_osc"),
        )

    def add_gradient_electric(
        self, offset: Tuple[float, float, float],
        grad: Tuple[float, float, float], axis: str = "x",
    ):
        self.electric.add_field(
            SpatialGradientField(offset, grad, axis, name="E_grad"),
        )

    def apply_to_voxels(self, voxels: List, t: float = 0.0):
        self.electric.apply_to_voxels(voxels, t)
        self.magnetic.apply_to_voxels(voxels, t)

    def clear(self):
        self.electric.clear_fields()
        self.magnetic.clear_fields()
