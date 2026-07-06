export const LAYERS = {
  SCALAR: ['voxel_color', 'temperature', 'ion_concentration', 'material'],
  VECTOR: ['electric_field', 'magnetic_field', 'current'],
};

const SCALAR_LABELS = {
  voxel_color: 'Base color',
  temperature: 'Temperature',
  ion_concentration: 'Ion concentration',
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
      activeScalar: 'voxel_color',
      activeVectors: new Set(),
      opacity: 1.0,
      arrowScale: 0.8,
      stepsPerFrame: 1,
      crossSection: { axis: 'off', pos: 0 },
      connected: false,
      time: 0,
      frame: 0,
      voxelCount: 0,
      arrowCount: 0,
    };
    this.listeners = new Set();
  }

  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  _notify(patch) {
    for (const fn of this.listeners) fn(this.state, patch);
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

  setCrossSection(axis, pos) {
    this.state.crossSection = { axis, pos };
    this._notify({ crossSection: this.state.crossSection });
  }

  setConnected(value) {
    this.state.connected = value;
    this._notify({ connected: value });
  }

  setFrameMeta({ time, frame, voxelCount, arrowCount }) {
    Object.assign(this.state, { time, frame, voxelCount, arrowCount });
    this._notify({ time, frame, voxelCount, arrowCount });
  }

  getActiveLayers() {
    const layers = [this.state.activeScalar];
    for (const v of this.state.activeVectors) layers.push(v);
    return layers;
  }
}
