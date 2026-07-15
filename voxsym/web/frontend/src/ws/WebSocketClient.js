import { LAYERS } from '../store/Store.js';

export class WebSocketClient {
  constructor(store, onFrame) {
    this.store = store;
    this.onFrame = onFrame;
    this.ws = null;
    this.queue = [];
    this.closed = false;
    this.lastFrame = null;
    this._connect();
  }

  _connect() {
    if (this.closed) return;
    const url = new URL('/ws', window.location.href);
    url.protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    console.log('[WS] connecting to', url.href);
    this.ws = new WebSocket(url.href);

    this.ws.addEventListener('open', () => {
      console.log('[WS] open');
      this.store.setConnected(true);
      this._flush();
    });

    this.ws.addEventListener('message', (ev) => {
      let data;
      try {
        data = JSON.parse(ev.data);
      } catch (err) {
        return;
      }
      if (data.type === 'voxel') {
        this.store.setInspectedVoxel(data.data);
      } else if (data.type === 'config') {
        this.store.syncConfig(data);
        // Sync default active layers from the config payload if present.
        if (Array.isArray(data.active_layers) && !this._initialSyncDone) {
          this._initialSyncDone = true;
          for (const layer of data.active_layers) {
            if (LAYERS.SCALAR.includes(layer)) {
              this.store.state.activeScalar = layer;
            }
          }
          const vectors = new Set();
          for (const layer of data.active_layers) {
            if (LAYERS.VECTOR.includes(layer)) {
              vectors.add(layer);
            }
          }
          this.store.state.activeVectors = vectors;
          this.store._notify({ activeScalar: this.store.state.activeScalar, activeVectors: new Set(vectors), remote: true });
        }
      } else if (data.type === 'toast') {
        console.log('[WS] toast', data); this.store.addToast(data);
      } else if (data.type === 'state') {
        // Authoritative real-time state update from the server; apply
        // immediately so the UI never flips back due to stale frames.
        // Use the remote setter so the UI does not echo the state back
        // as a new play/pause command.
        if (data.playing !== undefined) {
          this.store.setPlayingRemote(data.playing);
        }
        if (data.opacity !== undefined) {
          this.store.setOpacityRemote(data.opacity);
        }
        if (data.active_layers !== undefined) {
          this.store.setActiveLayersRemote(data.active_layers);
        }
        if (data.scalar_layer !== undefined) {
          this.store.setActiveScalarRemote(data.scalar_layer);
        }
        if (data.arrow_scale !== undefined) {
          this.store.setArrowScaleRemote(data.arrow_scale);
        }
        if (data.time_step !== undefined) {
          this.store.setTimeStepRemote(data.time_step);
        }
        if (data.steps_per_frame !== undefined) {
          this.store.setStepsPerFrameRemote(data.steps_per_frame);
        }
        if (data.em_field_period !== undefined) {
          this.store.setEmFieldPeriodRemote(data.em_field_period);
        }
        if (data.time !== undefined) {
          this.store.setTimeRemote(data.time);
        }
        if (data.cross_section !== undefined) {
          this.store.setCrossSectionRemote(data.cross_section.axis, data.cross_section.pos);
        }
        if (data.poisson_enabled !== undefined) {
          this.store.setSimSettingRemote('poissonEnabled', data.poisson_enabled);
        }
        if (data.heat_enabled !== undefined) {
          this.store.setSimSettingRemote('heatEnabled', data.heat_enabled);
        }
        if (data.electroneutrality_enabled !== undefined) {
          this.store.setSimSettingRemote('electroneutralityEnabled', data.electroneutrality_enabled);
        }
        if (data.butler_volmer_enabled !== undefined) {
          this.store.setSimSettingRemote('bvEnabled', data.butler_volmer_enabled);
        }
        if (data.double_layer_enabled !== undefined) {
          this.store.setSimSettingRemote('dlEnabled', data.double_layer_enabled);
        }
      } else if (this.onFrame) {
        if (data.type === 'frame') {
          // Merge incoming frame over cached frame so omitted metadata (from
          // deduplicated broadcasts) is still available.
          window.lastFrame = { ...(window.lastFrame || {}), ...data };
          this.onFrame(window.lastFrame);
        } else {
          this.onFrame(data);
        }
      }
    });

    this.ws.addEventListener('close', (ev) => {
      console.warn('[WS] close', ev.code, ev.reason);
      this.store.setConnected(false);
      setTimeout(() => this._connect(), 1500);
    });

    this.ws.addEventListener('error', (err) => {
      console.error('[WS] error', err);
      this.store.setConnected(false);
    });
  }

  _flush() {
    while (this.ws && this.ws.readyState === WebSocket.OPEN && this.queue.length) {
      this.ws.send(JSON.stringify(this.queue.shift()));
    }
  }

  send(cmd) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(cmd));
    } else {
      this.queue.push(cmd);
    }
  }
}
