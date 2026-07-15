export const LAYERS = {
  SCALAR: ['temperature', 'ion_concentration', 'effective_conductivity', 'charge', 'material'],
  VECTOR: ['electric_field', 'magnetic_field', 'current'],
};

const SCALAR_LABELS = {
  temperature: 'Temperature',
  ion_concentration: 'Ion concentration',
  effective_conductivity: 'σ_eff',
  charge: 'Charge',
  material: 'Material',
};

const VECTOR_LABELS = {
  electric_field: 'Electric field',
  magnetic_field: 'Magnetic field',
  current: 'Current',
};

export { SCALAR_LABELS, VECTOR_LABELS };

export class Store {
  constructor() {
    this.state = {
      activeScalar: 'material',
      activeVectors: new Set(),
      opacity: 1.0,
      arrowScale: 0.8,
      stepsPerFrame: 1,
      emFieldPeriod: 1,
      timeStep: 1e-3,
      playing: false,
      recording: false,
      crossSection: { axis: 'off', pos: 0 },
      inspectMode: false,
      inspectedVoxel: null,
      hoveredVoxel: null,
      poissonEnabled: true,
      heatEnabled: false,
      electroneutralityEnabled: true,
      bvEnabled: false,
      dlEnabled: false,
      connected: false,
      time: 0,
      frame: 0,
      voxelCount: 0,
      arrowCount: 0,
      bbox: { x: [-1, 1], y: [-1, 1], z: [-1, 1] },
      showGrid: true,
      showAxes: true,
      scalarRange: [0, 1],
      colormap: 'viridis',
      scalarValues: [],
      orthographic: false,
      shadowEnabled: false,
      probe: null,
      toast: null,
    };
    this.listeners = new Set();
  }

  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  _notify(patch) {
    for (const fn of this.listeners) {
      try {
        fn(this.state, patch);
      } catch (err) {
        console.error('Store listener error:', err);
      }
    }
  }

  setActiveScalar(name) {
    if (this.state.activeScalar === name) return;
    this.state.activeScalar = name;
    this._notify({ activeScalar: name });
  }

  setVectorActive(name, active) {
    const was = this.state.activeVectors.has(name);
    if (active) this.state.activeVectors.add(name);
    else this.state.activeVectors.delete(name);
    if (was !== active) {
      this._notify({ activeVectors: new Set(this.state.activeVectors), [name]: active });
    }
  }

  setOpacity(value) {
    const v = Math.max(0, Math.min(1, parseFloat(value)));
    if (Number.isNaN(v) || this.state.opacity === v) return;
    this.state.opacity = v;
    this._notify({ opacity: v });
  }

  setArrowScale(value) {
    const v = parseFloat(value);
    if (Number.isNaN(v) || this.state.arrowScale === v) return;
    this.state.arrowScale = v;
    this._notify({ arrowScale: v });
  }

  setStepsPerFrame(value) {
    const v = parseInt(value, 10);
    if (Number.isNaN(v) || this.state.stepsPerFrame === v) return;
    this.state.stepsPerFrame = v;
    this._notify({ stepsPerFrame: v });
  }

  setEmFieldPeriod(value) {
    const v = Math.max(1, parseInt(value, 10));
    if (Number.isNaN(v) || this.state.emFieldPeriod === v) return;
    this.state.emFieldPeriod = v;
    this._notify({ emFieldPeriod: v });
  }

  setTimeStep(value) {
    const v = parseFloat(value);
    if (Number.isNaN(v) || v <= 0 || this.state.timeStep === v) return;
    this.state.timeStep = v;
    this._notify({ timeStep: v });
  }

  _setSimSetting(key, value) {
    if (this.state[key] === value) return;
    this.state[key] = value;
    this._notify({ [key]: value });
  }

  setCrossSection(axis, pos) {
    const v = { axis, pos: parseFloat(pos) || 0 };
    if (this.state.crossSection.axis === v.axis && this.state.crossSection.pos === v.pos) return;
    this.state.crossSection = v;
    this._notify({ crossSection: v });
  }

