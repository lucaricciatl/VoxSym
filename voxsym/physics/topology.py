"""Shared voxel-grid topology cache.

``GridTopology`` builds and caches the coordinate-to-index map, the
edge/neighbor list for 6-connectivity (face neighbours), and lightweight
helper arrays such as the surface mask.  It is used by the diffusion
and mechanics solvers so they do not rebuild ``coord_to_idx`` every
step.
"""

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


# 6-connectivity directions: +x, -x, +y, -y, +z, -z
_FACE_DIRECTIONS = (
    (1, 0, 0),
    (-1, 0, 0),
    (0, 1, 0),
    (0, -1, 0),
    (0, 0, 1),
    (0, 0, -1),
)

# 26-connectivity offsets (including faces, edges, corners)
_26_OFFSETS = [
    (dx, dy, dz)
    for dx in (-1, 0, 1)
    for dy in (-1, 0, 1)
    for dz in (-1, 0, 1)
    if not (dx == 0 and dy == 0 and dz == 0)
]

_AXIS = {
    (1, 0, 0): 0,
    (-1, 0, 0): 0,
    (0, 1, 0): 1,
    (0, -1, 0): 1,
    (0, 0, 1): 2,
    (0, 0, -1): 2,
}

_SIGN = {
    (1, 0, 0): 1,
    (-1, 0, 0): -1,
    (0, 1, 0): 1,
    (0, -1, 0): -1,
    (0, 0, 1): 1,
    (0, 0, -1): -1,
}


