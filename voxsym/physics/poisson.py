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
    """Compute E = −∇φ  via central differences along existing edges [V/m]."""
    n = len(phi)
    grad = np.zeros((n, 3), dtype=np.float64)
    counts = np.zeros(n, dtype=np.int32)

    dphi = phi[edge_dst] - phi[edge_src]
    axes = np.zeros((len(edge_src), 3), dtype=np.float64)
    edge_len = np.zeros(len(edge_src), dtype=np.float64)
    for e in range(len(edge_src)):
        s = edge_src[e]
        d = edge_dst[e]
        dx_ = voxels[d].x - voxels[s].x
        dy_ = voxels[d].y - voxels[s].y
        dz_ = voxels[d].z - voxels[s].z
        norm = np.sqrt(dx_ * dx_ + dy_ * dy_ + dz_ * dz_) + 1e-30
        axes[e] = (dx_ / norm, dy_ / norm, dz_ / norm)
        edge_len[e] = norm

    safe_len = np.where(edge_len > 0, edge_len, 1.0)
    dphi_over_len = dphi / safe_len
    # Vectorized accumulation of the 3-vector gradient contribution.
    for axis_idx in range(3):
        component = dphi_over_len * axes[:, axis_idx]
        np.add.at(grad[:, axis_idx], edge_src, component)
    np.add.at(counts, edge_src, 1)

    valid = counts > 0
    denom = np.where(valid, counts, 1).reshape(-1, 1)
    grad = np.where(valid.reshape(-1, 1), grad / denom, grad)

    # E = −∇φ
    return -grad


def solve_potential_from_charge(
    voxsym: VoxSym,
    max_iter: int = 500,
    tol: float = 1e-6,
    epsilon: Optional[np.ndarray] = None,
    return_phi: bool = False,
    dirichlet: Optional[dict[int, float]] = None,
) -> Optional[np.ndarray]:
    """Solve Poisson's equation from voxel charges and store E = −∇φ.

    This is the standalone entry point used by ``VoxSym.solve_poisson()``.

    Args:
        voxsym: VoxSym instance containing the voxel grid.
        max_iter: Maximum Jacobi iterations.
        tol: Convergence tolerance on max |Δφ|.
        epsilon: Per-voxel permittivity array [F/m].  If None, vacuum
            permittivity is used everywhere.
        return_phi: If True, also return the solved potential array.
        dirichlet: Optional {voxel_index: fixed_potential_V} mapping for
            Dirichlet boundaries.

    Returns:
        The electric field array (N, 3) if ``return_phi`` is False,
        otherwise a tuple (E, phi).

    Boundary conditions:
        Dirichlet where ``dirichlet`` provides a value; otherwise Neumann
        (zero normal derivative of φ) on the outer surface of the voxel
        cloud.  Neumann is implicit because only face-connected neighbors are
        summed; a missing neighbor contributes as if φ_outside = φ_inside,
        giving  ∂φ/∂n = 0  and therefore E_n = 0.
    """
    voxels = voxsym.get_voxels()
    n = len(voxels)
    if n == 0:
        return None

    coord_to_idx, edge_src, edge_dst, neighbors, dx = _build_topology(voxels)

    # Net charge density from explicit free charges plus cation/anion imbalance.
    charges = np.array([v.charge for v in voxels], dtype=np.float64)
    for i, v in enumerate(voxels):
        zp = float(getattr(v.material, "ionic_valence", 1)) if v.material else 1.0
        zn = float(getattr(v.material, "anion_valence", -1)) if v.material else -1.0
        # Add contribution of mobile cations and anions to charge density [C/m³].
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

    # RHS = −ρ/ε .  charge density ρ = charge / volume.
    vol = dx ** 3
    rho = charges / np.where(vol > 0, vol, 1.0)
    rho_over_eps = rho / np.where(eps > 0, eps, EPSILON_0)
    # For the Jacobi update we use dx² · ρ/ε .  Use the local dx² as a
    # scale; the solver is effectively normalising by neighbor count.
    rhs = rho_over_eps * (dx ** 2)

    phi = np.zeros(n, dtype=np.float64)
    fixed = set(dirichlet.keys()) if dirichlet else set()
    for idx, val in (dirichlet or {}).items():
        phi[idx] = val
    phi = _solve_potential_jacobi(phi, rhs, neighbors, edge_src, edge_dst, max_iter, tol, fixed=fixed)

    E = _compute_electric_field(phi, voxels, edge_src, edge_dst, dx)

    # Store results on voxels
    for i, v in enumerate(voxels):
        v.electric_field = np.asarray(E[i], dtype=np.float32)
        # Also attach the scalar potential for inspection / physics coupling.
        v.phi = float(phi[i])

    if return_phi:
        return E, phi
    return E