  setInspectMode(value) {
    if (this.state.inspectMode === value) return;
    this.state.inspectMode = value;
    this._notify({ inspectMode: value });
  }

  setInspectedVoxel(data) {
    this.state.inspectedVoxel = data;
    this._notify({ inspectedVoxel: data });
  }

  syncConfig(cfg) {
    const patch = {};
    const map = {
      time_step: 'timeStep',
      steps_per_frame: 'stepsPerFrame',
      em_field_period: 'emFieldPeriod',
      // Do not sync playing from config: the live frame payload already
      // carries the server's playing state, and overwriting the UI toggle
      // with a stale connect-time config causes play to immediately pause.
      poisson_enabled: 'poissonEnabled',
      heat_enabled: 'heatEnabled',
      electroneutrality_enabled: 'electroneutralityEnabled',
      butler_volmer_enabled: 'bvEnabled',
      double_layer_enabled: 'dlEnabled',
      arrow_scale: 'arrowScale',
    };
    for (const [k, v] of Object.entries(map)) {
      if (cfg[k] !== undefined && this.state[v] !== cfg[k]) {
        this.state[v] = cfg[k];
        patch[v] = cfg[k];
      }
    }
    if (Object.keys(patch).length) this._notify(patch);
  }

  setActiveLayersRemote(layers) {
    const scalar = layers.find((l) => LAYERS.SCALAR.includes(l)) || 'material';
    const vectors = new Set(layers.filter((l) => LAYERS.VECTOR.includes(l)));
    let changed = false;
    if (this.state.activeScalar !== scalar) {
      this.state.activeScalar = scalar;
      changed = true;
    }
    if (this.state.activeVectors.size !== vectors.size || [...vectors].some((v) => !this.state.activeVectors.has(v))) {
      this.state.activeVectors = vectors;
      changed = true;
    }
    if (changed) this._notify({ activeScalar: scalar, activeVectors: new Set(vectors), remote: true });
  }

  setActiveScalarRemote(name) {
    this.setActiveScalar(name);
  }

  setOpacityRemote(value) {
    const v = Math.max(0, Math.min(1, parseFloat(value)));
    if (Number.isNaN(v) || this.state.opacity === v) return;
    this.state.opacity = v;
    this._notify({ opacity: v, remote: true });
  }

  setArrowScaleRemote(value) {
    const v = parseFloat(value);
    if (Number.isNaN(v) || this.state.arrowScale === v) return;
    this.state.arrowScale = v;
    this._notify({ arrowScale: v, remote: true });
  }

  setTimeStepRemote(value) {
    const v = parseFloat(value);
    if (Number.isNaN(v) || v <= 0 || this.state.timeStep === v) return;
    this.state.timeStep = v;
    this._notify({ timeStep: v, remote: true });
  }

  setStepsPerFrameRemote(value) {
    const v = parseInt(value, 10);
    if (Number.isNaN(v) || this.state.stepsPerFrame === v) return;
    this.state.stepsPerFrame = v;
    this._notify({ stepsPerFrame: v, remote: true });
  }

  setEmFieldPeriodRemote(value) {
    const v = Math.max(1, parseInt(value, 10));
    if (Number.isNaN(v) || this.state.emFieldPeriod === v) return;
    this.state.emFieldPeriod = v;
    this._notify({ emFieldPeriod: v, remote: true });
  }

  setTimeRemote(value) {
    const v = parseFloat(value);
    if (Number.isNaN(v) || this.state.time === v) return;
    this.state.time = v;
    this._notify({ time: v, remote: true });
  }

  setCrossSectionRemote(axis, pos) {
    const v = { axis, pos: parseFloat(pos) || 0 };
    if (this.state.crossSection.axis === v.axis && this.state.crossSection.pos === v.pos) return;
    this.state.crossSection = v;
    this._notify({ crossSection: v, remote: true });
  }

