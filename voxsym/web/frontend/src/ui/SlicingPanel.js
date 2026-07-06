export class SlicingPanel {
  constructor(container, store, ws) {
    this.container = container;
    this.store = store;
    this.ws = ws;
    this.store.subscribe((state, patch) => {
      if (patch.crossSection !== undefined) this._update(state.crossSection);
    });
  }

  _update({ axis, pos }) {
    const select = this.container.querySelector('#cs-axis');
    const range = this.container.querySelector('#cs-pos');
    const val = this.container.querySelector('#cs-pos-val');
    if (select && select.value !== axis) select.value = axis;
    if (range && range.value !== String(pos)) range.value = pos;
    if (val) val.textContent = Number(pos).toFixed(2);
  }

  render() {
    this.container.insertAdjacentHTML('beforeend', `
      <section id="slicing-panel">
        <h3>Cross Section</h3>
        <label>Axis
          <select id="cs-axis">
            <option value="off" selected>off</option>
            <option value="x">x</option>
            <option value="y">y</option>
            <option value="z">z</option>
          </select>
        </label>
        <label>Position <span id="cs-pos-val">0.00</span>
          <input id="cs-pos" type="range" min="-10" max="10" step="0.05" value="0">
        </label>
      </section>
    `);

    const onChange = () => {
      const axis = this.container.querySelector('#cs-axis')?.value ?? 'off';
      const pos = parseFloat(this.container.querySelector('#cs-pos')?.value ?? '0');
      this.store.setCrossSection(axis, pos);
    };

    this.container.querySelector('#cs-axis')?.addEventListener('change', onChange);
    this.container.querySelector('#cs-pos')?.addEventListener('input', onChange);
  }
}
