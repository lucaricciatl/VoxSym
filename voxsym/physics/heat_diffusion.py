"""
Heat diffusion solver — finite-difference thermal conduction.

Vectorized implementation using edge-list format and numpy operations.
"""

import numpy as np
from typing import Tuple, Optional
from voxsym.voxel import Voxel
from voxsym.voxsym import VoxSym
from voxsym.physics.topology import GridTopology


class HeatDiffusion:
    """Finite-difference thermal conduction solver (vectorized).

    Two-phase usage::

        new_temps = solver.compute_step(dt)
        for i, v in enumerate(voxels):
            v.temperature = new_temps[i]
    """

    def __init__(self, voxsym: VoxSym):
        self.voxsym = voxsym

        # Shared topology cache; rebuilt when the voxel grid changes.
        self._topology: Optional[GridTopology] = None
        self._topology_voxel_count = -1

        # Edge-list format for the neighbor graph
        self._edge_src = None   # (E,) int32
        self._edge_dst = None   # (E,) int32

        # Material arrays  (N,)
        self._k = None          # thermal conductivity [W/(m·K)]
        self._rho_cp = None     # density × specific_heat [J/(m³·K)]
        self._dx = None         # voxel size [m]

        # Sources / boundaries
        self._heat_sources: list[Tuple[Tuple[float, float, float], float, float]] = []
        self._fixed_regions: list[Tuple[Tuple[float, float, float], float, float]] = []

        self._built = False

    # ------------------------------------------------------------------
    # Build flat arrays from voxel grid (once)
    # ------------------------------------------------------------------

    def _build_arrays(self):
        if self._built and self._topology_voxel_count == len(self.voxsym.get_voxels()):
            return

        voxels = self.voxsym.get_voxels()
        n = len(voxels)
        if n == 0:
            self._topology = GridTopology([])
            self._topology_voxel_count = 0
            self._edge_src = self._topology.edges_src
            self._edge_dst = self._topology.edges_dst
            self._k = np.array([], dtype=np.float64)
            self._rho_cp = np.array([], dtype=np.float64)
            self._dx = np.array([], dtype=np.float64)
            self._built = True
            return

        # --- shared topology ---
        self._topology = GridTopology(voxels, connectivity=6)
        self._topology_voxel_count = n
        self._edge_src = self._topology.edges_src
        self._edge_dst = self._topology.edges_dst

        # --- material arrays ---
        self._k = np.zeros(n, dtype=np.float64)
        self._rho_cp = np.zeros(n, dtype=np.float64)
        self._dx = np.zeros(n, dtype=np.float64)

        for idx, v in enumerate(voxels):
            self._dx[idx] = float(v.size)
            if v.material is not None:
                self._k[idx] = float(v.material.thermal_conductivity)
                rho = float(v.material.density)
                cp = float(v.material.specific_heat)
                if rho > 0 and cp > 0:
                    self._rho_cp[idx] = rho * cp

        self._built = True

    # ------------------------------------------------------------------
    # Source / boundary management
    # ------------------------------------------------------------------

    def add_heat_source(self, center, radius, power):
        self._heat_sources.append((center, radius, power))

    def add_fixed_temperature(self, center, radius, temperature):
        self._fixed_regions.append((center, radius, temperature))

    def clear_sources(self):
        self._heat_sources.clear()
        self._fixed_regions.clear()

    # ------------------------------------------------------------------
    # Two-phase compute
    # ------------------------------------------------------------------

    def compute_step(self, dt: Optional[float] = None) -> np.ndarray:
        self._build_arrays()
        voxels = self.voxsym.get_voxels()
        n = len(voxels)
        if n == 0:
            return np.array([], dtype=np.float64)

        if dt is None:
            dt = self.voxsym.get_time_step()

        temps = np.array([v.temperature for v in voxels], dtype=np.float64)

        # ---- vectorized diffusion ----
        new_temps = self._diffusion_step(temps, dt)

        # ---- heat sources ----
        for (cx, cy, cz), radius, power in self._heat_sources:
            self._apply_heat_source(new_temps, cx, cy, cz, radius, power, dt)

        # ---- Dirichlet boundaries ----
        for (cx, cy, cz), radius, fixed_T in self._fixed_regions:
            self._apply_fixed_temp(new_temps, cx, cy, cz, radius, fixed_T)

        return new_temps

    # ------------------------------------------------------------------
    # Vectorized diffusion kernel
    # ------------------------------------------------------------------

    def _diffusion_step(self, temps: np.ndarray, dt: float) -> np.ndarray:
        """Single explicit diffusion step — fully vectorized."""
        src = self._edge_src
        dst = self._edge_dst

        # Harmonic-mean interface conductivity
        k_src = self._k[src]
        k_dst = self._k[dst]
        k_sum = k_src + k_dst
        # k_avg = 2·k₁·k₂/(k₁+k₂), with safe division
        with np.errstate(divide='ignore', invalid='ignore'):
            k_avg = np.where(k_sum > 0, 2.0 * k_src * k_dst / k_sum, 0.0)

        # Temperature difference along each edge
        t_diff = temps[dst] - temps[src]

        # Weight = k_avg / (ρ·cₚ·dx²)
        denom = self._rho_cp[src] * self._dx[src] * self._dx[src]
        valid = denom > 0
        weights = np.zeros(len(src), dtype=np.float64)
        weights[valid] = k_avg[valid] / denom[valid]

        # Scatter contributions to source voxels
        dT = np.zeros(len(temps), dtype=np.float64)
        np.add.at(dT, src, weights * t_diff)

        return temps + dt * dT

    # ------------------------------------------------------------------
    # Vectorized source / boundary helpers
    # ------------------------------------------------------------------

    def _apply_heat_source(
        self, temps: np.ndarray,
        cx: float, cy: float, cz: float,
        radius: float, power: float, dt: float,
    ):
        """Distribute heat-source power across a spherical region."""
        voxels = self.voxsym.get_voxels()
        xs = np.array([v.x for v in voxels])
        ys = np.array([v.y for v in voxels])
        zs = np.array([v.z for v in voxels])

        r2 = radius * radius
        mask = (xs - cx) ** 2 + (ys - cy) ** 2 + (zs - cz) ** 2 <= r2
        if not mask.any():
            return

        vol = self._dx[mask] ** 3
        thermal_mass = self._rho_cp[mask] * vol
        total_mass = thermal_mass.sum()
        if total_mass > 0:
            # Equal temperature rise for all affected voxels
            temps[mask] += power * dt / total_mass

    def _apply_fixed_temp(
        self, temps: np.ndarray,
        cx: float, cy: float, cz: float,
        radius: float, fixed_T: float,
    ):
        """Pin a spherical region to a fixed temperature."""
        voxels = self.voxsym.get_voxels()
        xs = np.array([v.x for v in voxels])
        ys = np.array([v.y for v in voxels])
        zs = np.array([v.z for v in voxels])

        r2 = radius * radius
        mask = (xs - cx) ** 2 + (ys - cy) ** 2 + (zs - cz) ** 2 <= r2
        temps[mask] = fixed_T

    # ------------------------------------------------------------------
    # Legacy single-phase step
    # ------------------------------------------------------------------

    def step(self, dt: Optional[float] = None):
        new_temps = self.compute_step(dt)
        voxels = self.voxsym.get_voxels()
        for i, v in enumerate(voxels):
            v.temperature = float(new_temps[i])

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def temperature_stats(self) -> Tuple[float, float, float]:
        temps = [v.temperature for v in self.voxsym.get_voxels()]
        if not temps:
            return 0.0, 0.0, 0.0
        return min(temps), max(temps), sum(temps) / len(temps)
