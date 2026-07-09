import { LAYERS } from '../store/Store.js';

export class InspectPanel {
  constructor(container, store, ws, overlayRoot) {
    this.container = container;
    this.store = store;
    this.ws = ws;
    this.overlayRoot = overlayRoot;
    this.store.subscribe((state, patch) => {
      if (patch.crossSection !== undefined || patch.crossSectionPos !== undefined) {
        this._updateCrossSectionUI(state);
      }
      if (patch.bbox !== undefined) {
        this._updateCrossSectionUI(state);
      }
      if (patch.inspectedVoxel !== undefined) {
        this._renderVoxelInspector(state.inspectedVoxel);
      }
    });
  }

  _axisRange(axis) {
    const bbox = this.store.state.bbox;
    const [lo, hi] = bbox[axis] || [-1, 1];
    return { min: lo, max: hi, step: Math.max(0.01, (hi - lo) / 200) };
  }

  render() {
    this.container.innerHTML = `
      <section id="inspect-panel">
        <h3>Inspect</h3>
        <div class="btn-stack">
          <button class="btn" id="inspect-mode-toggle">${this.store.state.inspectMode ? 'Exit inspect mode' : 'Inspect voxel'}</button>
        </div>
        <p class="hint">${this.store.state.inspectMode ? 'Click a voxel in the viewport to inspect its properties.' : ''}</p>

        <h3>Cross-section</h3>
        <label>Plane
          <select id="cs-axis">
            <option value="off" ${this.store.state.crossSection.axis === 'off' ? 'selected' : ''}>Off</option>
            <option value="x" ${this.store.state.crossSection.axis === 'x' ? 'selected' : ''}>X</option>
            <option value="y" ${this.store.state.crossSection.axis === 'y' ? 'selected' : ''}>Y</option>
            <option value="z" ${this.store.state.crossSection.axis === 'z' ? 'selected' : ''}>Z</option>
          </select>
        </label>
        <label id="cs-pos-label" style="display:${this.store.state.crossSection.axis === 'off' ? 'none' : 'block'}">Position <span id="cs-pos-val">${this.store.state.crossSection.pos.toExponential(2)}</span>
          <input id="cs-pos" type="range" min="0" max="1" step="0.01" value="0.5">
        </label>
      </section>
    `;

    this.container.querySelector('#inspect-mode-toggle')?.addEventListener('click', () => {
      this.store.setInspectMode(!this.store.state.inspectMode);
      this.render();
    });

    const axisSel = this.container.querySelector('#cs-axis');
    axisSel?.addEventListener('change', (e) => {
      const axis = e.target.value;
      let pos = this.store.state.crossSection.pos;
      if (axis !== 'off') {
        const { min, max } = this._axisRange(axis);
        pos = (min + max) / 2;
      }
      this.store.setCrossSection(axis, pos);
      this.ws.send({ cmd: 'set_cross_section', axis, pos });
    });

    const posInput = this.container.querySelector('#cs-pos');
    posInput?.addEventListener('input', (e) => {
      const axis = this.store.state.crossSection.axis;
      if (axis === 'off') return;
      const t = parseFloat(e.target.value);
      const { min, max } = this._axisRange(axis);
      const pos = min + t * (max - min);
      this.store.setCrossSection(axis, pos);
      this.ws.send({ cmd: 'set_cross_section', axis, pos });
    });
  }

  _updateCrossSectionUI(state) {
    const axisSel = this.container.querySelector('#cs-axis');
    const posInput = this.container.querySelector('#cs-pos');
    const posVal = this.container.querySelector('#cs-pos-val');
    const posLabel = this.container.querySelector('#cs-pos-label');
    const axis = state.crossSection.axis;
    if (axisSel) axisSel.value = axis;
    if (posLabel) posLabel.style.display = axis === 'off' ? 'none' : 'block';
    if (axis !== 'off') {
      const { min, max, step } = this._axisRange(axis);
      if (posInput) {
        posInput.min = min;
        posInput.max = max;
        posInput.step = step;
        if (document.activeElement !== posInput) {
          posInput.value = state.crossSection.pos;
        }
      }
    }
    if (posVal) posVal.textContent = state.crossSection.pos.toExponential(2);
  }

  showVoxelInspector(voxelId) {
    this.ws.send({ cmd: 'inspect_voxel', voxel_id: voxelId });
  }

  _renderVoxelInspector(data) {
    const overlay = this.overlayRoot;
    if (!overlay) return;
    if (!data) {
      overlay.style.display = 'none';
      return;
    }
    overlay.style.display = 'block';
    const fmt = (v) => {
      if (v === undefined || v === null) return '—';
      if (Array.isArray(v)) return v.map(x => typeof x === 'number' ? Number(x).toExponential(2) : String(x)).join(', ');
      if (typeof v === 'number') return Number(v).toExponential(3);
      return String(v);
    };
    const row = (k, v) => `<tr><th>${k}</th><td>${fmt(v)}</td></tr>`;
    const geometry = [
      row('index', data.index),
      row('x', data.x),
      row('y', data.y),
      row('z', data.z),
      row('size', data.size),
    ].join('');
    const material = [
      row('material', data.material),
      row('temperature [K]', data.temperature),
    ].join('');
    const ions = [
      row('H⁺ concentration', data.ion_concentration),
      row('anion concentration', data.anion_concentration),
      row('charge [C/m³]', data.charge),
      row('potential [V]', data.potential),
    ].join('');
    const fields = [
      row('E-field [V/m]', data.electric_field),
      row('B-field [T]', data.magnetic_field),
      row('current [A/m²]', data.current_density),
    ].join('');
    overlay.innerHTML = `
      <div class="inspector-card">
        <div class="inspector-header">
          <h4>Voxel ${data.id ?? ''}</h4>
          <span class="material-tag">${data.material ?? ''}</span>
        </div>
        <div class="inspector-body">
          <section><h5>Geometry</h5><table>${geometry}</table></section>
          <section><h5>Material</h5><table>${material}</table></section>
          <section><h5>Ions & Potential</h5><table>${ions}</table></section>
          <section><h5>Fields</h5><table>${fields}</table></section>
        </div>
        <div class="inspector-footer">
          <button class="btn" id="close-inspector">Close</button>
        </div>
      </div>
    `;
    overlay.querySelector('#close-inspector')?.addEventListener('click', () => {
      this.store.setInspectedVoxel(null);
    });
  }
}
