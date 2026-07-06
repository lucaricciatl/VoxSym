"""Explicit time-step stability helpers.

These helpers give conservative upper bounds for the explicit Euler
finite-difference solvers used by VoxSym.  They are based on the
Courant–Friedrichs–Lewy (CFL) condition for diffusion and a combined
diffusion + drift CFL for Nernst–Planck ion transport.

The returned caps are multiplied by ``dt_safety_factor`` in
``VoxSym.step_and_update`` before they are enforced.
"""

from typing import Iterable, Optional, Sequence

import numpy as np

from voxsym.constants import ELEMENTARY_CHARGE, BOLTZMANN_CONSTANT
from voxsym.voxel import Voxel


def max_stable_dt_for_diffusion(D: float, dx: float, dim: int = 3) -> float:
    """CFL cap for an explicit diffusion step in *dim* dimensions.

    For the 6-connected finite-difference Laplacian the stability limit is

        dt <= dx^2 / (2 * dim * D)

    so the returned value is exactly that expression.  If ``D`` or ``dx``
    is non-positive the function returns ``np.inf`` (no diffusion limit).

    Parameters
    ----------
    D
        Diffusion coefficient [m²/s].
    dx
        Voxel size [m].
    dim
        Spatial dimensionality (default 3).

    Returns
    -------
    float
        Maximum stable time step [s].
    """
    D = float(D)
    dx = float(dx)
    dim = int(dim)
    if D <= 0 or dx <= 0 or dim <= 0:
        return float("inf")
    return dx * dx / (2.0 * dim * D)


def max_stable_dt_for_ionic(
    D: float,
    dx: float,
    E: float,
    z: int = 1,
    T: float = 300.0,
    dim: int = 3,
) -> float:
    """Combined diffusion + drift CFL cap for ionic transport.

    The explicit finite-difference solver has two relevant time scales:

    * diffusion:  dt <= dx^2 / (2 * dim * D)
    * drift:     dt <= dx / (|mu| * |E|),  mu = z e D / (k_B T)

    This function returns the smaller of the two caps.  If ``D`` is zero
    or negative, only the drift limit is returned; if both contributions
    are inactive the function returns ``np.inf``.

    Parameters
    ----------
    D
        Ion diffusivity [m²/s].
    dx
        Voxel size [m].
    E
        Magnitude of the electric field [V/m].
    z
        Ionic valence (charge number, absolute value).
    T
        Temperature [K].
    dim
        Spatial dimensionality (default 3).

    Returns
    -------
    float
        Maximum stable time step [s].
    """
    D = float(D)
    dx = float(dx)
    E = float(E)
    z = abs(int(z))
    T = float(T)
    dim = int(dim)

    dt_diff = float("inf")
    if D > 0 and dx > 0 and dim > 0:
        dt_diff = dx * dx / (2.0 * dim * D)

    dt_drift = float("inf")
    if D > 0 and dx > 0 and z > 0 and T > 0 and E > 0:
        mobility = z * ELEMENTARY_CHARGE * D / (BOLTZMANN_CONSTANT * T)
        drift_speed = mobility * E
        if drift_speed > 0:
            dt_drift = dx / drift_speed

    return min(dt_diff, dt_drift)


def _voxel_dx(voxels: Sequence[Voxel]) -> Optional[float]:
    """Return a representative voxel size from a list of voxels."""
    if not voxels:
        return None
    sizes = np.array([v.size for v in voxels], dtype=np.float64)
    return float(np.min(sizes)) if len(sizes) else None


