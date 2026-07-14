"""Poisson / electrostatic solver on a regular voxel grid.

Solves  ∇²φ = −ρ/ε  (Gauss's law) with a simple iterative Jacobi method.
The electric field is recovered as  E = −∇φ  and stored back on voxels.
"""

import numpy as np
from typing import Optional

from voxsym.voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.constants import ELEMENTARY_CHARGE


# Physical constants
EPSILON_0 = 8.854187817e-12  # F/m


def _build_topology(voxels):
    """Return coordinate map, edge lists and neighbor counts for the grid.

    This is a local helper so ``poisson.py`` does not depend on an optional
    shared ``GridTopology`` already being present.
    """
    coord_to_idx = {}
    for idx, v in enumerate(voxels):
        key = (
            int(round(v.x / v.size)),
            int(round(v.y / v.size)),
            int(round(v.z / v.size)),
        )
        coord_to_idx[key] = idx

    dirs = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    src_list = []
    dst_list = []
    for idx, v in enumerate(voxels):
        base = (
            int(round(v.x / v.size)),
            int(round(v.y / v.size)),
            int(round(v.z / v.size)),
        )
        for dx_, dy_, dz_ in dirs:
            nkey = (base[0] + dx_, base[1] + dy_, base[2] + dz_)
            if nkey in coord_to_idx:
                src_list.append(idx)
                dst_list.append(coord_to_idx[nkey])

    edge_src = np.array(src_list, dtype=np.int32)
    edge_dst = np.array(dst_list, dtype=np.int32)

    n = len(voxels)
    neighbors = np.zeros(n, dtype=np.int32)
    np.add.at(neighbors, edge_src, 1)

    # Voxel sizes for gradient computation
    dx = np.array([v.size for v in voxels], dtype=np.float64)

    return coord_to_idx, edge_src, edge_dst, neighbors, dx


def _solve_potential_jacobi(
    phi: np.ndarray,
    rho_over_eps: np.ndarray,
    neighbors: np.ndarray,
    edge_src: np.ndarray,
    edge_dst: np.ndarray,
    max_iter: int,
    tol: float,
    fixed: Optional[set[int]] = None,
) -> np.ndarray:
    """Jacobi iteration for  ∇²φ = −ρ/ε  on a uniform-ish voxel grid.

    Interior update:  φ_i^{new} = ( Σ φ_j + dx² · ρ_i/ε ) / n_i
    Boundary condition: Neumann (zero normal derivative) is implicit because
    only existing neighbors participate in the sum; missing neighbors are
    effectively mirrored (φ_outside = φ_inside).  This is equivalent to a
    zero-flux / zero-normal-E-field boundary for the outer surface of the
    voxel cloud.

    Dirichlet nodes listed in ``fixed`` keep their initial value throughout
    the iteration.
    """
    n = len(phi)
    fixed = fixed or set()
    fixed_mask = np.zeros(n, dtype=bool)
    if fixed:
        fixed_mask[list(fixed)] = True

    for _ in range(max_iter):
        neighbor_sum = np.zeros(n, dtype=np.float64)
        np.add.at(neighbor_sum, edge_src, phi[edge_dst])
        # Laplacian discretisation: (Σ φ_neighbor − n·φ) / dx² = −ρ/ε
        # Rearranged Jacobi update at each voxel:
        new_phi = (neighbor_sum + rho_over_eps) / np.maximum(neighbors, 1)

        # Preserve fixed-potential Dirichlet nodes and isolated voxels.
        new_phi = np.where(fixed_mask | (neighbors == 0), phi, new_phi)
        delta = np.abs(new_phi - phi)
        max_delta = float(delta[~fixed_mask].max()) if (~fixed_mask).any() else 0.0
        phi = new_phi
        if max_delta < tol:
            break
    return phi


