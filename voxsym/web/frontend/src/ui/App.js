import * as THREE from 'three';
import { Scene } from '../scene/Scene.js';
import { Store, LAYERS, SCALAR_LABELS } from '../store/Store.js';
import { WebSocketClient } from '../ws/WebSocketClient.js';
import { updateVoxels } from '../render/Voxels.js';
import { updateArrows } from '../render/Arrows.js';
import { Colorbar } from './Colorbar.js';
import { Recorder } from './Recorder.js';
import { Toast } from './Toast.js';
import { LayersPanel } from './LayersPanel.js';
import { SettingsPanel } from './SettingsPanel.js';
import { InspectPanel } from './InspectPanel.js';
import './App.css';

const COLORMAP_STOPS = {
  viridis: [
    [0.0, '#440154'],
    [0.25, '#3b528b'],
    [0.5, '#21918c'],
    [0.75, '#5ec962'],
    [1.0, '#fde725'],
  ],
  plasma: [
    [0.0, '#0d0887'],
    [0.25, '#5b02a3'],
    [0.5, '#9c179e'],
    [0.75, '#ed7953'],
    [1.0, '#fdb42f'],
  ],
  inferno: [
    [0.0, '#000004'],
    [0.25, '#420a68'],
    [0.5, '#932667'],
    [0.75, '#e16462'],
    [1.0, '#fca50a'],
  ],
  magma: [
    [0.0, '#000004'],
    [0.25, '#3b0f70'],
    [0.5, '#8c2981'],
    [0.75, '#de4968'],
    [1.0, '#fcfdbf'],
  ],
};

function formatTime(seconds) {
  const t = Math.abs(seconds);
  if (t === 0) return 't = 0 s';
  if (t < 1e-9) {
    const ps = Math.round(t * 1e12);
    return `t = ${ps} ps`;
  }
  if (t < 1e-6) {
    const ns = Math.round(t * 1e9);
    return `t = ${ns} ns`;
  }
  if (t < 1e-3) {
    const us = Math.round(t * 1e6);
    return `t = ${us} µs`;
  }
  if (t < 1.0) {
    const ms = t * 1e3;
    return `t = ${ms.toFixed(3).replace(/\.?0+$/, '')} ms`.replace(/\.$/, '');
  }
  return `t = ${t.toFixed(3).replace(/\.?0+$/, '')} s`.replace(/\.$/, '');
}

export class App {
  constructor(root) {
    this.root = root;
    this.store = new Store();
    this.scene = null;
    this.ws = null;
    this.panelContent = null;
  }