def max_stable_dt_for_voxels(
    voxels: Sequence[Voxel],
    *,
    T: float = 300.0,
    E_default: float = 0.0,
    dim: int = 3,
) -> float:
    """Compute the most restrictive stable dt across a voxel grid.

    For each voxel the smaller of the heat-diffusion and ionic caps is
    evaluated, using the voxel's material properties and the local
    electric-field magnitude.  The global minimum is returned.  If no
    relevant physics is present the function returns ``np.inf``.

    Parameters
    ----------
    voxels
        Sequence of ``Voxel`` objects.
    T
        Temperature used in the Nernst–Planck mobility term [K].
    E_default
        Fallback electric-field magnitude for voxels with no ``electric_field``.
    dim
        Spatial dimensionality (default 3).

    Returns
    -------
    float
        Maximum stable time step [s].
    """
    if not voxels:
        return float("inf")

    dx = _voxel_dx(voxels)
    if dx is None or dx <= 0:
        return float("inf")

    dt_min = float("inf")
    for v in voxels:
        m = v.material
        if m is None:
            continue

        # Heat diffusion limit
        if m.thermal_conductivity > 0 and m.density > 0 and m.specific_heat > 0:
            D_thermal = m.thermal_conductivity / (m.density * m.specific_heat)
            dt_min = min(dt_min, max_stable_dt_for_diffusion(D_thermal, dx, dim))

        # Ionic diffusion + drift limit
        if m.ion_diffusivity > 0:
            E_vec = getattr(v, "electric_field", None)
            E_mag = E_default
            if E_vec is not None:
                E_mag = float(np.linalg.norm(E_vec))
            dt_min = min(
                dt_min,
                max_stable_dt_for_ionic(
                    m.ion_diffusivity, dx, E_mag, z=m.ionic_valence, T=T, dim=dim
                ),
            )

    return dt_min


def _solver_name(obj) -> str:
    """Return a readable solver name for warning messages."""
    return getattr(obj, "__class__", object).__name__


def max_stable_dt_for_heat_solver(heat_solver) -> float:
    """Cap from the thermal diffusivity of the current grid."""
    if heat_solver is None or not getattr(heat_solver, "_built", False):
        return float("inf")

    k = heat_solver._k
    rho_cp = heat_solver._rho_cp
    dx = heat_solver._dx
    if k is None or rho_cp is None or dx is None:
        return float("inf")

    valid = (rho_cp > 0) & (k > 0) & (dx > 0)
    if not valid.any():
        return float("inf")
    D = k[valid] / rho_cp[valid]
    caps = dx[valid] * dx[valid] / (6.0 * D)
    return float(caps.min())


def max_stable_dt_for_ion_solver(ion_solver) -> float:
    """Cap from ionic diffusivity + drift of the current grid."""
    if ion_solver is None or not getattr(ion_solver, "_built", False):
        return float("inf")

    D_arr = ion_solver._D
    dx_arr = ion_solver._dx
    z_arr = ion_solver._z
    T = getattr(ion_solver, "_temperature", 300.0)
    if D_arr is None or dx_arr is None or z_arr is None:
        return float("inf")

    voxels = ion_solver.voxsym.get_voxels()
    n = len(dx_arr)
    dx = dx_arr[:n]
    D = D_arr[:n]
    z = z_arr[:n]
    valid = (D > 0) & (dx > 0)
    if not valid.any():
        return float("inf")

    # Build E-field magnitudes for charged voxels; uncharged use pure diffusion.
    E = np.zeros(n, dtype=np.float64)
    charged = valid & (z != 0)
    if charged.any():
        for i in np.where(charged)[0]:
            if i < len(voxels):
                vec = getattr(voxels[i], "electric_field", None)
                if vec is not None:
                    E[i] = float(np.linalg.norm(vec))

    dt_diff = np.full(n, np.inf, dtype=np.float64)
    dt_diff[valid] = dx[valid] * dx[valid] / (6.0 * D[valid])

    dt_drift = np.full(n, np.inf, dtype=np.float64)
    charged_valid = charged & (E > 0) & (T > 0)
    if charged_valid.any():
        mobility = (
            np.abs(z[charged_valid].astype(np.float64))
            * ELEMENTARY_CHARGE
            * D[charged_valid]
            / (BOLTZMANN_CONSTANT * T)
        )
        drift_speed = mobility * E[charged_valid]
        dt_drift[charged_valid] = dx[charged_valid] / drift_speed

    return float(np.minimum(dt_diff, dt_drift).min())
