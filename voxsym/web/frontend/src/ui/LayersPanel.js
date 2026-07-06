import { LAYERS, SCALAR_LABELS, VECTOR_LABELS } from '../store/Store.js';

export class LayersPanel {
  constructor(container, store) {
    this.container = container;
    this.store = store;
    this.store.subscribe((state, patch) => {
      if (patch.activeScalar !== undefined || patch.activeVectors !== undefined) {
        this.render();
      }
      if (patch.voxelCount !== undefined) {
        const el = this.container.querySelector('#voxel-count');
        if (el) el.textContent = String(state.voxelCount);
      }
      if (patch.arrowCount !== undefined) {
        const el = this.container.querySelector('#arrow-count');
        if (el) el.textContent = String(state.arrowCount);
      }
    });
  }

  render() {
    const scalarCards = LAYERS.SCALAR.map((id) => {
      const active = this.store.state.activeScalar === id ? 'active' : '';
      return `<button class="layer-card ${active}" data-scalar="${id}">${SCALAR_LABELS[id]}</button>`;
    }).join('');

    const vectorChips = LAYERS.VECTOR.map((id) => {
      const active = this.store.state.activeVectors.has(id) ? 'active' : '';
      return `<label class="chip ${active}" data-vector="${id}"><input type="checkbox" ${active ? 'checked' : ''}> ${VECTOR_LABELS[id]}</label>`;
    }).join('');

    const mount = this.container;
    mount.innerHTML = `
      <section id="layers-panel">
        <h3>Scalar layer</h3>
        ${scalarCards}
        <h3>Vector overlays</h3>
        ${vectorChips}
        <p>voxels: <span id="voxel-count">${this.store.state.voxelCount}</span></p>
        <p>arrows: <span id="arrow-count">${this.store.state.arrowCount}</span></p>
      </section>
    `;

    this.container.querySelectorAll('[data-scalar]').forEach((btn) => {
      btn.addEventListener('click', () => this.store.setActiveScalar(btn.dataset.scalar));
    });
    this.container.querySelectorAll('[data-vector] input').forEach((cb) => {
      cb.addEventListener('change', () => this.store.setVectorActive(cb.closest('[data-vector]').dataset.vector, cb.checked));
    });
  }
}
