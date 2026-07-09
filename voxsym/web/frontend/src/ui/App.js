import * as THREE from 'three';
import { Scene } from '../scene/Scene.js';
import { Store, LAYERS } from '../store/Store.js';
import { WebSocketClient } from '../ws/WebSocketClient.js';
import { updateVoxels } from '../render/Voxels.js';
import { updateArrows } from '../render/Arrows.js';
import { LayersPanel } from './LayersPanel.js';
import { SettingsPanel } from './SettingsPanel.js';
import { InspectPanel } from './InspectPanel.js';
import './App.css';

function formatTime(seconds) {
  const t = Math.abs(seconds);
  if (t === 0) return 't = 0 s';
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
          <button class="nav-item" data-menu="inspect">Inspect</button>
          <button class="nav-item" data-menu="settings">Settings</button>
        </nav>
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
      </div>
    `;

    this.scene = new Scene(this.root.querySelector('#viewport'));

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
      if ((patch.recording !== undefined || patch.playing !== undefined) && this._currentMenu === 'simulation') {
        this._renderSimulationPanel();
      }
    });

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
      default:
        break;
    }
  }

  _renderSimulationPanel() {
    const isPlaying = this.store.state.playing;
    this.panelContent.innerHTML = `
      <section id="simulation-panel">
        <h3>Simulation</h3>
        <div class="btn-stack">
          <button class="btn primary" id="sim-play-pause">${isPlaying ? 'Pause' : 'Play'}</button>
          <button class="btn" id="sim-record">${this.store.state.recording ? 'Stop recording' : 'Record'}</button>
          <button class="btn" id="sim-restart">Restart</button>
        </div>
        <p class="hint">Status: <span id="sim-status">${isPlaying ? 'running' : 'paused'}</span></p>
      </section>
    `;
    this.panelContent.querySelector('#sim-play-pause')?.addEventListener('click', () => {
      const newState = !this.store.state.playing;
      this.store.setPlaying(newState);
    });
    this.panelContent.querySelector('#sim-record')?.addEventListener('click', () => this.store.setRecording(!this.store.state.recording));
    this.panelContent.querySelector('#sim-restart')?.addEventListener('click', () => this.ws.send({ cmd: 'restart' }));
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
    gridBtn?.addEventListener('click', () => this.store.setShowGrid(!this.store.state.showGrid));
    axesBtn?.addEventListener('click', () => this.store.setShowAxes(!this.store.state.showAxes));
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
      if (!this.store.state.inspectMode || !this.scene?.voxelMesh) {
        this.store.setHoveredVoxel(null);
        return;
      }
      const hits = ray(e);
      if (hits.length > 0) {
        const id = hits[0].instanceId;
        if (this.store.state.hoveredVoxel?.id !== id) {
          this.store.setHoveredVoxel({ id });
        }
      } else {
        this.store.setHoveredVoxel(null);
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
}