  mount() {
    this.root.innerHTML = `
      <header id="topbar">
        <nav class="topnav">
          <button class="nav-item" data-menu="simulation">Simulation</button>
          <button class="nav-item" data-menu="files">Files</button>
          <button class="nav-item" data-menu="layers">Layers</button>
          <button class="nav-item" data-menu="fields">Fields</button>
          <button class="nav-item" data-menu="recording">Recording</button>
          <button class="nav-item" data-menu="inspect">Inspect</button>
          <button class="nav-item" data-menu="settings">Settings</button>
        </nav>
        <span id="recording-indicator" class="recording-indicator" title="Recording video" style="display:none">● REC</span>
      </header>
      <aside id="panel">
        <div id="panel-content"></div>
      </aside>
      <div id="viewport"></div>
      <div id="bottom-bar">
        <span id="sim-time">t = 0 s</span>
        <span id="status">disconnected</span>
      </div>
      <div id="inspector-overlay" class="overlay" style="display:none"></div>
      <div id="viewport-controls">
        <button class="toggle ${this.store.state.showGrid ? 'active' : ''}" id="toggle-grid" title="Base grid">
          <span class="icon">#</span> Grid
        </button>
        <button class="toggle ${this.store.state.showAxes ? 'active' : ''}" id="toggle-axes" title="Axis">
          <span class="icon">+</span> Axis
        </button>
        <button class="toggle" id="toggle-ortho" title="Orthographic camera">
          <span class="icon">O</span> Ortho
        </button>
        <button class="btn" id="camera-reset" title="Reset camera">
          Reset
        </button>
      </div>
      <div id="probe-tooltip" class="probe-tooltip" style="display:none"></div>
    `;

    this.scene = new Scene(this.root.querySelector('#viewport'));
    this.colorbar = new Colorbar(this.root, this.store);
    this.toast = new Toast(this.root);

    this.ws = new WebSocketClient(this.store, (payload) => this.onFrame(payload));

    this.panelContent = this.root.querySelector('#panel-content');
    this.layersPanel = new LayersPanel(this.panelContent, this.store);
    this.settingsPanel = new SettingsPanel(this.panelContent, this.store, this.ws);
    this.inspectPanel = new InspectPanel(this.panelContent, this.store, this.ws, this.root.querySelector('#inspector-overlay'));

    this.store.subscribe((state, patch) => this.onStoreChange(state, patch));

    this._bindTopNav();
    this._bindViewportControls();
    this._bindViewportClick();

    this._openMenu('layers');

    this.store.subscribe((state, patch) => {
      if (patch.hoveredVoxel !== undefined) {
        this._updateSelectionPreview(state.hoveredVoxel);
      }
      if (patch.inspectedVoxel !== undefined) {
        this._updateSelectionPreview(state.hoveredVoxel);
      }
      if (patch.connected !== undefined) {
        const el = this.root.querySelector('#status');
        if (el) el.textContent = state.connected ? 'connected' : 'disconnected';
      }
      if (patch.time !== undefined || patch.frame !== undefined) {
        const timeEl = this.root.querySelector('#sim-time');
        if (timeEl) timeEl.textContent = formatTime(state.time);
      }
      if (patch.showGrid !== undefined || patch.showAxes !== undefined) {
        this._updateSceneHelpers(state.showGrid, state.showAxes);
        const gridBtn = this.root.querySelector('#toggle-grid');
        const axesBtn = this.root.querySelector('#toggle-axes');
        gridBtn?.classList.toggle('active', state.showGrid);
        axesBtn?.classList.toggle('active', state.showAxes);
      }
      if (patch.recording !== undefined) {
        const ind = this.root.querySelector('#recording-indicator');
        if (ind) ind.style.display = state.recording ? 'inline-block' : 'none';
        if (state.recording) {
          const ok = this.recorder?.start(2);
          if (!ok) {
            const msg = this.recorder?.lastError || 'Recording not supported in this browser';
            this.toast?.warn(msg);
            if (ind) ind.style.display = 'none';
          }
        } else {
          this.recorder?.stop();
        }
      }
      if (patch.toast !== undefined) {
        console.log('App toast patch', patch.toast);
        const { kind, message } = patch.toast || {};
        if (message && this.toast) {
          this.toast.show(message, kind || 'info', kind === 'error' ? 5000 : 3000);
        } else {
          console.warn('Toast patch ignored', { kind, message, hasToast: !!this.toast });
        }
      }
      if ((patch.recording !== undefined || patch.playing !== undefined || patch.timeStep !== undefined || patch.stepsPerFrame !== undefined) && (this._currentMenu === 'simulation' || this._currentMenu === 'recording')) {
        if (this._currentMenu === 'recording') {
          this._renderRecordingPanel();
        } else {
          this._renderSimulationPanel();
        }
      }
    });

    this.recorder = null;
    if (this.scene) {
      this.recorder = new Recorder(this.store, this.scene);
    }

    window.voxsymApp = this;
    window.store = this.store;
  }

