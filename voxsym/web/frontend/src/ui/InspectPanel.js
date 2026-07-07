import { LAYERS } from '../store/Store.js';

export class InspectPanel {
  constructor(container, store, ws) {
    this.container = container;
    this.store = store;
    this.ws = ws;
    this.store.subscribe((state, patch) => {
      if (patch.crossSection !== undefined || patch.crossSectionPos !== undefined) {
        this._updateCrossSectionUI(state);
      }
      if (patch.inspectedVoxel !== undefined) {
        this._renderVoxelInspector(state.inspectedVoxel);
      }
    });
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
        <label>Position <span id="cs-pos-val">${this.store.state.crossSection.pos.toFixed(2)}</span>
          <input id="cs-pos" type="range" min="-100" max="100" step="0.5" value="${this.store.state.crossSection.pos}">
        </label>
      </section>
      <div id="voxel-inspector" class="overlay" style="display:none"></div>
    `;

    this.container.querySelector('#inspect-mode-toggle')?.addEventListener('click', () => {
      this.store.setInspectMode(!this.store.state.inspectMode);
      this.render();
    });

    const axisSel = this.container.querySelector('#cs-axis');
    axisSel?.addEventListener('change', (e) => {
      const axis = e.target.value;
      this.store.setCrossSection(axis, this.store.state.crossSection.pos);
      this.ws.send({ cmd: 'set_cross_section', axis, pos: this.store.state.crossSection.pos });
    });

    const posInput = this.container.querySelector('#cs-pos');
    posInput?.addEventListener('input', (e) => {
      const pos = parseFloat(e.target.value);
      this.store.setCrossSection(this.store.state.crossSection.axis, pos);
      this.ws.send({ cmd: 'set_cross_section', axis: this.store.state.crossSection.axis, pos });
    });
  }

  _updateCrossSectionUI(state) {
    const axisSel = this.container.querySelector('#cs-axis');
    const posInput = this.container.querySelector('#cs-pos');
    const posVal = this.container.querySelector('#cs-pos-val');
    if (axisSel) axisSel.value = state.crossSection.axis;
    if (posInput && document.activeElement !== posInput) posInput.value = state.crossSection.pos;
    if (posVal) posVal.textContent = state.crossSection.pos.toFixed(2);
  }

  showVoxelInspector(voxelId) {
    this.ws.send({ cmd: 'inspect_voxel', voxel_id: voxelId });
  }

  _renderVoxelInspector(data) {
    const overlay = this.container.querySelector('#voxel-inspector');
    if (!overlay) return;
    if (!data) {
      overlay.style.display = 'none';
      return;
    }
    overlay.style.display = 'block';
    const rows = Object.entries(data)
      .map(([k, v]) => `<tr><th>${k}</th><td>${Array.isArray(v) ? v.map(x => Number(x).toExponential(2)).join(', ') : (typeof v === 'number' ? Number(v).toExponential(2) : String(v))}</td></tr>`)
      .join('');
    overlay.innerHTML = `
      <div class="inspector-card">
        <h4>Voxel ${data.id ?? ''}</h4>
        <table>${rows}</table>
        <button class="btn" id="close-inspector">Close</button>
      </div>
    `;
    overlay.querySelector('#close-inspector')?.addEventListener('click', () => {
      this.store.setInspectedVoxel(null);
    });
  }
}