class GridTopology:
    """Immutable topology of a voxel grid.

    The topology is built once from a list of voxels and can be reused
    by multiple physics solvers.  Mutations to the voxel list require a
    rebuild; VoxSym handles this automatically.

    Parameters
    ----------
    voxels
        Sequence of ``Voxel`` objects.  Voxels are assumed to be on a
        regular Cartesian grid with uniform size.
    connectivity
        Either ``6`` (face-connected, default) or ``26`` (all
        neighbours).  Most solvers use ``6``.
    """

    def __init__(self, voxels: Sequence, *, connectivity: int = 6):
        self._voxels = list(voxels)
        self.connectivity = int(connectivity)
        if self.connectivity not in (6, 26):
            raise ValueError("connectivity must be 6 or 26")

        self._coord_to_idx: Dict[Tuple[int, int, int], int] = {}
        self._idx_to_coord: List[Tuple[int, int, int]] = []
        self._edge_src: Optional[np.ndarray] = None
        self._edge_dst: Optional[np.ndarray] = None
        self._edge_axis: Optional[np.ndarray] = None
        self._edge_sign: Optional[np.ndarray] = None
        self._neighbors: Optional[List[np.ndarray]] = None
        self._is_surface: Optional[np.ndarray] = None
        self._n: int = 0
        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self):
        voxels = self._voxels
        n = len(voxels)
        self._n = n
        if n == 0:
            self._edge_src = np.array([], dtype=np.int32)
            self._edge_dst = np.array([], dtype=np.int32)
            self._edge_axis = np.array([], dtype=np.int8)
            self._edge_sign = np.array([], dtype=np.float64)
            self._neighbors = []
            self._is_surface = np.array([], dtype=bool)
            return

        # Coordinate map
        coord_to_idx: Dict[Tuple[int, int, int], int] = {}
        idx_to_coord: List[Tuple[int, int, int]] = []
        for idx, v in enumerate(voxels):
            key = self._coord_key(v)
            coord_to_idx[key] = idx
            idx_to_coord.append(key)
        self._coord_to_idx = coord_to_idx
        self._idx_to_coord = idx_to_coord

        # Directed edge list for the requested connectivity
        dirs = _FACE_DIRECTIONS if self.connectivity == 6 else _26_OFFSETS
        src_list: List[int] = []
        dst_list: List[int] = []
        axis_list: List[int] = []
        sign_list: List[int] = []
        neighbors: List[List[int]] = [[] for _ in range(n)]

        for idx, v in enumerate(voxels):
            base = self._coord_key(v)
            for d in dirs:
                nkey = (base[0] + d[0], base[1] + d[1], base[2] + d[2])
                if nkey in coord_to_idx:
                    dst = coord_to_idx[nkey]
                    src_list.append(idx)
                    dst_list.append(dst)
                    if self.connectivity == 6:
                        axis_list.append(_AXIS[d])
                        sign_list.append(_SIGN[d])
                    # Build undirected neighbor list: avoid duplicates for
                    # 26-connectivity by only adding forward edges once.
                    if dst not in neighbors[idx]:
                        neighbors[idx].append(dst)
                    if idx not in neighbors[dst]:
                        neighbors[dst].append(idx)

        self._edge_src = np.array(src_list, dtype=np.int32)
        self._edge_dst = np.array(dst_list, dtype=np.int32)
        if self.connectivity == 6:
            self._edge_axis = np.array(axis_list, dtype=np.int8)
            self._edge_sign = np.array(sign_list, dtype=np.float64)
        else:
            self._edge_axis = np.array([], dtype=np.int8)
            self._edge_sign = np.array([], dtype=np.float64)

        # Pack neighbor arrays (variable length per voxel)
        self._neighbors = [np.array(lst, dtype=np.int32) for lst in neighbors]

        # Surface mask: a voxel is on the surface if it has <6 face neighbours
        face_counts = np.zeros(n, dtype=np.int32)
        if len(self._edge_src) > 0:
            np.add.at(face_counts, self._edge_src, 1)
        # Each directed edge contributes one face; 6-connectivity has two
        # directed edges per physical face, so src count == 6 means fully
        # surrounded.
        self._is_surface = face_counts < 6

    @staticmethod
    def _coord_key(v) -> Tuple[int, int, int]:
        size = float(v.size)
        if size == 0:
            raise ValueError("Voxel size must be non-zero")
        return (
            int(round(float(v.x) / size)),
            int(round(float(v.y) / size)),
            int(round(float(v.z) / size)),
        )

    # ------------------------------------------------------------------
    # Read-only accessors
    # ------------------------------------------------------------------

    @property
    def n_voxels(self) -> int:
        return self._n

    @property
    def coord_to_idx(self) -> Dict[Tuple[int, int, int], int]:
        return self._coord_to_idx

    @property
    def edges_src(self) -> np.ndarray:
        """Directed edge source indices (E,)."""
        return self._edge_src

    @property
    def edges_dst(self) -> np.ndarray:
        """Directed edge destination indices (E,)."""
        return self._edge_dst

    @property
    def edges_axis(self) -> np.ndarray:
        """Axis of each 6-connectivity edge: 0=x, 1=y, 2=z."""
        if self.connectivity != 6:
            raise AttributeError("edges_axis is only defined for 6-connectivity")
        return self._edge_axis

    @property
    def edges_sign(self) -> np.ndarray:
        """Sign of each 6-connectivity edge (+1 or -1)."""
        if self.connectivity != 6:
            raise AttributeError("edges_sign is only defined for 6-connectivity")
        return self._edge_sign

    @property
    def is_surface(self) -> np.ndarray:
        """Boolean mask (N,) True for voxels with a missing face neighbour."""
        return self._is_surface

    def neighbors(self, idx: int) -> np.ndarray:
        """Return the 1-D array of neighbour indices for voxel *idx*."""
        if idx < 0 or idx >= self._n:
            raise IndexError(f"voxel index {idx} out of range [0, {self._n})")
        return self._neighbors[idx]

    def is_surface_voxel(self, idx: int) -> bool:
        """Return True if voxel *idx* is on the surface of the grid."""
        return bool(self._is_surface[idx])

    # ------------------------------------------------------------------
    # Topology mutation helpers used by VoxSym
    # ------------------------------------------------------------------

    @staticmethod
    def invalidate(topology: Optional["GridTopology"]) -> None:
        """No-op marker for symmetry with future cache-invalidation logic."""
        # The topology object is immutable; VoxSym replaces the reference.
        pass