  onFrame(payload) {
    if (!payload || payload.type !== 'frame') return;
    window.lastFrame = payload;
    updateVoxels(this.scene, payload);
    const arrowCount = updateArrows(this.scene, payload.arrows);
    this.store.setFrameMeta({
      time: payload.time ?? 0,
      frame: payload.frame_index ?? 0,
      voxelCount: payload.voxels?.count ?? 0,
      arrowCount,
    });
    // Keep playback indicator in sync with the server.  Full frames can be
    // queued before the server processed a play/pause command, so we ignore
    // stale playing mismatches for a short window after a local toggle.
    // Authoritative state messages bypass this guard entirely and update
    // the store directly; this guard only catches full-frame races.
    if (payload.playing !== undefined && payload.playing !== this.store.state.playing) {
      const recentToggle = this._lastPlayToggle && (performance.now() - this._lastPlayToggle) < 1000;
      if (!recentToggle) {
        this.store.setPlaying(payload.playing);
      }
    }
    if (this._lastPlayToggle && (performance.now() - this._lastPlayToggle) >= 1000) {
      this._lastPlayToggle = undefined;
    }
    this.store.setScalarMeta({
      scalarRange: payload.scalar_range,
      colormap: payload.colormap,
      scalarValues: payload.scalar_values,
    });

    const positions = payload.voxels?.positions;
    if (positions && positions.length >= 3) {
      let minX = Infinity, maxX = -Infinity;
      let minY = Infinity, maxY = -Infinity;
      let minZ = Infinity, maxZ = -Infinity;
      for (let i = 0; i < positions.length; i += 3) {
        const x = positions[i], y = positions[i + 1], z = positions[i + 2];
        if (x < minX) minX = x; if (x > maxX) maxX = x;
        if (y < minY) minY = y; if (y > maxY) maxY = y;
        if (z < minZ) minZ = z; if (z > maxZ) maxZ = z;
      }
      this.store.setBBox({ x: [minX, maxX], y: [minY, maxY], z: [minZ, maxZ] });
    }
    if (payload.active_layers && Array.isArray(payload.active_layers) && !this._initialSyncDone) {
      this._initialSyncDone = true;
      for (const layer of payload.active_layers) {
        if (LAYERS.SCALAR.includes(layer)) {
          this.store.state.activeScalar = layer;
        }
      }
      const vectors = new Set();
      for (const layer of payload.active_layers) {
        if (LAYERS.VECTOR.includes(layer)) {
          vectors.add(layer);
        }
      }
      this.store.state.activeVectors = vectors;
      this.store._notify({ activeScalar: this.store.state.activeScalar, activeVectors: new Set(vectors) });
    }
  }

  onStoreChange(state, patch) {
    if (patch.opacity !== undefined) {
      this.ws.send({ cmd: 'set_opacity', value: state.opacity });
    }
    if (patch.activeScalar !== undefined) {
      for (const s of LAYERS.SCALAR) {
        this.ws.send({ cmd: 'set_layer', layer: s, active: s === state.activeScalar });
      }
    }
    if (patch.activeVectors !== undefined) {
      for (const v of LAYERS.VECTOR) {
        const active = state.activeVectors.has(v);
        this.ws.send({ cmd: 'set_layer', layer: v, active });
      }
    }
    if (patch.arrowScale !== undefined) {
      this.ws.send({ cmd: 'set_arrow_scale', value: state.arrowScale });
    }
    if (patch.stepsPerFrame !== undefined) {
      this.ws.send({ cmd: 'set_time_scale', value: state.stepsPerFrame });
    }
    if (patch.timeStep !== undefined) {
      this.ws.send({ cmd: 'set_time_step', value: state.timeStep });
    }
    if (patch.playing !== undefined) {
      this.ws.send({ cmd: state.playing ? 'play' : 'pause' });
    }
    if (patch.showGrid !== undefined || patch.showAxes !== undefined) {
      this._updateSceneHelpers(state.showGrid, state.showAxes);
    }
  }

