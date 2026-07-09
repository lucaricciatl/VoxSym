export class SettingsPanel {
  constructor(container, store, ws) {
    this.container = container;
    this.store = store;
    this.ws = ws;
    this.store.subscribe((state, patch) => {
      if (patch.stepsPerFrame !== undefined) this._updateSteps(state.stepsPerFrame);
      if (patch.timeStep !== undefined) {
        const el = this.container.querySelector('#dt-val');
        if (el) el.textContent = Number(state.timeStep).toExponential(2);
      }
      const boolKeys = ['poissonEnabled','heatEnabled','electroneutralityEnabled','bvEnabled','dlEnabled'];
      const ids = ['sim-set-poisson','sim-set-heat','sim-set-electroneutrality','sim-set-bv','sim-set-dl'];
      for (let i = 0; i < boolKeys.length; i++) {
        if (patch[boolKeys[i]] !== undefined) {
          const btn = this.container.querySelector(`#${ids[i]}`);
          if (btn) btn.textContent = btn.textContent.split(':')[0] + ': ' + (state[boolKeys[i]] ? 'on' : 'off');
        }
      }
    });
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
        <h3>Simulation settings</h3>
        <label>Steps/frame <span id="steps-val">${this.store.state.stepsPerFrame}</span>
          <input id="steps" type="range" min="1" max="200" step="1" value="${this.store.state.stepsPerFrame}">
        </label>
        <div class="btn-stack">
          <button class="btn" id="sim-set-poisson">Poisson: ${this.store.state.poissonEnabled ? 'on' : 'off'}</button>
          <button class="btn" id="sim-set-heat">Heat: ${this.store.state.heatEnabled ? 'on' : 'off'}</button>
          <button class="btn" id="sim-set-electroneutrality">Electroneutrality: ${this.store.state.electroneutralityEnabled ? 'on' : 'off'}</button>
          <button class="btn" id="sim-set-bv">Butler–Volmer: ${this.store.state.bvEnabled ? 'on' : 'off'}</button>
          <button class="btn" id="sim-set-dl">Double-layer: ${this.store.state.dlEnabled ? 'on' : 'off'}</button>
        </div>
      </section>
    `;

    this.container.querySelector('#steps')?.addEventListener('input', (e) => {
      const v = parseInt(e.target.value, 10);
      this.store.setStepsPerFrame(v);
    });

    const toggles = [
      ['sim-set-poisson', 'poissonEnabled', 'set_poisson'],
      ['sim-set-heat', 'heatEnabled', 'set_heat'],
      ['sim-set-electroneutrality', 'electroneutralityEnabled', 'set_electroneutrality'],
      ['sim-set-bv', 'bvEnabled', 'set_butler_volmer'],
      ['sim-set-dl', 'dlEnabled', 'set_double_layer'],
    ];
    for (const [id, stateKey, cmd] of toggles) {
      this.container.querySelector(`#${id}`)?.addEventListener('click', () => {
        const next = !this.store.state[stateKey];
        this.store._setSimSetting(stateKey, next);
        this.ws.send({ cmd, active: next });
        this.render();
      });
    }
  }
}
