# Rendering architecture

VoxSym separates physics simulation from visualization through a small backend abstraction. The same simulation code drives the browser-based WebGL/Three.js viewer or runs completely headless.

## Backend abstraction

All render backends implement `RenderBackend` defined in `voxsym/visualization/backends/base.py`:

| Method | Purpose |
| --- | --- |
| `render(positions, scales, colors, opacities)` | Update or create the batched voxel mesh. |
| `add_arrows(points, colors, shaft_radius, head_radius, head_length)` | Add vector-field arrow overlays. |
| `set_opacity(opacity)` | Set the global opacity multiplier. |
| `clear()` | Remove all geometry managed by this backend. |
| `handle` | Implementation-specific server handle. |

### Concrete backend

* **`WebGLBackend`** (`voxsym/visualization/backends/webgl_backend.py`) — does not draw locally. It serializes the current frame into a compact JSON payload and hands it to `WebGLServer`, which streams it to browser clients over WebSocket.

The legacy Viser backend has been removed; `WebGLBackend` is the only concrete renderer.

## Switching backends

The backend is selected when `VoxSym` is created:

```python
from voxsym import VoxSym

# Default browser-based WebGL/Three.js viewer
vs = VoxSym(backend="webgl", port=8080)

# Headless simulation (no renderer, no server)
vs = VoxSym(backend=None)
```

The WebGL server binds to `0.0.0.0` by default so the viewer is reachable from non-local clients.

## JSON wire protocol

The WebGL backend communicates with the browser through text JSON frames. The payload is optimized so only changed data is sent each frame.

### Server → client: `FramePayload`

Defined in `voxsym/web/protocol.py`:

```json
{
  "type": "frame",
  "time": 0.0,
  "frame_index": 0,
  "opacity": 1.0,
  "voxels": {
    "count": 3,
    "positions": [x0, y0, z0, x1, y1, z1, ...],
    "sizes": [s0, s1, ...],
    "colors": [r0, g0, b0, r1, g1, b1, ...],
    "opacities": [a0, a1, ...]
  },
  "arrows": {
    "count": 1,
    "points": [[tail_x, tail_y, tail_z, head_x, head_y, head_z], ...],
    "colors": [[r, g, b], ...]
  },
  "active_layers": ["voxel_color"]
}
```

Voxel arrays are flattened so the JavaScript front end can upload them directly into a `THREE.InstancedMesh`. The browser camera is automatically framed around the incoming voxel bounding box.

### Payload deduplication

The WebGL backend keeps the previous broadcast payload and omits metadata fields that have not changed:

- `active_layers`
- active scalar layer and `scalar_range`
- `colormap`

The client merges incoming frames onto `lastFrame`, so missing fields keep their previous values. This reduces per-frame JSON size, especially when only voxel positions/colors change.

### Adaptive throttling

`VoxSym.target_fps` (default `60`) controls the render loop while playing. The simulation loop measures elapsed time per iteration and sleeps for the remainder of the target frame interval, with a small minimum sleep. While paused the target drops to 10 fps to reduce idle CPU/GPU usage. The visualizer throttle is aligned with the same target.

### EM-field period

Poisson and EM field updates are expensive. `VoxSym` exposes `set_em_field_period(n)` so fields are only recomputed every `n` sub-steps. The default is `steps_per_frame`, meaning one EM solve per rendered frame. This is the single biggest lever for large or multi-sub-step simulations.

The `arrows.points` array is ordered tail→head for every arrow so the client can reconstruct an oriented shaft + cone glyph without guessing direction. Each arrow also carries a `base_size` value when the payload is built:

```json
{
  "arrows": {
    "count": 1,
    "points": [[tail_x, tail_y, tail_z, head_x, head_y, head_z]],
    "colors": [[r, g, b]],
    "base_size": 1.0
  }
}
```

`base_size` is the rendered size of one voxel. The arrow renderer uses it to clamp the arrow length to a visible range and to offset the arrow so it sits just outside the source voxel instead of being buried inside.

### GPU-friendly frontend defaults

The Three.js frontend reuses `InstancedMesh` geometry when voxel/arrow counts stay the same, only updating per-instance matrices and colors. Arrow meshes are reused instead of rebuilt every frame; when the count changes the group is recreated. Shadows are off by default for grids above ~1 k voxels and can be toggled from the display panel.

### Client → server: `CommandPayload`

Control messages from the browser GUI:

