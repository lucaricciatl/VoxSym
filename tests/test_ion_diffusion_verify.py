"""Verify ion diffusion against an analytical 1D solution."""

import numpy as np
from math import erf
import numpy as np

_vec_erf = np.vectorize(erf)

from voxsym import VoxSym, Voxel, Material


def _analytical_box_diffusion(x, D, t, half_width):
    """Error-function solution for an initial rectangular concentration box."""
    a = 2 * np.sqrt(D * t)
    x = np.asarray(x, dtype=np.float64)
    return 500.0 * (_vec_erf((x + half_width) / a) - _vec_erf((x - half_width) / a))


def make_test_material():
    return Material(
        name='diffusion_test',
        conductivity=1.0,
        thermal_conductivity=1e-12,  # make heat diffusion negligible
        specific_heat=1.0,
        density=1.0,
        ion_diffusivity=1e-9,
        ionic_valence=0,  # pure diffusion, no migration
        ion_conc_max=1000.0,
        color=(200, 200, 200),
    )


def test_1d_fick_diffusion_matches_analytical():
    """Explicit Fick diffusion should agree with the analytical erf profile."""
    D = 1e-9          # m^2/s
    size = 1e-6       # m
    t_total = 1e-3    # s

    mat = make_test_material()
    vs = VoxSym(backend=None)

    nx = 21
    for i in range(nx):
        v = Voxel((i - nx // 2) * size, 0.0, 0.0, size)
        v.material = mat
        if abs(i - nx // 2) <= 2:
            v.ion_concentration = 1000.0
        else:
            v.ion_concentration = 0.0
        vs.add_voxel(v)

    vs.disable_heat()
    vs.set_time_step(t_total)
    vs.dt_safety_factor = 1.0

    cap = vs.max_stable_dt()
    expected_cap = size**2 / (6 * D)
    assert np.isclose(cap, expected_cap, rtol=0.1)

    vs.step_and_update(t_total)

    xs = np.array([v.x for v in vs.voxels])
    sim = np.array([v.ion_concentration for v in vs.voxels])
    anal = _analytical_box_diffusion(xs, D, t_total, 2.5 * size)

    # Peak error should be small relative to the 1000 mol/m^3 range.
    assert np.max(np.abs(sim - anal)) < 25.0
    # Total ions should be conserved.
    assert np.isclose(sim.sum(), 5.0 * 1000.0, rtol=1e-3)


def test_diffusion_changes_voxel_color():
    """Changing ion concentration must change the rendered scalar color."""
    from voxsym.visualization.visualizer import Visualizer, Layer
    from voxsym.visualization.renderer import Renderer
    from voxsym.visualization.backends.webgl_backend import WebGLBackend

    size = 1e-6
    mat = make_test_material()
    vs = VoxSym(backend=None)
    for i in range(5):
        v = Voxel((i - 2) * size, 0.0, 0.0, size)
        v.material = mat
        v.ion_concentration = float(i * 250)
        vs.add_voxel(v)

    backend = WebGLBackend(vs, None)
    renderer = Renderer(vs)
    renderer.backend = backend
    vis = Visualizer(None, vs, renderer)
    vis.set_layer(Layer.ION_CONCENTRATION, True)
    vis.render()

    colors = backend._latest_payload.voxels['colors']
    # 5 voxels * 3 channels = 15 values; they should not all be equal.
    assert len(colors) == 15
    assert len(set(colors)) > 3

    # Same for temperature layer
    vis2 = Visualizer(None, vs, renderer)
    vis2.set_layer(Layer.TEMPERATURE, True)
    for i, v in enumerate(vs.voxels):
        v.temperature = 300.0 + float(i * 50)
    vis2.render()
    colors2 = backend._latest_payload.voxels['colors']
    assert len(colors2) == 15
    assert len(set(colors2)) > 3
