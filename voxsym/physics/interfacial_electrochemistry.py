"""Interfacial electrochemistry: Butler–Volmer + Stern double layer.

Both quantities are evaluated on the *edge* (heterogeneous interface) between
voxels.  The source term is then accumulated onto the bulk voxels on either
side of the edge.
"""

import numpy as np
from typing import Optional, Tuple
from voxsym.constants import (
    ELEMENTARY_CHARGE,
    BOLTZMANN_CONSTANT,
    AVOGADRO_NUMBER,
)


FARADAY = 96485.33212  # C/mol


def _edge_overpotential(
    phi_src: np.ndarray,
    phi_dst: np.ndarray,
    conc_src: np.ndarray,
    conc_dst: np.ndarray,
    z: int,
    T: float,
) -> np.ndarray:
    """Return the Nernst overpotential η at each interface edge (V).

    η = φ_src − φ_dst − (k_B T / z e) ln(c_dst / c_src)

    This assumes the reference potential is the same on both sides; the
    true equilibrium shift must be supplied by the caller through the
    exchange-current density.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(conc_src > 0, conc_dst / conc_src, 1.0)
    ratio = np.clip(ratio, 1e-12, 1e12)
    if z == 0:
        return phi_src - phi_dst
    nernst = (BOLTZMANN_CONSTANT * T / (z * ELEMENTARY_CHARGE)) * np.log(ratio)
    return phi_src - phi_dst - nernst


def butler_volmer_current(
    phi_src: np.ndarray,
    phi_dst: np.ndarray,
    conc_src: np.ndarray,
    conc_dst: np.ndarray,
    i0: np.ndarray,
    alpha: np.ndarray,
    z: int,
    T: float,
) -> np.ndarray:
    """Return interfacial faradaic current density [A/m²] for each edge.

    j = i₀ [ exp((1−α) z e η / kT) − exp(−α z e η / kT) ]

    Positive j means oxidation (charge leaving src, entering dst).  ``i0`` and
    ``alpha`` must be edge-length arrays defined on the same edge list as the
    potential / concentration arrays.
    """
    eta = _edge_overpotential(phi_src, phi_dst, conc_src, conc_dst, z, T)
    kT = BOLTZMANN_CONSTANT * T
    # dimensionless argument
    arg = z * ELEMENTARY_CHARGE * eta / kT
    # Clamp the dimensionless argument to avoid float overflow / inf.
    arg = np.clip(arg, -50.0, 50.0)
    j = i0 * (np.exp((1.0 - alpha) * arg) - np.exp(-alpha * arg))
    return j


def stern_double_layer_charge(
    phi_src: np.ndarray,
    phi_dst: np.ndarray,
    C_s: np.ndarray,
) -> np.ndarray:
    """Return double-layer charge density [C/m²] on each edge.

    σ_DL = C_S (φ_src − φ_dst)

    The sign convention follows η above: positive σ_DL on the src side when
    φ_src > φ_dst.  This is a linear Stern-layer model; non-linear corrections
    would need the surface charge / Gouy–Chapman term.
    """
    return C_s * (phi_src - phi_dst)


class InterfacialElectrochemistry:
    """Compute BV faradaic currents and Stern DL screening for a VoxSym grid.

    Usage::

        ie = InterfacialElectrochemistry(voxsym)
        dC_faradaic, dQ_dl = ie.compute_sources(dt)

    ``dC_faradaic`` is a per-voxel concentration change [mol/m³] for the
    participating ion species.  ``dQ_dl`` is a per-voxel charge change [C]
    stored on the voxel surface.  The caller is responsible for updating
    ``voxel.charge`` and optionally ``voxel.ion_concentration``.
    """

    def __init__(self, voxsym):
        self.voxsym = voxsym
        self._topology = None
        self._edge_src = None
        self._edge_dst = None
        self._edge_sign = None
        self._edge_axis = None
        self._built = False

    def _ensure_built(self):
        if self._built:
            return
        from voxsym.physics.topology import GridTopology

        voxels = self.voxsym.get_voxels()
        n = len(voxels)
        if n == 0:
            self._topology = GridTopology([])
        else:
            self._topology = GridTopology(voxels, connectivity=6)
        src = self._topology.edges_src
        dst = self._topology.edges_dst
        self._edge_src = src
        self._edge_dst = dst
        self._edge_axis = self._topology.edges_axis
        self._edge_sign = self._topology.edges_sign

        # Precompute heterogeneous interface mask + per-edge material
        # properties once.  Only those edges need Butler–Volmer / DL work.
        if n > 0 and src is not None and len(src) > 0:
            mat_src = np.array(
                [
                    voxels[i].material.name if voxels[i].material is not None else "none"
                    for i in src
                ],
                dtype=object,
            )
            mat_dst = np.array(
                [
                    voxels[i].material.name if voxels[i].material is not None else "none"
                    for i in dst
                ],
                dtype=object,
            )
            self._heterogeneous = mat_src != mat_dst
            self._edge_i0 = np.array([
                float(getattr(voxels[i].material, "exchange_current_density", 0.0))
                if voxels[i].material is not None else 0.0
                for i in src
            ], dtype=np.float64)
            self._edge_alpha = np.array([
                float(getattr(voxels[i].material, "charge_transfer_coefficient", 0.5))
                if voxels[i].material is not None else 0.5
                for i in src
            ], dtype=np.float64)
            self._edge_Cs = np.array([
                float(getattr(voxels[i].material, "stern_capacitance", 0.0))
                if voxels[i].material is not None else 0.0
                for i in src
            ], dtype=np.float64)
            self._edge_dx = np.array([voxels[i].size for i in src], dtype=np.float64)
        else:
            self._heterogeneous = np.array([], dtype=bool)
            self._edge_i0 = np.array([], dtype=np.float64)
            self._edge_alpha = np.array([], dtype=np.float64)
            self._edge_Cs = np.array([], dtype=np.float64)
            self._edge_dx = np.array([], dtype=np.float64)

        self._built = True

    def compute_sources(
        self,
        dt: float,
        species: str = "cation",
        apply_faradaic: bool = True,
        apply_double_layer: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return bulk concentration change (mol/m³) and charge change (C).

        Args:
            dt: time step [s].
            species: ``"cation"`` or ``"anion"`` — which species participates
                in the BV faradaic reaction.
            apply_faradaic: include Butler–Volmer current.
            apply_double_layer: include Stern DL charging.
        """
        self._ensure_built()
        voxels = self.voxsym.get_voxels()
        n = len(voxels)
        dC = np.zeros(n, dtype=np.float64)
        dQ = np.zeros(n, dtype=np.float64)
        if n == 0:
            return dC, dQ

        src = self._edge_src
        dst = self._edge_dst
        n = len(voxels)
        dC = np.zeros(n, dtype=np.float64)
        dQ = np.zeros(n, dtype=np.float64)
        if n == 0:
            return dC, dQ

        if src is None or len(src) == 0:
            return dC, dQ

        # Only consider precomputed heterogeneous interface edges.
        het = self._heterogeneous
        if not het.any():
            return dC, dQ
        src_h = src[het]
        dst_h = dst[het]
        i0_h = self._edge_i0[het]
        alpha_h = self._edge_alpha[het]
        Cs_h = self._edge_Cs[het]
        dx_h = self._edge_dx[het]
        face_area = dx_h * dx_h

        T = float(getattr(self.voxsym, "temperature", 300.0))

        phi = np.array([
            float(getattr(v, "phi", 0.0) or getattr(v, "potential", 0.0))
            for v in voxels
        ], dtype=np.float64)
        phi_src = phi[src_h]
        phi_dst = phi[dst_h]

        if apply_faradaic:
            if species == "cation":
                conc = np.array([v.ion_concentration for v in voxels], dtype=np.float64)
                z_arr = np.array([
                    int(getattr(voxels[i].material, "ionic_valence", 0)) if voxels[i].material is not None else 0
                    for i in src_h
                ], dtype=np.int32)
            else:
                conc = np.array([v.anion_concentration for v in voxels], dtype=np.float64)
                z_arr = np.array([
                    int(getattr(voxels[i].material, "anion_valence", 0)) if voxels[i].material is not None else 0
                    for i in src_h
                ], dtype=np.int32)
            conc_src = conc[src_h]
            conc_dst = conc[dst_h]

            z_repr = int(np.max(np.abs(z_arr))) if np.any(z_arr != 0) else 1
            j = butler_volmer_current(
                phi_src, phi_dst, conc_src, conc_dst,
                i0_h, alpha_h, z_repr, T,
            )
            j = np.clip(j, -1e9, 1e9)

            # Only transfer ions into a material that can host them.
            mat_dst = [voxels[i].material for i in dst_h]
            can_host_dst = np.array([
                (getattr(m, "ion_conc_max", 0.0) > 0 or getattr(m, "ion_diffusivity", 0.0) > 0)
                if m is not None else False
                for m in mat_dst
            ], dtype=bool)
            active = (i0_h > 0) & can_host_dst & (z_arr != 0)

            flux = np.zeros_like(j)
            z_active = z_arr[active].astype(np.float64)
            flux[active] = j[active] / (z_active * FARADAY)
            vol = dx_h ** 3
            dC_src = -(flux[active] * face_area[active] / vol[active])
            dC_dst = +(flux[active] * face_area[active] / vol[active])
            np.add.at(dC, src_h[active], dC_src)
            np.add.at(dC, dst_h[active], dC_dst)

            dQ_src = -j[active] * face_area[active] * dt
            dQ_dst = +j[active] * face_area[active] * dt
            np.add.at(dQ, src_h[active], dQ_src)
            np.add.at(dQ, dst_h[active], dQ_dst)

        if apply_double_layer:
            active_dl = Cs_h > 0
            sigma_dl = stern_double_layer_charge(phi_src, phi_dst, Cs_h)
            dQ_dl = sigma_dl[active_dl] * face_area[active_dl] * dt
            np.add.at(dQ, src_h[active_dl], +dQ_dl)
            np.add.at(dQ, dst_h[active_dl], -dQ_dl)

        return dC, dQ