```json
{ "cmd": "play" }
{ "cmd": "pause" }
{ "cmd": "reset" }
{ "cmd": "stop" }
{ "cmd": "set_layer", "layer": "temperature", "active": true }
{ "cmd": "set_opacity", "value": 0.8 }
{ "cmd": "set_cross_section", "axis": "x", "pos": 0.5 }
{ "cmd": "set_arrow_scale", "value": 1.2 }
{ "cmd": "set_time_scale", "value": 10 }
```

`CommandPayload.decode(raw)` parses a JSON string into a typed dataclass; `FramePayload.encode()` serializes a frame for broadcast. `WebGLServer.handle_command()` routes each command to the attached `VoxSym` instance.

## Static viewer and WebSocket control

The WebGL server (`voxsym/web/server.py`) is a Tornado application that:

1. Serves the static HTML/CSS/JS viewer from `voxsym/web/static/` on `http://host:port/`.
2. Accepts WebSocket connections on `/ws`.
3. Broadcasts the latest `FramePayload` to all connected clients whenever `VoxSym.render()` is called.
4. Receives `CommandPayload` messages and updates simulation control flags (`play`, `pause`, `reset`, `stop`, layer toggles, opacity, cross-section, arrow scale, steps-per-frame).

Usage in a script:

```python
from voxsym import VoxSym

vs = VoxSym(backend="webgl", port=8080)
# build voxel grid ...
print(f"Open http://{vs.server.host}:{vs.server.port}")
vs.run_simulation(dt=1.0)
```

## How layers work

Scalar color layers (`voxel_color`, `temperature`, `material`, `ion_concentration`) are mutually exclusive: activating one deactivates the others. The active scalar layer mutates `voxel.color` before `Renderer.render()` builds the per-voxel arrays. Vector overlay layers (`electric_field`, `magnetic_field`, `current`) can coexist and are drawn as arrow glyphs via `RenderBackend.add_arrows()`. The active layer list is included in every `FramePayload` so the browser UI can keep its layer cards in sync.

In the viewer, scalar layers are presented as icon cards and vector overlays as toggle chips. Selecting a new scalar card sends `set_layer` for that layer and, on the client, clears the previous scalar layer; toggling a vector chip sends `set_layer` for just that overlay.

## How arrows work

`Visualizer` subsamples non-zero field vectors, normalizes them, and builds a compact `(tail, head)` point array. The browser reconstructs cylinder/cone arrow geometry from these points:

1. Read `base_size` from the arrow payload (or default to `1.0`).
2. For each arrow, compute `dir = head - tail` and `len = |dir|`.
3. Clamp `len` to a visible range derived from `base_size`.
4. Offset the tail away from the voxel center along `dir` so the arrowhead is visible above the voxel surface.
5. Rotate the shaft+cone geometry from the unrotated +Y axis onto `dir` and set the total scale to `tip.distanceTo(tail) / 1.25` (the unrotated glyph height is `1.25` units).

This explicit tail→head ordering makes arrow orientation unambiguous, even for very small or very large field magnitudes.

## Adaptive time display

The viewer's top-bar time badge formats `payload.time` with the coarsest readable unit:

| Magnitude | Display |
| --- | --- |
| `|t| ≥ 1` | `t = X.XXX s` |
| `1e-3 ≤ |t| < 1` | `t = X.XX ms` |
| `1e-6 ≤ |t| < 1e-3` | `t = X.XX µs` |
| otherwise | `t = X.XX ns` |

The server always sends `time` in seconds; the client performs the unit conversion.

## Canvas recording

The top-bar **● Record** button starts a browser-side `MediaRecorder` capture of the WebGL canvas at 30 fps. While recording, the button shows the elapsed time and pulses red. Clicking it again stops the recorder and triggers a download of a `voxsym-<timestamp>.webm` file. No server-side support is required; recording is purely a client-side operation.

## Adding a new layer

1. Add a constant to `visualizer.Layer` (and the matching `VoxSym.LAYER_*` alias).
2. Register a render callback in `Visualizer._callbacks` (for vector layers) or add it to `scalar_priority` in `_apply_scalar_colors()` (for scalar layers).
3. Implement the colour/arrow computation method, e.g. `_color_by_my_field()` or `_render_my_field()`.
4. Add the layer to the layer panel template in `voxsym/web/static/js/gui.js` (`SCALAR_LAYERS` or `VECTOR_LAYERS`).
5. Update this document with the new layer name and semantics.

## Headless mode

For batch jobs, use `backend=None`. No server is started, `Renderer` receives `None` as its backend, and `VoxSym.render()` becomes a no-op. The physics solvers and recorder continue to work normally.

```python
vs = VoxSym(backend=None)
for i in range(1000):
    vs.step_and_update(dt=1e-7)
```