  _openMenu(menu) {
    this._currentMenu = menu;
    this.panelContent.innerHTML = '';
    this.root.querySelectorAll('.nav-item').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.menu === menu);
    });
    switch (menu) {
      case 'layers':
        this.layersPanel.renderLayers();
        break;
      case 'fields':
        this.layersPanel.renderFields();
        break;
      case 'simulation':
        this._renderSimulationPanel();
        break;
      case 'files':
        this._renderFilesPanel();
        break;
      case 'inspect':
        this.inspectPanel.render();
        break;
      case 'settings':
        this.settingsPanel.render();
        break;
      case 'recording':
        this._renderRecordingPanel();
        break;
      default:
        break;
    }
  }

  _renderSimulationPanel() {
    const isPlaying = this.store.state.playing;
    const dt = this.store.state.timeStep;
    const steps = this.store.state.stepsPerFrame;
    this.panelContent.innerHTML = `
      <section id="simulation-panel">
        <h3>Simulation</h3>
        <div class="btn-stack">
          <button class="btn primary" id="sim-play-pause">${isPlaying ? 'Pause' : 'Play'}</button>
          <button class="btn" id="sim-step"${isPlaying ? ' disabled' : ''}>Step once</button>
          <button class="btn" id="sim-reset">Reset simulation</button>
          <button class="btn" id="sim-restart">Restart</button>
        </div>
        <p class="hint">Status: <span id="sim-status">${isPlaying ? 'running' : 'paused'}</span></p>
        <h4>Timing</h4>
        <label>Time step <span id="dt-val">${dt.toExponential(2)}</span> s
          <input id="dt-input" type="number" min="1e-9" max="1" step="any" value="${dt}">
        </label>
        <label>Steps/frame <span id="steps-val">${steps}</span>
          <input id="steps-input" type="range" min="1" max="100" step="1" value="${steps}">
        </label>
      </section>
    `;
    this.panelContent.querySelector('#sim-play-pause')?.addEventListener('click', () => {
      this._lastPlayToggle = performance.now();
      this.store.setPlaying(!this.store.state.playing);
    });
    this.panelContent.querySelector('#sim-step')?.addEventListener('click', () => {
      if (!this.store.state.playing) this.ws.send({ cmd: 'single_step' });
    });
    this.panelContent.querySelector('#sim-reset')?.addEventListener('click', () => {
      this.store.setPlaying(false);
      this.ws.send({ cmd: 'reset' });
    });
    this.panelContent.querySelector('#sim-restart')?.addEventListener('click', () => this.ws.send({ cmd: 'restart' }));
    this.panelContent.querySelector('#dt-input')?.addEventListener('change', (e) => {
      this.store.setTimeStep(e.target.value);
    });
    this.panelContent.querySelector('#steps-input')?.addEventListener('input', (e) => {
      this.store.setStepsPerFrame(e.target.value);
    });
  }

  _renderRecordingPanel() {
    const recording = this.store.state.recording;
    const frameSize = this.scene ? `${Math.round(this.scene.renderer.domElement.width * 2)} × ${Math.round(this.scene.renderer.domElement.height * 2)}` : '—';
    this.panelContent.innerHTML = `
      <section id="recording-panel">
        <h3>Recording</h3>
        <div class="btn-stack">
          <button class="btn" id="rec-frame" ${recording ? 'disabled' : ''}>Capture high-res PNG</button>
          <button class="btn ${recording ? 'danger' : 'primary'}" id="rec-video">${recording ? 'Stop video recording' : 'Record high-res WebM'}</button>
          <button class="btn" id="rec-data">Download frame data (CSV)</button>
        </div>
        <p class="hint">PNG/WebM are rendered at 2× the on-screen resolution (${frameSize}).</p>
        <p class="hint">CSV contains voxel positions and the current scalar value for the active layer.</p>
      </section>
    `;
    this.panelContent.querySelector('#rec-frame')?.addEventListener('click', async () => {
      if (!this.scene) return;
      this.toast?.show('Rendering high-res PNG...', 'info', 2000);
      const blob = await this.scene.capturePng(2, this._pngOverlay.bind(this));
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `voxsym-frame-${Date.now()}.png`;
      a.click();
      URL.revokeObjectURL(url);
    });
    this.panelContent.querySelector('#rec-video')?.addEventListener('click', () => {
      if (!this.recorder) return;
      if (this.recorder.isSupported()) {
        this.store.setRecording(!recording);
      } else {
        this.toast?.warn('Video recording not supported in this browser');
      }
    });
    this.panelContent.querySelector('#rec-data')?.addEventListener('click', () => this._downloadFrameDataCsv());
  }

  _downloadFrameDataCsv() {
    const frame = window.lastFrame;
    if (!frame?.voxels) {
      this.toast?.warn('No frame data available yet');
      return;
    }
    const positions = frame.voxels.positions || [];
    const scalars = frame.scalar_values || [];
    const layer = frame.scalar_layer || 'material';
    const count = frame.voxels.count ?? (positions.length / 3);
    let csv = `x,y,z,${layer}\n`;
    for (let i = 0; i < count; i++) {
      const x = positions[i * 3] ?? 0;
      const y = positions[i * 3 + 1] ?? 0;
      const z = positions[i * 3 + 2] ?? 0;
      const v = scalars[i] ?? 0;
      csv += `${x},${y},${z},${v}\n`;
    }
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `voxsym-data-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  _pngOverlay(ctx, w, h) {
    const pad = 24;
    const { time, activeScalar, scalarRange, colormap } = this.store.state;

    // Semi-transparent top-left time stamp
    ctx.font = 'bold 22px sans-serif';
    ctx.textBaseline = 'top';
    const timeText = formatTime(time);
    const tw = ctx.measureText(timeText).width;
    ctx.fillStyle = 'rgba(0, 0, 0, 0.55)';
    ctx.fillRect(pad, pad, tw + 18, 34);
    ctx.fillStyle = '#ffffff';
    ctx.fillText(timeText, pad + 9, pad + 6);

    // Skip legend for the material layer (no scalar colorbar)
    if (activeScalar === 'material') return;

    const label = SCALAR_LABELS[activeScalar] ?? activeScalar;
    const barW = Math.min(320, w - pad * 2);
    const barH = 18;
    const bx = w - barW - pad;
    const by = h - 60;

    // Colormap gradient
    const stops = COLORMAP_STOPS[colormap] ?? COLORMAP_STOPS.viridis;
    const grad = ctx.createLinearGradient(bx, by, bx + barW, by);
    for (const [t, color] of stops) grad.addColorStop(t, color);
    ctx.fillStyle = grad;
    ctx.fillRect(bx, by, barW, barH);

    // Border
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.85)';
    ctx.lineWidth = 2;
    ctx.strokeRect(bx, by, barW, barH);

    // Label and min/max values
    ctx.font = 'bold 14px sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.textBaseline = 'bottom';
    ctx.fillText(label, bx, by - 6);

    const fmt = (v) => {
      const t = Math.abs(v);
      if (t === 0) return '0';
      if (t < 1e-3 || t >= 1e3) return v.toExponential(2);
      return v.toFixed(3).replace(/\.?0+$/, '');
    };

    ctx.font = '13px sans-serif';
    ctx.textBaseline = 'top';
    ctx.fillText(fmt(scalarRange[0]), bx, by + barH + 4);
    const maxText = fmt(scalarRange[1]);
    const maxW = ctx.measureText(maxText).width;
    ctx.fillText(maxText, bx + barW - maxW, by + barH + 4);
  }

  _renderFilesPanel() {
    this.panelContent.innerHTML = `
      <section id="files-panel">
        <h3>Files</h3>
        <div class="btn-stack">
          <button class="btn" id="load-sim-data">Load simulation data</button>
          <button class="btn" id="load-sim">Load simulation</button>
        </div>
        <p class="hint">Select a JSON/CSV data file or a saved simulation checkpoint.</p>
        <input type="file" id="file-input" accept=".json,.csv,.h5,.npz,.vxs" style="display:none">
      </section>
    `;
    const fileInput = this.panelContent.querySelector('#file-input');
    this.panelContent.querySelector('#load-sim-data')?.addEventListener('click', () => {
      fileInput?.setAttribute('data-mode', 'data');
      fileInput?.click();
    });
    this.panelContent.querySelector('#load-sim')?.addEventListener('click', () => {
      fileInput?.setAttribute('data-mode', 'sim');
      fileInput?.click();
    });
    fileInput?.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const mode = fileInput.getAttribute('data-mode');
      if (mode === 'data') {
        this.ws.send({ cmd: 'load_simulation_data', filename: file.name });
      } else {
        this.ws.send({ cmd: 'load_simulation', filename: file.name });
      }
      alert(`Sent ${mode} load request for ${file.name}`);
    });
  }

  _bindTopNav() {
    this.root.querySelectorAll('.nav-item').forEach((btn) => {
      btn.addEventListener('click', () => this._openMenu(btn.dataset.menu));
    });
  }

  _bindViewportControls() {
    const gridBtn = this.root.querySelector('#toggle-grid');
    const axesBtn = this.root.querySelector('#toggle-axes');
    const orthoBtn = this.root.querySelector('#toggle-ortho');
    const resetBtn = this.root.querySelector('#camera-reset');
    gridBtn?.addEventListener('click', () => this.store.setShowGrid(!this.store.state.showGrid));
    axesBtn?.addEventListener('click', () => this.store.setShowAxes(!this.store.state.showAxes));
    orthoBtn?.addEventListener('click', () => {
      const ortho = this.scene.toggleOrthographic();
      this.store.setOrthographic(ortho);
      orthoBtn.classList.toggle('active', ortho);
    });
    resetBtn?.addEventListener('click', () => this.scene.resetCamera());
  }

  _bindViewportClick() {
    const viewport = this.root.querySelector('#viewport');
    if (!viewport) return;
    this._raycaster = new THREE.Raycaster();
    this._pointer = new THREE.Vector2();

    const ray = (e) => {
      const rect = viewport.getBoundingClientRect();
      this._pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      this._pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      this._raycaster.setFromCamera(this._pointer, this.scene.camera);
      return this._raycaster.intersectObject(this.scene.voxelMesh, false);
    };

    viewport.addEventListener('pointermove', (e) => {
      if (!this.scene?.voxelMesh) {
        this.store.setHoveredVoxel(null);
        this._updateProbe(null);
        return;
      }
      const hits = ray(e);
      if (hits.length > 0) {
        const id = hits[0].instanceId;
        if (this.store.state.inspectMode) {
          if (this.store.state.hoveredVoxel?.id !== id) {
            this.store.setHoveredVoxel({ id });
          }
        }
        this._updateProbe({ id, clientX: e.clientX, clientY: e.clientY });
      } else {
        this.store.setHoveredVoxel(null);
        this._updateProbe(null);
      }
    });

    viewport.addEventListener('pointerdown', (e) => {
      if (!this.store.state.inspectMode || !this.scene?.voxelMesh) return;
      const hits = ray(e);
      if (hits.length > 0) {
        const id = hits[0].instanceId;
        this.store.setInspectedVoxel({ id });
        this.inspectPanel.showVoxelInspector(id);
        this.store.setInspectMode(false);
        this.store.setHoveredVoxel(null);
      }
    });

    viewport.addEventListener('pointerleave', () => this.store.setHoveredVoxel(null));
  }

  _getVoxelCenter(id) {
    const mesh = this.scene?.voxelMesh;
    const voxels = mesh?.userData?.voxels;
    if (!voxels || id < 0 || id >= (voxels.count ?? 0)) return null;
    const positions = voxels.positions || [];
    const sizes = voxels.sizes || [];
    return {
      x: positions[id * 3] ?? 0,
      y: positions[id * 3 + 1] ?? 0,
      z: positions[id * 3 + 2] ?? 0,
      size: sizes[id] ?? 1.0,
    };
  }

  _updateProbe(pointer) {
    const tooltip = this.root.querySelector('#probe-tooltip');
    if (!tooltip) return;
    if (!pointer) {
      tooltip.style.display = 'none';
      return;
    }
    const v = this.scene.getVoxelValueAt(pointer.id);
    if (!v) {
      tooltip.style.display = 'none';
      return;
    }
    const mesh = this.scene.voxelMesh;
    const layer = mesh?.userData?.scalar_layer || 'material';
    const values = mesh?.userData?.scalar_values || [];
    let valueText = '';
    if (layer === 'material') {
      valueText = 'material';
    } else if (values.length > pointer.id) {
      const raw = values[pointer.id];
      const t = Math.abs(raw);
      const fmt = t === 0 ? '0' : (t < 1e-3 || t >= 1e3) ? raw.toExponential(2) : raw.toFixed(3).replace(/\.?0+$/, '');
      valueText = `${fmt} ${this._probeUnit(layer)}`;
    }
    tooltip.innerHTML = `
      <div class="probe-title">Voxel ${v.id}</div>
      <div class="probe-row">${valueText}</div>
      <div class="probe-coords">(${v.x.toExponential(1)}, ${v.y.toExponential(1)}, ${v.z.toExponential(1)})</div>
    `;
    tooltip.style.display = 'block';
    tooltip.style.left = `${pointer.clientX + 12}px`;
    tooltip.style.top = `${pointer.clientY + 12}px`;
  }

  _probeUnit(layer) {
    switch (layer) {
      case 'temperature': return 'K';
      case 'ion_concentration': return 'mol/m³';
      case 'effective_conductivity': return 'S/m';
      default: return '';
    }
  }

  _updateSelectionPreview(hovered) {
    const selected = this.store.state.inspectedVoxel;
    const previewId = hovered ? hovered.id : null;
    if (previewId !== null && previewId !== (selected?.id ?? -1)) {
      const c = this._getVoxelCenter(previewId);
      if (c) this.scene.setSelectionBox(new THREE.Vector3(c.x, c.y, c.z), c.size, 0xff3300, 'preview');
    } else {
      this.scene.removeSelectionBox('preview');
    }
    if (selected) {
      const c = this._getVoxelCenter(selected.id);
      if (c) this.scene.setSelectionBox(new THREE.Vector3(c.x, c.y, c.z), c.size, 0xff0000, 'selected');
    } else {
      this.scene.removeSelectionBox('selected');
    }
  }

  _updateSceneHelpers(showGrid, showAxes) {
    if (!this.scene) return;
    this.scene.showGrid(showGrid);
    this.scene.showAxes(showAxes);
  }


  _onStoreChange(state, patch) {
    // Send control commands to the server whenever relevant UI state changes.
    // UI re-renders live in the constructor subscription; this handler is strictly the server bridge.
    if (patch.playing !== undefined) {
      this.ws.send({ cmd: state.playing ? 'play' : 'pause' });
    }
    if (patch.activeScalar !== undefined) {
      for (const s of LAYERS.SCALAR) {
        this.ws.send({ cmd: 'set_layer', layer: s, active: s === state.activeScalar });
      }
    }
    if (patch.activeVectors !== undefined) {
      for (const v of LAYERS.VECTOR) {
        this.ws.send({ cmd: 'set_layer', layer: v, active: state.activeVectors.has(v) });
      }
    }
    if (patch.opacity !== undefined) {
      this.ws.send({ cmd: 'set_opacity', value: state.opacity });
    }
    if (patch.arrowScale !== undefined) {
      this.ws.send({ cmd: 'set_arrow_scale', value: state.arrowScale });
    }
    if (patch.stepsPerFrame !== undefined) {
      this.ws.send({ cmd: 'set_time_scale', value: state.stepsPerFrame });
    }
    if (patch.timeStep !== undefined) {
      this.ws.send({ cmd: 'set_time_step', value: state.timeStep });
    }
  }
}
