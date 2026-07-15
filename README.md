# VoxSym

VoxSym is a voxel-based physics simulation and visualization package. It runs a Python back-end that models heat diffusion, ion transport, electric/magnetic fields, forces and light-matter interactions on a regular 3-D voxel grid, and renders the result with a custom browser-based WebGL/Three.js viewer.

## Features

- **Voxel physics engine**: heat diffusion, ion diffusion, electric and magnetic fields, current density, mechanics, optics and magnetism solvers on a shared grid.
- **WebGL/Three.js viewer**: interactive browser GUI with a top toolbar, collapsible icon sidebar, per-layer icons, single-scalar-layer mode and canvas recording.
- **Recording / playback**: save simulations as `.npz` or `.csv` and reload them in the viewer; capture the WebGL canvas directly to `.webm` from the browser.
- **Headless mode**: run simulations with `backend=None` for batch jobs or automated sweeps without starting a server.

## Installation

```bash
# Clone the repository
git clone https://github.com/nousresearch/voxsym.git
cd voxsym

# Create a virtual environment and install voxsym
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .

# Optional: install development tools (pytest, ruff)
python -m pip install -e ".[dev]"
```

The WebGL backend is enabled by default and requires `tornado` + `websockets`, which are now core dependencies.

## Quickstart

Run the basic copper cube example:

```bash
python examples/01_basic_grid.py
```

Then open `http://0.0.0.0:8080` in your browser (the server binds to `0.0.0.0` by default).

A minimal scripted example:

```python
from voxsym import VoxSym, Voxel
from voxsym.material import COPPER

vs = VoxSym()  # defaults to backend="webgl"

for x in range(-3, 3):
    for y in range(-3, 3):
        for z in range(-3, 3):
            v = Voxel(x=x, y=y, z=z, size=1, color=COPPER.color)
            v.material = COPPER
            vs.add_voxel(v)

vs.setup_gui()  # prints the WebGL URL and initializes the renderer
vs.run_simulation()
```

## Architecture

- **Back-end** (`voxsym/`): owns the voxel grid, physics solvers, recorder and player. It is independent of any renderer and can run headless.
- **Renderer** (`voxsym/visualization/`): a small backend abstraction (`RenderBackend`) with a single WebGL implementation that serializes frames to JSON and streams them over WebSocket.
- **Front-end** (`voxsym/web/`): static HTML/CSS/JS viewer that connects to the Python simulation server over WebSocket/HTTP.

## Viewer controls

The viewer is laid out as a full-screen 3-D viewport with a fixed top bar and a left icon sidebar.

### Top bar

The top bar runs across the top of the window and contains the primary simulation and session controls:

- **▶ / ⏸ Play** — single toggle button that plays or pauses the simulation. The button icon mirrors the current server state.
- **↺ Reset** — resets the simulation to its initial state.
- **⏹ Stop** — stops the simulation loop.
- **t = …** — adaptive time badge. The badge chooses the coarsest readable unit automatically (`s`, `ms`, `µs` or `ns`) based on the current simulation time magnitude.
- **● Record** — starts or stops a browser-side `MediaRecorder` capture of the WebGL canvas. While recording the button pulses red and shows the elapsed seconds; stopping downloads a `.webm` file.
- **? Help** — reserved for on-demand help / shortcuts.

### Icon sidebar

The left icon sidebar switches between collapsible tool panels:

| Icon | Panel | Purpose |
| --- | --- | --- |
| 🎨 | Layers | Choose the active scalar layer and toggle vector overlays. |
| ⚙️ | Display | Global opacity, vector arrow scale and steps-per-frame. |
| ✂️ | Cross section | Choose a slicing axis (`off` / `x` / `y` / `z`) and move the cut plane. |
| 💾 | Recording | Drag-and-drop upload of `.npz` / `.csv` recordings and timeline controls. |

### Layer model

Layers are split into two groups:

- **Scalar layers** — `Base color`, `Temperature`, `Ion concentration`, `Material`. Exactly one scalar layer is shown at a time; selecting a new scalar layer deactivates the previous one.
- **Vector overlays** — `Electric field`, `Magnetic field`, `Current`. These are independent toggles and can be enabled on top of any scalar layer. Vector overlays are rendered as arrow glyphs whose orientation is computed explicitly from field tail→head data.

## Performance tips

- **Steps per frame** — Increase `steps_per_frame` to advance physics further between renders. The display panel exposes a slider; set it programmatically with `vs.set_steps_per_frame(n)`.
- **EM-field period** — Electric/magnetic field solves are the biggest per-step cost. Set `vs.set_em_field_period(n)` to recompute EM fields only every `n` sub-steps. The default matches `steps_per_frame` so fields solve once per rendered frame. Lower it if rapid field transients matter.
- **Target FPS / adaptive throttling** — Set `vs.target_fps` (default `60`) to cap frames while playing. While paused the loop throttles to 10 fps automatically to save CPU/GPU.
- **Shadows toggle** — Shadows look nice but hurt large grids. The display panel has a toggle; default is off for grids above ~1 k voxels.
- **Payload deduplication** — The WebGL backend caches unchanged metadata (`active_layers`, scalar layer, colormap, range) and only resends them when they change, which lowers per-frame JSON size.
- **Headless mode** — For sweeps or CI use `backend=None` to skip the server and rendering entirely.

## Headless mode

For batch jobs or automated sweeps, create `VoxSym(backend=None)` to avoid starting any server:

```python
vs = VoxSym(backend=None)
# build voxel grid ...
for i in range(100):
    vs.step_and_update(dt=1e-6)
```

## Recording and Playback

Every `VoxSym` instance records state automatically. After a simulation run, save programmatically:

```python
# Record while running
for i in range(50):
    vs.step_and_update(dt=200.0)

# Save both .npz and .csv
npz_path, csv_path = vs.autosave()
```

To replay a recording in a fresh viewer window:

```bash
python viewer.py results/my_simulation.npz
```

or drag-and-drop a `.npz`/`.csv` file into the browser viewer.

You can also capture the live canvas to a `.webm` video by pressing the **● Record** button in the top bar.

## Legacy Viser backend

The Viser backend has been removed. VoxSym now ships with the WebGL/Three.js viewer as the default renderer. Use `backend=None` for headless use.

## Development

```bash
# Run tests
pytest tests/ -v

# Lint
ruff check voxsym examples tests
```

## License

MIT
