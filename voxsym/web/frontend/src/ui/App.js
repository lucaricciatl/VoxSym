import { Scene } from '../scene/Scene.js';
import { Store, LAYERS } from '../store/Store.js';
import { WebSocketClient } from '../ws/WebSocketClient.js';
import { updateVoxels } from '../render/Voxels.js';
import { updateArrows } from '../render/Arrows.js';
import { LayersPanel } from './LayersPanel.js';
import { DisplayPanel } from './DisplayPanel.js';
import { SlicingPanel } from './SlicingPanel.js';
import './App.css';

export class App {
  constructor(root) {
    this.root = root;
    this.store = new Store();
    this.scene = null;
    this.ws = null;
  }

  mount() {
    this.root.innerHTML = `
      <header id="topbar"></header>
      <aside id="panel">
        <div id="layers-mount"></div>
        <div id="display-mount"></div>
        <div id="slicing-mount"></div>
      </aside>
      <div id="viewport"></div>
      <div id="status">disconnected</div>
    `;

    this.scene = new Scene(this.root.querySelector('#viewport'));

    this.ws = new WebSocketClient(this.store, (payload) => this.onFrame(payload));

    this.layersPanel = new LayersPanel(this.root.querySelector('#layers-mount'), this.store);
    this.displayPanel = new DisplayPanel(this.root.querySelector('#display-mount'), this.store, this.ws);
    this.slicingPanel = new SlicingPanel(this.root.querySelector('#slicing-mount'), this.store, this.ws);

    this.store.subscribe((state, patch) => this.onStoreChange(state, patch));

    this.layersPanel.render();
    this.displayPanel.render();
    this.slicingPanel.render();

    this.store.subscribe((state, patch) => {
      if (patch.connected !== undefined) {
        const el = this.root.querySelector('#status');
        if (el) el.textContent = state.connected ? 'connected' : 'disconnected';
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
    if (patch.crossSection !== undefined) {
      this.ws.send({ cmd: 'set_cross_section', axis: state.crossSection.axis, pos: state.crossSection.pos });
    }
    if (patch.arrowScale !== undefined) {
      this.ws.send({ cmd: 'set_arrow_scale', value: state.arrowScale });
    }
    if (patch.stepsPerFrame !== undefined) {
      this.ws.send({ cmd: 'set_time_scale', value: state.stepsPerFrame });
    }
  }
}
