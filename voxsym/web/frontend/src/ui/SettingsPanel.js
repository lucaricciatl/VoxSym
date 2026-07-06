export class SettingsPanel {
  constructor(container, store) {
    this.container = container;
    this.store = store;
    this.store.subscribe((state, patch) => {
      if (patch.arrowScale !== undefined) this._updateArrowScale(state.arrowScale);
      if (patch.stepsPerFrame !== undefined) this._updateSteps(state.stepsPerFrame);
    });
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
    this.container.innerHTML = `
      <section id="settings-panel">
        <h3>Settings</h3>
        <label>Arrow scale <span id="arrow-scale-val">${this.store.state.arrowScale.toFixed(2)}</span>
          <input id="arrow-scale" type="range" min="0.1" max="3" step="0.05" value="${this.store.state.arrowScale}">
        </label>
        <label>Steps/frame <span id="steps-val">${this.store.state.stepsPerFrame}</span>
          <input id="steps" type="range" min="1" max="200" step="1" value="${this.store.state.stepsPerFrame}">
        </label>
        <p class="hint">Cross-section slicing is planned for a future release.</p>
      </section>
    `;

    this.container.querySelector('#arrow-scale')?.addEventListener('input', (e) => {
      this.store.setArrowScale(e.target.value);
    });
    this.container.querySelector('#steps')?.addEventListener('input', (e) => {
      this.store.setStepsPerFrame(e.target.value);
    });
  }
}
