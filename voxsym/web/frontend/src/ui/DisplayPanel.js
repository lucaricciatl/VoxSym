export class DisplayPanel {
  constructor(container, store, ws) {
    this.container = container;
    this.store = store;
    this.ws = ws;
    this.store.subscribe((state, patch) => {
      if (patch.opacity !== undefined) this._updateOpacity(state.opacity);
      if (patch.arrowScale !== undefined) this._updateArrowScale(state.arrowScale);
      if (patch.stepsPerFrame !== undefined) this._updateSteps(state.stepsPerFrame);
    });
  }

  _updateOpacity(value) {
    const input = this.container.querySelector('#opacity');
    if (input && document.activeElement !== input) input.value = value;
    const val = this.container.querySelector('#opacity-val');
    if (val) val.textContent = value.toFixed(2);
  }

  _updateArrowScale(value) {
    const input = this.container.querySelector('#arrow-scale');
    if (input && document.activeElement !== input) input.value = value;
    const val = this.container.querySelector('#arrow-scale-val');
    if (val) val.textContent = value.toFixed(2);
  }

  _updateSteps(value) {
    const input = this.container.querySelector('#steps');
    if (input && document.activeElement !== input) input.value = value;
    const val = this.container.querySelector('#steps-val');
    if (val) val.textContent = String(value);
  }

  render() {
    this.container.insertAdjacentHTML('beforeend', `
      <section id="display-panel">
        <h3>Display</h3>
        <label>Opacity <span id="opacity-val">${this.store.state.opacity.toFixed(2)}</span>
          <input id="opacity" type="range" min="0" max="1" step="0.01" value="${this.store.state.opacity}">
        </label>
        <label>Arrow scale <span id="arrow-scale-val">${this.store.state.arrowScale.toFixed(2)}</span>
          <input id="arrow-scale" type="range" min="0.1" max="3" step="0.05" value="${this.store.state.arrowScale}">
        </label>
        <label>Steps/frame <span id="steps-val">${this.store.state.stepsPerFrame}</span>
          <input id="steps" type="range" min="1" max="200" step="1" value="${this.store.state.stepsPerFrame}">
        </label>
      </section>
    `);

    this.container.querySelector('#opacity')?.addEventListener('input', (e) => {
      this.store.setOpacity(e.target.value);
    });
    this.container.querySelector('#arrow-scale')?.addEventListener('input', (e) => {
      this.store.setArrowScale(e.target.value);
    });
    this.container.querySelector('#steps')?.addEventListener('input', (e) => {
      this.store.setStepsPerFrame(e.target.value);
    });
  }
}