def _compute_electric_field(
    phi: np.ndarray,
    voxels: list[Voxel],
    edge_src: np.ndarray,
    edge_dst: np.ndarray,
    dx: np.ndarray,
) -> np.ndarray:
    """Compute E = −∇φ via central differences along existing edges [V/m]."""
    n = len(phi)
    grad = np.zeros((n, 3), dtype=np.float64)
    counts = np.zeros(n, dtype=np.int32)

    if len(edge_src) > 0:
        # Vectorized edge vectors and 1D dphi.
        vs = np.array([[v.x, v.y, v.z] for v in voxels], dtype=np.float64)
        edge_vec = vs[edge_dst] - vs[edge_src]
        edge_len = np.linalg.norm(edge_vec, axis=1)
        safe_len = np.where(edge_len > 0, edge_len, 1.0)
        dphi = phi[edge_dst] - phi[edge_src]
        dphi_over_len = dphi / safe_len
        # Unit direction vectors.
        axes = edge_vec / safe_len[:, None]
        # Accumulate each component separately.
        for axis_idx in range(3):
            component = dphi_over_len * axes[:, axis_idx]
            np.add.at(grad[:, axis_idx], edge_src, component)
        np.add.at(counts, edge_src, 1)

    valid = counts > 0
    denom = np.where(valid, counts, 1).reshape(-1, 1)
    grad = np.where(valid.reshape(-1, 1), grad / denom, grad)

    return -grad


def solve_potential_from_charge(
    voxsym,
    max_iter: int = 500,
    tol: float = 1e-6,
    epsilon: Optional[np.ndarray] = None,
    return_phi: bool = False,
    dirichlet: Optional[dict[int, float]] = None,
) -> Optional[np.ndarray]:
    """Solve Poisson's equation from voxel charges and store E = −∇φ.

    Uses the shared GridTopology on *voxsym* so the coordinate map is not
    rebuilt every call.
    """
    voxels = voxsym.get_voxels()
    n = len(voxels)
    if n == 0:
        return None

    topology = voxsym.get_topology()
    edge_src = topology.edges_src
    edge_dst = topology.edges_dst
    # Neighbor counts for the Jacobi update: each directed edge contributes
    # one face, so the count per voxel equals its number of face neighbours.
    neighbors = np.zeros(n, dtype=np.int32)
    if len(edge_src) > 0:
        np.add.at(neighbors, edge_src, 1)
    dx = np.array([v.size for v in voxels], dtype=np.float64)

    # Net charge density from explicit free charges plus cation/anion imbalance.
    charges = np.array([v.charge for v in voxels], dtype=np.float64)
    for i, v in enumerate(voxels):
        zp = float(getattr(v.material, "ionic_valence", 1)) if v.material else 1.0
        zn = float(getattr(v.material, "anion_valence", -1)) if v.material else -1.0
        charges[i] += ELEMENTARY_CHARGE * (zp * v.ion_concentration + zn * v.anion_concentration)

    if epsilon is None:
        eps = np.full(n, EPSILON_0, dtype=np.float64)
        for i, v in enumerate(voxels):
            epsr = float(getattr(v.material, "dielectric_constant", 1.0)) if v.material else 1.0
            eps[i] = EPSILON_0 * max(epsr, 1.0)
    else:
        eps = np.asarray(epsilon, dtype=np.float64)
        if len(eps) != n:
            raise ValueError(f"epsilon length {len(eps)} != voxel count {n}")

    vol = dx ** 3
    rho = charges / np.where(vol > 0, vol, 1.0)
    rho_over_eps = rho / np.where(eps > 0, eps, EPSILON_0)
    rhs = rho_over_eps * (dx ** 2)

    phi = np.zeros(n, dtype=np.float64)
    fixed = set(dirichlet.keys()) if dirichlet else set()
    for idx, val in (dirichlet or {}).items():
        phi[idx] = val

    for i, v in enumerate(voxels):
        if getattr(v, "potential_fixed", False):
            fixed.add(i)
            phi[i] = float(getattr(v, "potential", 0.0))
    phi = _solve_potential_jacobi(phi, rhs, neighbors, edge_src, edge_dst, max_iter, tol, fixed=fixed)

    E = _compute_electric_field(phi, voxels, edge_src, edge_dst, dx)

    for i, v in enumerate(voxels):
        v.electric_field = np.asarray(E[i], dtype=np.float32)
        v.phi = float(phi[i])

    if return_phi:
        return E, phi
    return E


# Legacy alias for code that imported the function directly.
solve_potential_from_charge_voxels = solve_potential_from_charge