  setSimSettingRemote(key, value) {
    if (this.state[key] === value) return;
    this.state[key] = value;
    this._notify({ [key]: value, remote: true });
  }

  setHoveredVoxel(data) {
    if (this.state.hoveredVoxel === data || (this.state.hoveredVoxel && data && this.state.hoveredVoxel.id === data.id)) return;
    this.state.hoveredVoxel = data;
    this._notify({ hoveredVoxel: data });
  }

  setPlaying(value) {
    if (this.state.playing === value) return;
    this.state.playing = value;
    this._notify({ playing: value });
  }

  setPlayingRemote(value) {
    if (this.state.playing === value) return;
    this.state.playing = value;
    this._notify({ playing: value, remote: true });
  }

  setRecording(value) {
    if (this.state.recording === value) return;
    this.state.recording = value;
    this._notify({ recording: value });
  }

  setConnected(value) {
    this.state.connected = value;
    this._notify({ connected: value });
  }

  setShowGrid(value) {
    if (this.state.showGrid === value) return;
    this.state.showGrid = value;
    this._notify({ showGrid: value });
  }

  setShowAxes(value) {
    if (this.state.showAxes === value) return;
    this.state.showAxes = value;
    this._notify({ showAxes: value });
  }

  setOrthographic(value) {
    if (this.state.orthographic === value) return;
    this.state.orthographic = value;
    this._notify({ orthographic: value });
  }

  setShadowEnabled(value) {
    const v = Boolean(value);
    if (this.state.shadowEnabled === v) return;
    this._userTouchedShadow = true;
    this.state.shadowEnabled = v;
    this._notify({ shadowEnabled: v });
  }

  setProbe(data) {
    const same = this.state.probe && data && this.state.probe.id === data.id;
    if (same) return;
    this.state.probe = data;
    this._notify({ probe: data });
  }

  addToast(data) {
    if (!data || !data.message) return;
    const toast = { kind: data.kind || 'info', message: data.message };
    window.__addToastCalled = (window.__addToastCalled||0)+1;
    console.log('Store.addToast', toast);
    this.state.toast = toast;
    this._notify({ toast });
  }

  setFrameMeta({ time, frame, voxelCount, arrowCount }) {
    const firstFrame = this.state.frame === 0 && frame > 0;
    Object.assign(this.state, { time, frame, voxelCount, arrowCount });
    this._notify({ time, frame, voxelCount, arrowCount });
    // Default shadows off for large grids to stay GPU-friendly.
    if (firstFrame && voxelCount > 1000 && !this._userTouchedShadow) {
      this.state.shadowEnabled = false;
      this._notify({ shadowEnabled: false });
    }
  }

  setScalarMeta({ scalarRange, colormap, scalarValues }) {
    let changed = false;
    if (scalarRange !== undefined) {
      const lo = parseFloat(scalarRange[0]);
      const hi = parseFloat(scalarRange[1]);
      if (!Number.isNaN(lo) && !Number.isNaN(hi) && (this.state.scalarRange[0] !== lo || this.state.scalarRange[1] !== hi)) {
        this.state.scalarRange = [lo, hi];
        changed = true;
      }
    }
    if (colormap !== undefined && this.state.colormap !== colormap) {
      this.state.colormap = colormap;
      changed = true;
    }
    if (scalarValues !== undefined) {
      this.state.scalarValues = scalarValues;
      changed = true;
    }
    if (changed) this._notify({ scalarRange: this.state.scalarRange, colormap: this.state.colormap, scalarValues: this.state.scalarValues });
  }

  setBBox(bbox) {
    this.state.bbox = bbox;
    this._notify({ bbox });
  }

  getActiveLayers() {
    const layers = [this.state.activeScalar];
    for (const v of this.state.activeVectors) layers.push(v);
    return layers;
  }
}
