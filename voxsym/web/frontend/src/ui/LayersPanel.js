import { LAYERS, SCALAR_LABELS, VECTOR_LABELS } from '../store/Store.js';

export class LayersPanel {
  constructor(container, store) {
    this.container = container;
    this.store = store;
    this.store.subscribe((state, patch) => {
      if (patch.activeScalar !== undefined || patch.activeVectors !== undefined) {
        this._updateClasses();
      }
      if (patch.voxelCount !== undefined) {
        const el = this.container.querySelector('#voxel-count');
        if (el) el.textContent = String(state.voxelCount);
      }
      if (patch.arrowCount !== undefined) {
        const el = this.container.querySelector('#arrow-count');
        if (el) el.textContent = String(state.arrowCount);
      }
      if (patch.opacity !== undefined) {
        const input = this.container.querySelector('#opacity');
        if (input && document.activeElement !== input) input.value = state.opacity;
        const val = this.container.querySelector('#opacity-val');
        if (val) val.textContent = state.opacity.toFixed(2);
      }
    });
  }

  _updateClasses() {
    this.container.querySelectorAll('[data-scalar]').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.scalar === this.store.state.activeScalar);
    });
    this.container.querySelectorAll('[data-vector]').forEach((chip) => {
      const active = this.store.state.activeVectors.has(chip.dataset.vector);
      chip.classList.toggle('active', active);
      const cb = chip.querySelector('input');
      if (cb) cb.checked = active;
    });
  }

  renderLayers() {
    const scalarCards = LAYERS.SCALAR.map((id) => {
      const active = this.store.state.activeScalar === id ? 'active' : '';
      return `<button class="layer-card ${active}" data-scalar="${id}">
        <span class="layer-color ${id}"></span>
        ${SCALAR_LABELS[id]}
      </button>`;
    }).join('');

    this.container.innerHTML = `
      <section id="layers-panel">
        <h3>Layers & Opacity</h3>
        <label>Opacity <span id="opacity-val">${this.store.state.opacity.toFixed(2)}</span>
          <input id="opacity" type="range" min="0" max="1" step="0.01" value="${this.store.state.opacity}">
        </label>
        <div class="layer-list">${scalarCards}</div>
        <p>voxels: <span id="voxel-count">${this.store.state.voxelCount}</span> · arrows: <span id="arrow-count">${this.store.state.arrowCount}</span></p>
      </section>
    `;

    this.container.querySelector('#opacity')?.addEventListener('input', (e) => {
      this.store.setOpacity(e.target.value);
    });
    this.container.querySelectorAll('[data-scalar]').forEach((btn) => {
      btn.addEventListener('click', () => this.store.setActiveScalar(btn.dataset.scalar));
    });
  }

  renderFields() {
    const vectorChips = LAYERS.VECTOR.map((id) => {
      const active = this.store.state.activeVectors.has(id) ? 'active' : '';
      return `<label class="chip ${active}" data-vector="${id}">
        <input type="checkbox" ${active ? 'checked' : ''}>
        <span class="chip-dot ${id}"></span>
        ${VECTOR_LABELS[id]}
      </label>`;
    }).join('');

    this.container.innerHTML = `
      <section id="fields-panel">
        <h3>Vector fields</h3>
        <div class="chip-list">${vectorChips}</div>
        <p>arrows: <span id="arrow-count">${this.store.state.arrowCount}</span></p>
      </section>
    `;

    this.container.querySelectorAll('[data-vector] input').forEach((cb) => {
      cb.addEventListener('change', () => this.store.setVectorActive(cb.closest('[data-vector]').dataset.vector, cb.checked));
    });
  }
}
