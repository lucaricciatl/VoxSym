"""
Coupled mechanics, optics and induced-magnetism solver.

This is a small-signal explicit update that uses the existing material
properties in :class:`Material`:

* Mechanical: density, Young's modulus, Poisson ratio, thermal expansion
  → thermo-elastic stress wave propagation with damping.
* Optical: refractive index, absorption coefficient
  → Beer-Lambert light intensity attenuation along +z.
* Magnetic: permeability, magnetic susceptibility
  → induced magnetization M = χ_m · H in linear media, plus thermal
    demagnetization at high temperature.

Units are SI. All updates are applied in-place in a single vectorized
pass; the solver is intended for visualisation of coupled physics rather
than high-accuracy FEA.
"""

import numpy as np
from typing import Tuple, Optional
from voxsym.voxel import Voxel
from voxsym.voxsym import VoxSym


# ---------------------------------------------------------------------------
# Voigt notation helpers
# ---------------------------------------------------------------------------

_STRESS_ORDER = {
    "xx": 0, "yy": 1, "zz": 2, "xy": 3, "xz": 4, "yz": 5,
}


def _young_poisson_to_lame(E: float, nu: float) -> Tuple[float, float]:
    """Return (Lamé first parameter λ, shear modulus μ)."""
    mu = E / (2.0 * (1.0 + nu))
    lam = E * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))
    return lam, mu


