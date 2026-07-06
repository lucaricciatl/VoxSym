import { Scene } from '../scene/Scene.js';
import { Store, LAYERS } from '../store/Store.js';
import { WebSocketClient } from '../ws/WebSocketClient.js';
import { updateVoxels } from '../render/Voxels.js';
import { updateArrows } from '../render/Arrows.js';
import { LayersPanel } from './LayersPanel.js';
import { SettingsPanel } from './SettingsPanel.js';
import './App.css';

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
          <button class="nav-item" data-menu="files">Files</button>
          <button class="nav-item" data-menu="layers">Layers</button>
          <button class="nav-item" data-menu="fields">Fields</button>
          <button class="nav-item" data-menu="settings">Settings</button>
        </nav>
      </header>
      <aside id="panel">
        <div id="panel-content"></div>
      </aside>
      <div id="viewport"></div>
      <div id="status">disconnected</div>
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
    this.settingsPanel = new SettingsPanel(this.panelContent, this.store);

    this.store.subscribe((state, patch) => this.onStoreChange(state, patch));

    this._bindTopNav();
    this._bindViewportControls();

    // Default menu: layers
    this._openMenu('layers');

    this.store.subscribe((state, patch) => {
      if (patch.connected !== undefined) {
        const el = this.root.querySelector('#status');
        if (el) el.textContent = state.connected ? 'connected' : 'disconnected';
      }
      if (patch.showGrid !== undefined || patch.showAxes !== undefined) {
        this._updateSceneHelpers(state.showGrid, state.showAxes);
        const gridBtn = this.root.querySelector('#toggle-grid');
        const axesBtn = this.root.querySelector('#toggle-axes');
        gridBtn?.classList.toggle('active', state.showGrid);
        axesBtn?.classList.toggle('active', state.showAxes);
      }
    });

    window.voxsymApp = this;
  }

  onFrame(payload) {
    if (!payload || payload.type !== 'frame') return;
    updateVoxels(this.scene, payload);
    const arrowCount = updateArrows(this.scene, payload.arrows);
    this.store.setFrameMeta({
      time: payload.time ?? 0,
      frame: payload.frame_index ?? 0,
      voxelCount: payload.voxels?.count ?? 0,
      arrowCount,
    });
    if (payload.active_layers && Array.isArray(payload.active_layers)) {
      for (const layer of payload.active_layers) {
        if (LAYERS.SCALAR.includes(layer)) {
          this.store.state.activeScalar = layer;
          break;
        }
      }
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
    if (patch.showGrid !== undefined) {
      this._updateSceneHelpers(state.showGrid, state.showAxes);
    }
    if (patch.showAxes !== undefined) {
      this._updateSceneHelpers(state.showGrid, state.showAxes);
    }
  }

  _openMenu(menu) {
    this.panelContent.innerHTML = '';
    this.root.querySelectorAll('.nav-item').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.menu === menu);
    });
    switch (menu) {
      case 'layers':
      case 'fields':
        // Fields and layers both show the unified layers panel so users can
        // toggle scalar heatmaps and vector arrows from one place.
        this.layersPanel.render();
        break;
      case 'files':
        this.panelContent.innerHTML = `
          <section>
            <h3>Files</h3>
            <p>No file operations yet.</p>
          </section>
        `;
        break;
      case 'settings':
        this.settingsPanel.render();
        break;
      default:
        break;
    }
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

  _updateSceneHelpers(showGrid, showAxes) {
    if (!this.scene) return;
    this.scene.showGrid(showGrid);
    this.scene.showAxes(showAxes);
  }
}
