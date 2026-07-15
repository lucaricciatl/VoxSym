export class SettingsPanel {
  constructor(container, store, ws) {
    this.container = container;
    this.store = store;
    this.ws = ws;
    this.store.subscribe((state, patch) => {
      if (patch.stepsPerFrame !== undefined) {
        this._updateSteps(state.stepsPerFrame);
        this._updateEmFieldPeriod(state.emFieldPeriod, state.stepsPerFrame);
      }
      if (patch.emFieldPeriod !== undefined) this._updateEmFieldPeriod(state.emFieldPeriod, state.stepsPerFrame);
      if (patch.arrowScale !== undefined) this._updateArrowScale(state.arrowScale);
      if (patch.timeStep !== undefined) {
        const el = this.container.querySelector('#dt-val');
        if (el) el.textContent = Number(state.timeStep).toExponential(2);
      }
      if (patch.shadowEnabled !== undefined) {
        const btn = this.container.querySelector('#toggle-shadows');
        if (btn) {
          btn.classList.toggle('active', state.shadowEnabled);
          btn.textContent = `Shadows: ${state.shadowEnabled ? 'on' : 'off'}`;
        }
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

  _updateArrowScale(value) {
    const input = this.container.querySelector('#arrow-scale');
    if (input && document.activeElement !== input) input.value = value;
    const val = this.container.querySelector('#arrow-scale-val');
    if (val) val.textContent = Number(value).toFixed(1);
  }

  _updateSteps(value) {
    const input = this.container.querySelector('#steps');
    if (input && document.activeElement !== input) input.value = value;
    const val = this.container.querySelector('#steps-val');
    if (val) val.textContent = String(value);
  }

  _updateEmFieldPeriod(value, steps) {
    const input = this.container.querySelector('#em-period');
    const max = Math.max(1, steps || 1);
    if (input) {
      input.max = max;
      if (document.activeElement !== input) input.value = Math.min(value, max);
    }
    const val = this.container.querySelector('#em-period-val');
    if (val) val.textContent = String(Math.min(value, max));
  }

  render() {
    const state = this.store.state;
    const emMax = Math.max(1, state.stepsPerFrame);
    const emVal = Math.min(state.emFieldPeriod, emMax);
    this.container.innerHTML = `
      <section id="settings-panel">
        <h3>Simulation settings</h3>
        <label>Steps/frame <span id="steps-val">${state.stepsPerFrame}</span>
          <input id="steps" type="range" min="1" max="200" step="1" value="${state.stepsPerFrame}">
        </label>
        <label>EM-field period <span id="em-period-val">${emVal}</span>
          <input id="em-period" type="range" min="1" max="${emMax}" step="1" value="${emVal}">
        </label>
        <p class="hint">Recompute Poisson/currents once every N sub-steps.</p>
        <label>Arrow scale <span id="arrow-scale-val">${Number(state.arrowScale).toFixed(1)}</span>
          <input id="arrow-scale" type="range" min="0.2" max="3.0" step="0.1" value="${state.arrowScale}">
        </label>
        <div class="btn-stack">
          <button class="btn ${state.shadowEnabled ? 'active' : ''}" id="toggle-shadows">Shadows: ${state.shadowEnabled ? 'on' : 'off'}</button>
          <button class="btn" id="sim-set-poisson">Poisson: ${state.poissonEnabled ? 'on' : 'off'}</button>
          <button class="btn" id="sim-set-heat">Heat: ${state.heatEnabled ? 'on' : 'off'}</button>
          <button class="btn" id="sim-set-electroneutrality">Electroneutrality: ${state.electroneutralityEnabled ? 'on' : 'off'}</button>
          <button class="btn" id="sim-set-bv">Butler–Volmer: ${state.bvEnabled ? 'on' : 'off'}</button>
          <button class="btn" id="sim-set-dl">Double-layer: ${state.dlEnabled ? 'on' : 'off'}</button>
        </div>
      </section>
    `;

    this.container.querySelector('#steps')?.addEventListener('input', (e) => {
      const v = parseInt(e.target.value, 10);
      this.store.setStepsPerFrame(v);
    });

    this.container.querySelector('#em-period')?.addEventListener('input', (e) => {
      const v = parseInt(e.target.value, 10);
      this.store.setEmFieldPeriod(v);
      this.ws.send({ cmd: 'set_em_field_period', value: v });
    });

    this.container.querySelector('#arrow-scale')?.addEventListener('input', (e) => {
      const v = parseFloat(e.target.value);
      this.store.setArrowScale(v);
      this.ws.send({ cmd: 'set_arrow_scale', value: v });
    });

    const toggles = [
      ['toggle-shadows', null, null],
      ['sim-set-poisson', 'poissonEnabled', 'set_poisson'],
      ['sim-set-heat', 'heatEnabled', 'set_heat'],
      ['sim-set-electroneutrality', 'electroneutralityEnabled', 'set_electroneutrality'],
      ['sim-set-bv', 'bvEnabled', 'set_butler_volmer'],
      ['sim-set-dl', 'dlEnabled', 'set_double_layer'],
    ];
    for (const [id, stateKey, cmd] of toggles) {
      this.container.querySelector(`#${id}`)?.addEventListener('click', () => {
        if (id === 'toggle-shadows') {
          this.store.setShadowEnabled(!this.store.state.shadowEnabled);
          return;
        }
        const next = !this.store.state[stateKey];
        this.store._setSimSetting(stateKey, next);
        this.ws.send({ cmd, active: next });
        this.render();
      });
    }
  }
}