class MechanicsOpticsMagnetism:
    """Coupled small-signal mechanics / optics / induced-magnetism solver.

    The solver operates on the VoxSym voxel list. It builds flat arrays
    once and then updates displacement, velocity, stress, optical
    intensity, and magnetization each step.

    Typical usage inside a VoxSym callback::

        mom = MechanicsOpticsMagnetism(vs)
        mom.add_optical_source((0, 0, -5), (0, 0, 1), 1.0)
        mom.set_external_magnetic_field((0, 0, 1e5))

        @vs.on_update
        def step():
            mom.step(dt=1e-6)
            vs.step_and_update(dt=1e-6)
    """

    def __init__(self, voxsym: VoxSym):
        self.voxsym = voxsym

        self._built = False
        # Material arrays (N,)
        self._rho = None          # density [kg/m³]
        self._E = None            # Young's modulus [Pa]
        self._nu = None           # Poisson ratio
        self._lam = None          # Lamé λ [Pa]
        self._mu = None           # Lamé μ (shear modulus) [Pa]
        self._alpha = None        # thermal expansion [1/K]
        self._n_ref = None        # refractive index
        self._absorb = None       # absorption coefficient [1/m]
        self._mu0 = None          # magnetic permeability μ = μ0·μ_r [H/m]
        self._chi = None          # magnetic susceptibility
        self._dx = None           # voxel size [m]
        # Edge list and axis arrays
        self._edge_src = None
        self._edge_dst = None
        self._edge_dir = None     # (E, 3) unit direction from src to dst
        self._edge_len = None     # (E,) distance between src and dst

        # Sources / fields
        self._external_B: Optional[np.ndarray] = None
        self._external_H: Optional[np.ndarray] = None
        self._optical_sources: list[Tuple[Tuple[float, float, float],
                                         Tuple[float, float, float], float]] = []

    # ------------------------------------------------------------------
    # Build flat arrays from voxel grid (once)
    # ------------------------------------------------------------------

    def _build_arrays(self):
        if self._built:
            return
        voxels = self.voxsym.get_voxels()
        n = len(voxels)
        if n == 0:
            self._built = True
            return

        self._rho = np.zeros(n, dtype=np.float64)
        self._E = np.zeros(n, dtype=np.float64)
        self._nu = np.zeros(n, dtype=np.float64)
        self._lam = np.zeros(n, dtype=np.float64)
        self._mu = np.zeros(n, dtype=np.float64)
        self._alpha = np.zeros(n, dtype=np.float64)
        self._n_ref = np.ones(n, dtype=np.float64)
        self._absorb = np.zeros(n, dtype=np.float64)
        self._mu0 = np.full(n, 4.0 * np.pi * 1e-7, dtype=np.float64)
        self._chi = np.zeros(n, dtype=np.float64)
        self._dx = np.zeros(n, dtype=np.float64)

        for idx, v in enumerate(voxels):
            self._dx[idx] = float(v.size)
            if v.material is None:
                continue
            m = v.material
            self._rho[idx] = float(m.density)
            self._E[idx] = float(m.youngs_modulus)
            nu = float(m.poisson_ratio)
            self._nu[idx] = nu
            lam, mu = _young_poisson_to_lame(m.youngs_modulus, nu)
            self._lam[idx] = lam
            self._mu[idx] = mu
            self._alpha[idx] = float(m.thermal_expansion)
            self._n_ref[idx] = float(m.refractive_index)
            self._absorb[idx] = float(m.absorption_coeff)
            self._mu0[idx] *= float(m.permeability)
            self._chi[idx] = float(m.magnetic_susceptibility)

        # Edge list (face-connected neighbours)
        coord_to_idx = {}
        for idx, v in enumerate(voxels):
            key = (
                int(round(v.x / v.size)),
                int(round(v.y / v.size)),
                int(round(v.z / v.size)),
            )
            coord_to_idx[key] = idx

        dirs = np.array([
            (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)
        ], dtype=np.float64)
        src_list = []
        dst_list = []
        dir_list = []
        len_list = []
        for idx, v in enumerate(voxels):
            base = (
                int(round(v.x / v.size)),
                int(round(v.y / v.size)),
                int(round(v.z / v.size)),
            )
            for d in dirs:
                nkey = (base[0] + int(d[0]), base[1] + int(d[1]), base[2] + int(d[2]))
                if nkey in coord_to_idx:
                    src_list.append(idx)
                    dst_list.append(coord_to_idx[nkey])
                    dir_list.append(d)
                    len_list.append(float(v.size))

        self._edge_src = np.array(src_list, dtype=np.int32)
        self._edge_dst = np.array(dst_list, dtype=np.int32)
        self._edge_dir = np.array(dir_list, dtype=np.float64)
        self._edge_len = np.array(len_list, dtype=np.float64)

        self._built = True

    # ------------------------------------------------------------------
    # Source / boundary configuration
    # ------------------------------------------------------------------

    def set_external_magnetic_field(self, B: Tuple[float, float, float]):
        """Set a uniform applied B-field [T] for induced magnetisation."""
        self._external_B = np.array(B, dtype=np.float64)

    def set_external_magnetic_field_H(self, H: Tuple[float, float, float]):
        """Set a uniform applied H-field [A/m] for induced magnetisation."""
        self._external_H = np.array(H, dtype=np.float64)

    def add_optical_source(
        self,
        origin: Tuple[float, float, float],
        direction: Tuple[float, float, float],
        intensity: float,
    ):
        """Add a directed light source at *origin* pointing along *direction*.

        The ray propagates in a straight line and attenuates according to
        each voxel's refractive index and absorption coefficient. Multiple
        sources are supported.
        """
        self._optical_sources.append((origin, direction, intensity))

    def clear_optical_sources(self):
        self._optical_sources.clear()

    # ------------------------------------------------------------------
    # Main update
    # ------------------------------------------------------------------

    def step(self, dt: Optional[float] = None):
        """Advance one explicit mechanics / optics / magnetism step.

        Args:
            dt: time step [s]. Uses ``voxsym.time_step`` if None.
        """
        self._build_arrays()
        if dt is None:
            dt = self.voxsym.get_time_step()
        voxels = self.voxsym.get_voxels()
        n = len(voxels)
        if n == 0:
            return

        # Snapshot voxel state into arrays
        pos = np.array([[v.x, v.y, v.z] for v in voxels], dtype=np.float64)
        disp = np.array([v.displacement for v in voxels], dtype=np.float64)
        vel = np.array([v.velocity for v in voxels], dtype=np.float64)
        stress = np.array([v.stress for v in voxels], dtype=np.float64)
        temp = np.array([v.temperature for v in voxels], dtype=np.float64)
        T0 = 300.0

        # ---- 1. Mechanics: explicit elastic wave with thermal stress ----
        # Build strain from relative displacement along edges.
        # Normal strain ε_n = (Δdisp · edge_dir) / dx
        du = disp[self._edge_dst] - disp[self._edge_src]
        dn = np.sum(du * self._edge_dir, axis=1)
        normal_strain = dn / self._edge_len

        # Engineering shear strains are skipped for simplicity; the model
        # propagates compressive/dilatational waves only.
        vol_strain = np.zeros(n, dtype=np.float64)
        np.add.at(vol_strain, self._edge_src, normal_strain)
        vol_strain /= 3.0  # crude average over the 3 directions

        # Thermal strain
        thermal_strain = self._alpha * (temp - T0)

        # Hooke's law for isotropic material (small-signal)
        trace = 3.0 * vol_strain
        pressure = self._lam * (trace - 3.0 * thermal_strain) + \
                   2.0 * self._mu * (vol_strain - thermal_strain)

        # Stress gradient along edges → force density on src voxel
        dp = pressure[self._edge_dst] - pressure[self._edge_src]
        force = np.zeros((n, 3), dtype=np.float64)
        edge_force = (dp / self._edge_len).reshape(-1, 1) * self._edge_dir
        np.add.at(force, self._edge_src, edge_force)
        # Newton's third law: add opposite force to dst
        np.add.at(force, self._edge_dst, -edge_force)

        # Velocity update (F = m·a) + damping
        damping = 0.1
        accel = np.zeros((n, 3), dtype=np.float64)
        valid_mass = self._rho > 0
        # force is currently in [N] integrated over the face; convert to
        # acceleration by F/(rho * dx^3)
        accel[valid_mass] = (
            force[valid_mass]
            / (self._rho[valid_mass].reshape(-1, 1) * self._dx[valid_mass].reshape(-1, 1) ** 3)
        )

        # Pin bottom boundary (z == min coordinate) by zeroing velocity/accel
        z_coords = pos[:, 2]
        z_min = z_coords.min()
        pinned = np.abs(z_coords - z_min) < 1e-9
        accel[pinned] = 0.0
        vel[pinned] = 0.0
        disp[pinned] = 0.0

        vel = vel + dt * accel - dt * damping * vel
        disp = disp + dt * vel

        # Update normal stress in Voigt notation (diagonal only)
        new_stress = stress.copy()
        new_stress[:, 0] = -pressure
        new_stress[:, 1] = -pressure
        new_stress[:, 2] = -pressure

        # ---- 2. Optics: Beer-Lambert attenuation along rays ----
        intensity = np.zeros(n, dtype=np.float64)
        for origin, direction, I0 in self._optical_sources:
            ray_o = np.array(origin, dtype=np.float64)
            ray_d = np.array(direction, dtype=np.float64)
            norm = np.linalg.norm(ray_d)
            if norm < 1e-12:
                continue
            ray_d /= norm

            # Project each voxel centre onto the ray
            rel = pos - ray_o
            t = np.sum(rel * ray_d, axis=1)
            # Distance from ray line
            closest = ray_o + t.reshape(-1, 1) * ray_d
            perp = pos - closest
            perp_dist = np.linalg.norm(perp, axis=1)
            # Effective path length through cubic voxel
            half_size = self._dx * 0.5
            inside = perp_dist <= half_size * 1.5
            path = np.zeros(n, dtype=np.float64)
            path[inside] = 2.0 * np.sqrt(np.maximum(
                half_size[inside] ** 2 - perp_dist[inside] ** 2, 0.0
            ))

            # Sort voxels by ray parameter t and accumulate attenuation
            order = np.argsort(t)
            atten = 1.0
            for idx in order:
                if not inside[idx] or path[idx] <= 0:
                    continue
                # Intensity entering this voxel
                intensity[idx] += I0 * atten
                # Beer-Lambert: dI/dz = −α·I, with α corrected for refractive index
                alpha_eff = self._absorb[idx] / max(self._n_ref[idx], 1e-3)
                atten *= np.exp(-alpha_eff * path[idx])

        # ---- 3. Induced magnetisation ----
        # M = χ_m · H  in linear media; clip to saturation-like behaviour
        # with a Curie-law thermal roll-off near a nominal Curie point.
        magnetization = np.zeros((n, 3), dtype=np.float64)
        if self._external_H is not None:
            H = self._external_H
        elif self._external_B is not None:
            # B = μ0 μ_r H → H = B / (μ0 μ_r), per voxel
            H_vec = self._external_B.reshape(1, 3) / self._mu0.reshape(-1, 1)
        else:
            H_vec = np.zeros((n, 3), dtype=np.float64)

        if self._external_H is not None:
            h_norm = np.linalg.norm(H)
        else:
            h_norm = np.linalg.norm(self._external_B) if self._external_B is not None else 0.0

        if h_norm > 1e-12:
            for i in range(n):
                chi = self._chi[i]
                if chi > 0:
                    # Thermal demagnetisation factor: linear roll-off above 700 K
                    T_curie = 1000.0
                    temp_factor = max(0.0, 1.0 - temp[i] / T_curie)
                    H_i = H if self._external_H is not None else H_vec[i]
                    magnetization[i] = chi * temp_factor * H_i

        # ---- 4. Write back ----
        for i, v in enumerate(voxels):
            v.displacement = disp[i]
            v.velocity = vel[i]
            v.stress = new_stress[i]
            v.optical_intensity = float(intensity[i])
            v.magnetization = magnetization[i].astype(np.float32)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def max_stress_magnitude(self) -> float:
        stresses = np.array([v.stress for v in self.voxsym.get_voxels()], dtype=np.float64)
        if stresses.size == 0:
            return 0.0
        return float(np.max(np.abs(stresses)))

    def total_optical_power_absorbed(self) -> float:
        voxels = self.voxsym.get_voxels()
        if not voxels:
            return 0.0
        power = 0.0
        for v in voxels:
            if v.material is None or v.material.absorption_coeff <= 0:
                continue
            vol = v.size ** 3
            power += v.optical_intensity * v.material.absorption_coeff * vol
        return power

    def magnetization_stats(self) -> Tuple[float, float, float]:
        mags = [np.linalg.norm(v.magnetization) for v in self.voxsym.get_voxels()]
        if not mags:
            return 0.0, 0.0, 0.0
        return min(mags), max(mags), sum(mags) / len(mags)
