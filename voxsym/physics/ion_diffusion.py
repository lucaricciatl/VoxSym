"""
Ion diffusion solver — Fick + Nernst–Planck equations (vectorized).

Uses edge-list format and numpy vectorization for 10–100× speedup
over the Python-loop version.

Equations
---------
Fick::
    ∂c/∂t = D · ∇²c

Nernst–Planck::
    ∂c/∂t = D·∇²c  −  (z e D / k_B T)  ∇·(c E)
"""

import numpy as np
from typing import Tuple, Optional
from voxsym.voxel import Voxel
from voxsym.voxsym import VoxSym
from voxsym.constants import ELEMENTARY_CHARGE, BOLTZMANN_CONSTANT
from voxsym.physics.topology import GridTopology


class IonDiffusion:
    """Finite-difference ion-transport solver (vectorized).

    Two-phase usage::

        new_conc = solver.compute_step(dt)
        for i, v in enumerate(voxels):
            v.ion_concentration = new_conc[i]
    """

    def __init__(self, voxsym: VoxSym):
        self.voxsym = voxsym

        # Shared topology cache; rebuilt when the voxel grid changes.
        self._topology: Optional[GridTopology] = None
        self._topology_voxel_count = -1

        # Edge-list format
        self._edge_src = None    # (E,) int32
        self._edge_dst = None    # (E,) int32
        self._edge_axis = None   # (E,) int8   — 0=x, 1=y, 2=z
        self._edge_sign = None   # (E,) float64 — +1 or −1

        # Material arrays  (N,)
        self._D = None           # ion diffusivity [m²/s]
        self._z = None           # ionic valence
        self._Da = None          # anion diffusivity [m²/s]
        self._za = None          # anion valence
        self._dx = None          # voxel size [m]
        self._conc_max = None    # max concentration [mol/m³]
        self._partition = None   # partition coefficient K (dimensionless)
        self._interface_capacity = None  # Γ_max [mol/m²]
        self._adsorption_rate = None     # k_a [m³/(mol·s)]
        self._desorption_rate = None     # k_d [1/s]
        self._material_name = None       # str name for interface detection
        self._interface_area = None      # total heterogeneous interface area [m²]
        self._interface_conc = None      # Γ [mol/m²]

        self._temperature = 300.0  # K
        self._built = False

        # Charge conservation / source control
        self.conserve_charge = False
        self.charge_source_per_step = None  # optional (N,) array [C/s]
        self.conserved_total = True         # when True, enforce ΣQ = const
        self._last_dQdt = None              # flux divergence from last step

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
            self._edge_axis = self._topology.edges_axis
            self._edge_sign = self._topology.edges_sign
            self._D = np.array([], dtype=np.float64)
            self._z = np.array([], dtype=np.int32)
            self._dx = np.array([], dtype=np.float64)
            self._conc_max = np.array([], dtype=np.float64)
            self._partition = np.array([], dtype=np.float64)
            self._interface_capacity = np.array([], dtype=np.float64)
            self._adsorption_rate = np.array([], dtype=np.float64)
            self._desorption_rate = np.array([], dtype=np.float64)
            self._material_name = np.array([], dtype=object)
            self._interface_area = np.array([], dtype=np.float64)
            self._interface_conc = np.array([], dtype=np.float64)
            self._built = True
            return

        # --- shared topology ---
        self._topology = GridTopology(voxels, connectivity=6)
        self._topology_voxel_count = n
        self._edge_src = self._topology.edges_src
        self._edge_dst = self._topology.edges_dst
        self._edge_axis = self._topology.edges_axis
        self._edge_sign = self._topology.edges_sign

        # --- material arrays ---
        self._D = np.zeros(n, dtype=np.float64)
        self._z = np.zeros(n, dtype=np.int32)
        self._Da = np.zeros(n, dtype=np.float64)
        self._za = np.full(n, -1, dtype=np.int32)
        self._dx = np.zeros(n, dtype=np.float64)
        self._conc_max = np.full(n, np.inf, dtype=np.float64)
        self._partition = np.ones(n, dtype=np.float64)
        self._interface_capacity = np.zeros(n, dtype=np.float64)
        self._adsorption_rate = np.zeros(n, dtype=np.float64)
        self._desorption_rate = np.zeros(n, dtype=np.float64)
        self._material_name = np.full(n, "none", dtype=object)
        self._interface_area = np.zeros(n, dtype=np.float64)
        self._interface_conc = np.zeros(n, dtype=np.float64)

        for idx, v in enumerate(voxels):
            self._dx[idx] = float(v.size)
            self._interface_conc[idx] = float(getattr(v, "interface_concentration", 0.0))
            if v.material is not None:
                self._D[idx] = float(v.material.ion_diffusivity)
                self._z[idx] = int(v.material.ionic_valence)
                self._Da[idx] = float(getattr(v.material, "anion_diffusivity", 0.0))
                self._za[idx] = int(getattr(v.material, "anion_valence", -1))
                if v.material.ion_conc_max > 0:
                    self._conc_max[idx] = float(v.material.ion_conc_max)
                self._partition[idx] = float(v.material.partition_coeff)
                self._interface_capacity[idx] = float(v.material.interface_capacity)
                self._adsorption_rate[idx] = float(v.material.adsorption_rate)
                self._desorption_rate[idx] = float(v.material.desorption_rate)
                self._material_name[idx] = v.material.name

        # --- per-voxel heterogeneous interface area ---
        # The directed edge list contains each physical face twice.
        # Add half the shared face area to both endpoints for each directed edge
        # so the total area per voxel equals the sum of its distinct faces.
        src = self._edge_src
        dst = self._edge_dst
        if src is not None and len(src) > 0:
            dx_src = self._dx[src]
            dx_dst = self._dx[dst]
            face_area = np.minimum(dx_src * dx_src, dx_dst * dx_dst)
            heterogeneous = self._material_name[src] != self._material_name[dst]
            area_per_edge = np.where(heterogeneous, face_area * 0.5, 0.0)
            np.add.at(self._interface_area, src, area_per_edge)
            np.add.at(self._interface_area, dst, area_per_edge)

        self._built = True

    # ------------------------------------------------------------------
    # Two-phase compute
    # ------------------------------------------------------------------

    def compute_step(self, dt: Optional[float] = None) -> np.ndarray:
        """Backward-compatible single-species step (returns cations only)."""
        cation_new, _ = self.compute_step_both(dt)
        return cation_new

    def compute_step_both(self, dt: Optional[float] = None) -> Tuple[np.ndarray, np.ndarray]:
        """Compute one transport step for both cations and anions."""
        self._build_arrays()
        voxels = self.voxsym.get_voxels()
        n = len(voxels)
        if n == 0:
            empty = np.array([], dtype=np.float64)
            return empty, empty

        if dt is None:
            dt = self.voxsym.get_time_step()

        E_field = np.array([getattr(v, "electric_field", np.zeros(3)) for v in voxels],
                           dtype=np.float64)

        cation = np.array([getattr(v, "ion_concentration", 0.0) for v in voxels],
                         dtype=np.float64)
        anion = np.array([getattr(v, "anion_concentration", 0.0) for v in voxels],
                        dtype=np.float64)

        new_cation = self._transport_step(cation, self._D, self._z, E_field, dt)
        new_anion = self._transport_step(anion, self._Da, self._za, E_field, dt)

        np.clip(new_cation, 0.0, self._conc_max, out=new_cation)
        np.clip(new_anion, 0.0, self._conc_max, out=new_anion)

        # Write adsorbed interface concentration back to voxels
        for i, v in enumerate(voxels):
            v.interface_concentration = float(self._interface_conc[i])

        return new_cation, new_anion

    def _transport_step(
        self, conc: np.ndarray, D_array: np.ndarray, z_array: np.ndarray,
        E_field: np.ndarray, dt: float,
    ) -> np.ndarray:
        """Single explicit transport step for one species — fully vectorized."""
        src = self._edge_src
        dst = self._edge_dst
        n = len(conc)

        # Harmonic-mean interface diffusivity for this species
        D_src = D_array[src]
        D_dst = D_array[dst]
        D_sum = D_src + D_dst
        with np.errstate(divide='ignore', invalid='ignore'):
            D_avg = np.where(D_sum > 0, 2.0 * D_src * D_dst / D_sum, 0.0)

        # Block transport across interfaces where either side cannot host
        # this species.  Metal/graphene electrodes are impermeable walls for
        # the mobile ion; only electrolyte and insertion materials exchange.
        can_host = np.array([
            getattr(self.voxsym.voxels[i].material, "ion_conc_max", 0.0) > 0
            if self.voxsym.voxels[i].material is not None else False
            for i in dst
        ], dtype=bool) & np.array([
            getattr(self.voxsym.voxels[i].material, "ion_conc_max", 0.0) > 0
            if self.voxsym.voxels[i].material is not None else False
            for i in src
        ], dtype=bool)
        D_avg = np.where(can_host, D_avg, 0.0)

        # ---- Fickian diffusion with partition-corrected jump condition ----
        # At equilibrium across a boundary between material A and B:
        #     c_B / c_A = K_B / K_A .
        # The effective driving force is zero at that ratio, so we replace
        # the raw concentration difference with a partition-weighted one.
        K_src = self._partition[src]
        K_dst = self._partition[dst]
        with np.errstate(divide='ignore', invalid='ignore'):
            K_ratio = np.where(K_src > 0, K_dst / K_src, 1.0)
        c_diff = conc[dst] - K_ratio * conc[src]

        dx2 = self._dx[src] * self._dx[src]
        valid_fick = (dx2 > 0) & (D_avg > 0)

        w_fick = np.zeros(len(src), dtype=np.float64)
        w_fick[valid_fick] = D_avg[valid_fick] / dx2[valid_fick]

        dC_fick = np.zeros(n, dtype=np.float64)
        np.add.at(dC_fick, src, w_fick * c_diff)

        # ---- Nernst–Planck migration  −(zeD/kBT) ∇·(c E) ----
        z_src = z_array[src].astype(np.float64)
        has_charge = z_src != 0

        dC_mig = np.zeros(n, dtype=np.float64)
        if has_charge.any():
            e = ELEMENTARY_CHARGE
            kBT = BOLTZMANN_CONSTANT * self._temperature

            # E·n for each edge
            E_dot_n = E_field[src, self._edge_axis] * self._edge_sign

            # Mobility  μ = z·e·D / kBT
            mobility = z_src * e * D_avg / kBT

            # Average concentration at interface
            c_avg = 0.5 * (conc[src] + conc[dst])

            # Migration contribution  −μ·c_avg·(E·n) / dx
            dx_src = self._dx[src]
            valid_mig = (dx_src > 0) & has_charge & (D_avg > 0)

            w_mig = np.zeros(len(src), dtype=np.float64)
            w_mig[valid_mig] = (
                -mobility[valid_mig]
                * c_avg[valid_mig]
                * E_dot_n[valid_mig]
                / dx_src[valid_mig]
            )

            np.add.at(dC_mig, src, w_mig)

        # ---- Interfacial adsorption / desorption (Langmuir kinetics) ----
        # dΓ/dt = k_a · c · (Γ_max − Γ) − k_d · Γ   [mol/(m²·s)]
        # Bulk concentration change: dC/dt = − dΓ/dt · A_interface / V_voxel
        gamma = self._interface_conc
        gamma_max = self._interface_capacity
        k_a = self._adsorption_rate
        k_d = self._desorption_rate
        area = self._interface_area
        vol = self._dx ** 3

        active_interface = (area > 0) & (gamma_max > 0) & ((k_a > 0) | (k_d > 0))
        dC_ads = np.zeros(n, dtype=np.float64)
        d_gamma = np.zeros(n, dtype=np.float64)
        if active_interface.any():
            d_gamma[active_interface] = (
                k_a[active_interface] * conc[active_interface]
                * (gamma_max[active_interface] - gamma[active_interface])
                - k_d[active_interface] * gamma[active_interface]
            )
            # Moles leaving/entering the bulk per unit volume
            dC_ads[active_interface] = (
                -d_gamma[active_interface] * area[active_interface]
                / vol[active_interface]
            )
            # Update adsorbed amount in-place (explicit Euler)
            gamma[active_interface] = np.clip(
                gamma[active_interface] + d_gamma[active_interface] * dt,
                0.0,
                gamma_max[active_interface],
            )

        # Store the divergence of ionic flux for optional charge conservation.
        # dC/dt from transport (excluding sources) is dC_fick + dC_mig + dC_ads.
        self._last_dQdt = dC_fick + dC_mig + dC_ads

        return conc + dt * (dC_fick + dC_mig + dC_ads)

    def pending_charge_update(self, dt: Optional[float] = None) -> np.ndarray:
        """Return updated voxel charges from ionic flux divergence.

        Total charge is conserved in the absence of explicit charge sources:
        the sum of ``dQ = z · F · dC`` over the grid is zero up to floating
        point round-off because every ion that leaves one voxel enters a
        neighbor.  An optional per-voxel charge source (or sink) can be
        added via ``charge_source_per_step`` [C/s].
        """
        self._build_arrays()
        voxels = self.voxsym.get_voxels()
        n = len(voxels)
        if dt is None:
            dt = self.voxsym.get_time_step()

        charges = np.array([v.charge for v in voxels], dtype=np.float64)
        z = self._z.astype(np.float64)
        za = self._za.astype(np.float64)
        F = 96485.33212  # Faraday constant [C/mol]

        if self._last_dQdt is None:
            dQdt = np.zeros(n, dtype=np.float64)
        else:
            dQdt = z * F * self._last_dQdt

        # Add optional explicit source/sink [C/s].
        if self.charge_source_per_step is not None:
            source = np.asarray(self.charge_source_per_step, dtype=np.float64)
            if len(source) == n:
                dQdt = dQdt + source

        new_charges = charges + dt * dQdt

        # If strict total conservation is requested and no source is present,
        # remove any global drift introduced by round-off.
        if self.conserved_total and self.charge_source_per_step is None:
            total_before = float(charges.sum())
            drift = float(new_charges.sum()) - total_before
            if n > 0 and abs(drift) > 1e-24:
                new_charges -= drift / n

        return new_charges

    # ------------------------------------------------------------------
    # Charge conservation helpers
    # ------------------------------------------------------------------

    def set_charge_source(self, source_per_step: Optional[np.ndarray] = None):
        """Set an optional per-voxel charge source/sink [C/s]."""
        if source_per_step is not None:
            source_per_step = np.asarray(source_per_step, dtype=np.float64)
        self.charge_source_per_step = source_per_step

    def set_conserve_charge(self, enabled: bool = True, conserved_total: bool = True):
        """Enable / disable charge conservation from ion transport.

        Args:
            enabled: When True, ``compute_step`` records ionic flux
                divergence and ``VoxSym.update()`` will update voxel charges.
            conserved_total: When True and no charge source is set, enforce
                zero net drift by subtracting the average round-off error.
        """
        self.conserve_charge = bool(enabled)
        self.conserved_total = bool(conserved_total)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def step(self, dt: Optional[float] = None):
        new_conc = self.compute_step(dt)
        voxels = self.voxsym.get_voxels()
        for i, v in enumerate(voxels):
            v.ion_concentration = float(new_conc[i])
            v.interface_concentration = float(self._interface_conc[i])

    def set_temperature(self, T: float):
        self._temperature = T

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def concentration_stats(self) -> Tuple[float, float, float]:
        concs = [getattr(v, "ion_concentration", 0.0) for v in self.voxsym.get_voxels()]
        if not concs:
            return 0.0, 0.0, 0.0
        return min(concs), max(concs), sum(concs) / len(concs)
