import numpy as np
import viser
import trimesh


class Renderer:
    """Takes all voxels from a VoxSym and draws all cubes in a single batch.

    Parameters
    ----------
    voxsym : VoxSym
    render_scale : float
        Multiply all positions and sizes by this factor before sending
        to viser.  Use when physics coordinates are very small (e.g. µm)
        and you need the rendered geometry to be at a visible scale.
        Default 1.0 (no scaling).
    """

    def __init__(self, voxsym, render_scale: float = 1.0):
        self.voxsym = voxsym
        self.render_scale = float(render_scale)
        self._cube_mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
        self._handle = None

    @property
    def handle(self):
        """Read-only access to the batched mesh handle (None before first render)."""
        return self._handle

    def render(self, server: viser.ViserServer):
        voxels = self.voxsym.get_voxels()
        n = len(voxels)
        if n == 0:
            return

        scl = self.render_scale

        positions = np.zeros((n, 3), dtype=np.float32)
        scales = np.zeros((n, 3), dtype=np.float32)
        colors = np.zeros((n, 3), dtype=np.uint8)
        opacities = np.ones((n,), dtype=np.float32)
        wxyzs = np.zeros((n, 4), dtype=np.float32)
        wxyzs[:, 0] = 1.0  # identity quaternion

        for i, voxel in enumerate(voxels):
            positions[i] = [voxel.x * scl, voxel.y * scl, voxel.z * scl]
            s = voxel.size * scl
            scales[i] = [s, s, s]
            colors[i] = voxel.color
            opacities[i] = getattr(voxel, "opacity", 1.0)

        vertices = np.array(self._cube_mesh.vertices, dtype=np.float32)
        faces = np.array(self._cube_mesh.faces, dtype=np.int32)

        if self._handle is None:
            self._handle = server.scene.add_batched_meshes_simple(
                name="/voxels",
                vertices=vertices,
                faces=faces,
                batched_wxyzs=wxyzs,
                batched_positions=positions,
                batched_scales=scales,
                batched_colors=colors,
                batched_opacities=opacities,
                flat_shading=True,
                side="double",
            )
        else:
            # Update existing batched mesh in-place.
            self._handle.batched_positions = positions
            self._handle.batched_scales = scales
            self._handle.batched_colors = colors
            self._handle.batched_opacities = opacities
