"""Verify 1D ion diffusion against analytical Gaussian/erf solution."""
import sys
from math import erf
import numpy as np

sys.path.insert(0, '/home/atled/workspace/voxsym')
from voxsym import VoxSym, Voxel, Material

D = 1e-9          # m^2/s
size = 1e-6       # m
T = 1e-3          # total time to advance

print(f"voxel size: {size:.1e} m")
print(f"diffusion cap per sub-step: {size**2 / (6 * D):.3e} s")

mat = Material(
    name='test',
    conductivity=1.0,
    thermal_conductivity=1e-12,  # make thermal diffusion negligible so ion cap dominates
    specific_heat=1.0,
    density=1.0,
    ion_diffusivity=D,
    ionic_valence=0,  # pure diffusion, no migration
    ion_conc_max=1000.0,
    color=(200, 200, 200),
)

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

vs.set_time_step(T)
vs.dt_safety_factor = 0.9
cap = vs.max_stable_dt()
print(f"reported max_stable_dt: {cap:.3e} s")
print(f"sub-steps for dt={T}: {int(np.ceil(T / cap))}")

vs.step_and_update(T)

# Analytical solution for initial box of width 5*size (from -2.5size to +2.5size)
w = 2.5 * size  # half-width
def analytical(x):
    a = 2 * np.sqrt(D * T)
    return 500.0 * (erf((x + w) / a) - erf((x - w) / a))

xs = np.array([v.x for v in vs.voxels])
sim = np.array([v.ion_concentration for v in vs.voxels])
anal = np.array([analytical(x) for x in xs])

print("x\t\tsim\tanal\terr")
for x, s, a in zip(xs, sim, anal):
    print(f"{x:.2e}\t{s:6.1f}\t{a:6.1f}\t{abs(s - a):.1f}")

print(f"max error:     {np.max(np.abs(sim - anal)):.2f} mol/m^3")
print(f"mean error:    {np.mean(np.abs(sim - anal)):.2f} mol/m^3")
print(f"total sim:     {sim.sum():.1f}  (initial 5000)")
print(f"conservation:  {abs(sim.sum() - 5000.0) < 1.0}")

# Verify color mapping changes with ion concentration
from voxsym.visualization.visualizer import Visualizer, Layer
from voxsym.visualization.renderer import Renderer
from voxsym.visualization.backends.webgl_backend import WebGLBackend

vs2 = VoxSym(backend='webgl')
for i in range(5):
    v = Voxel((i - 2) * size, 0.0, 0.0, size)
    v.material = mat
    v.ion_concentration = float(i * 250)  # 0, 250, 500, 750, 1000
    vs2.add_voxel(v)

backend = WebGLBackend(vs2, None)
renderer = Renderer(vs2)
vis = Visualizer(None, vs2, renderer)
vis._backend = backend
vis.set_layer(Layer.ION_CONCENTRATION, True)
vis.render()
frame = backend._latest_payload if hasattr(backend, '_latest_payload') else backend.get_latest_frame_payload()
print("voxel colors for ion concentrations 0,250,500,750,1000:")
print(frame.voxels['colors'])

# Also verify heat map path
vis2 = Visualizer(None, vs2, renderer)
vis2._backend = backend
vis2.set_layer(Layer.TEMPERATURE, True)
for i, v in enumerate(vs2.voxels):
    v.temperature = 300.0 + float(i * 50)
vis2.render()
frame2 = backend._latest_payload if hasattr(backend, '_latest_payload') else backend.get_latest_frame_payload()
print("voxel colors for temperatures 300,350,400,450,500:")
print(frame2.voxels['colors'])
