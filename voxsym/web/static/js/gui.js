import { sendCommand } from './websocket.js?v=1';

const SCALAR_LAYERS = [
  { id: 'voxel_color', label: 'Base color', icon: '🧊' },
  { id: 'temperature', label: 'Temperature', icon: '🌡️' },
  { id: 'ion_concentration', label: 'Ion concentration', icon: '⚡' },
  { id: 'material', label: 'Material', icon: '🧪' },
];

const VECTOR_LAYERS = [
  { id: 'electric_field', label: 'Electric field', icon: '⚡' },
  { id: 'magnetic_field', label: 'Magnetic field', icon: '🧲' },
  { id: 'current', label: 'Current', icon: '➡️' },
];

const DEFAULT_SCALAR = 'voxel_color';

function ws() {
  if (window.voxsym?.getWs) {
    return window.voxsym.getWs();
  }
  return window.voxsym?.ws ?? null;
}

function emit(cmd) {
  const socket = ws();
  sendCommand(socket, cmd);
}

function renderLayersPanel(activeScalar = DEFAULT_SCALAR, activeVectors = []) {
  const scalarCards = SCALAR_LAYERS.map((layer) => {
    const activeClass = layer.id === activeScalar ? 'active' : '';
    return `<button class="layer-card ${activeClass}" data-scalar="${layer.id}">
      <span>${layer.icon}</span> ${layer.label}
    </button>`;
  }).join('');

  const vectorChips = VECTOR_LAYERS.map((layer) => {
    const isActive = activeVectors.includes(layer.id);
    return `<label class="chip ${isActive ? 'active' : ''}" data-vector-chip="${layer.id}">
      <input type="checkbox" data-vector="${layer.id}" ${isActive ? 'checked' : ''}>
      <span>${layer.icon} ${layer.label}</span>
    </label>`;
  }).join('');

  return `
    <button class="panel-close" aria-label="Close panel">✕</button>
    <section>
      <h3>Scalar layer</h3>
      <div class="layer-grid">${scalarCards}</div>
    </section>
    <section>
      <h3>Vector overlays</h3>
      <div class="toggle-row">${vectorChips}</div>
    </section>
    <section>
      <h3>Counts</h3>
      <p>voxels: <span id="voxel-count">0</span></p>
      <p>arrows: <span id="arrow-count">0</span></p>
    </section>
  `;
}

function renderDisplayPanel(opacity = 1.0, arrowScale = 0.8, timeScale = 1) {
  return `
    <button class="panel-close" aria-label="Close panel">✕</button>
    <section>
      <h3>Display</h3>
      <label>Opacity <span id="opacity-val">${Number(opacity).toFixed(2)}</span>
        <input id="opacity" type="range" min="0" max="1" step="0.01" value="${opacity}">
      </label>
      <label>Arrow scale <span id="arrow-scale-val">${Number(arrowScale).toFixed(2)}</span>
        <input id="arrow-scale" type="range" min="0.1" max="3.0" step="0.05" value="${arrowScale}">
      </label>
      <label>Steps/frame <span id="time-scale-val">${timeScale}</span>
        <input id="time-scale" type="range" min="1" max="200" step="1" value="${timeScale}">
      </label>
    </section>
  `;
}

function renderSlicingPanel(axis = 'off', pos = 0) {
  return `
    <button class="panel-close" aria-label="Close panel">✕</button>
    <section>
      <h3>Cross Section</h3>
      <label>Axis
        <select id="cs-axis">
          <option value="off" ${axis === 'off' ? 'selected' : ''}>off</option>
          <option value="x" ${axis === 'x' ? 'selected' : ''}>x</option>
          <option value="y" ${axis === 'y' ? 'selected' : ''}>y</option>
          <option value="z" ${axis === 'z' ? 'selected' : ''}>z</option>
        </select>
      </label>
      <label>Position <span id="cs-pos-val">${Number(pos).toFixed(2)}</span>
        <input id="cs-pos" type="range" min="-10" max="10" step="0.05" value="${pos}">
      </label>
    </section>
  `;
}

function renderRecordingPanel() {
  return `
    <button class="panel-close" aria-label="Close panel">✕</button>
    <section>
      <h3>Recording</h3>
      <p>Use the ● button in the top bar to capture the canvas to a WebM video.</p>
      <div id="upload-zone" class="upload-zone">
        Drop .npz / .csv here or click to browse
        <input id="file-input" type="file" accept=".npz,.csv">
      </div>
      <div id="timeline-wrap" class="timeline-wrap hidden">
        <label>Frame <span id="frame-val">0</span> / <span id="frame-total">0</span>
          <input id="timeline" type="range" min="0" max="0" step="1" value="0">
        </label>
        <div class="btn-row">
          <button id="pb-play">▶</button>
          <button id="pb-pause">⏸</button>
        </div>
      </div>
    </section>
  `;
}

const PANELS = {
  layers: renderLayersPanel,
  display: renderDisplayPanel,
  slicing: renderSlicingPanel,
  recording: renderRecordingPanel,
};

let currentPanel = 'layers';
let cachedState = {
  activeScalar: DEFAULT_SCALAR,
  activeVectors: [],
  opacity: 1.0,
  arrowScale: 0.8,
  timeScale: 1,
  csAxis: 'off',
  csPos: 0,
};

export function renderPanel(name, sidePanel) {
  const renderer = PANELS[name] || renderLayersPanel;
  if (name === 'layers') {
    sidePanel.innerHTML = renderer(cachedState.activeScalar, cachedState.activeVectors);
  } else if (name === 'display') {
    sidePanel.innerHTML = renderer(cachedState.opacity, cachedState.arrowScale, cachedState.timeScale);
  } else if (name === 'slicing') {
    sidePanel.innerHTML = renderer(cachedState.csAxis, cachedState.csPos);
  } else {
    sidePanel.innerHTML = renderer();
  }
  currentPanel = name;
}

export function bindPanelEvents() {
  const sidePanel = document.getElementById('side-panel');

  sidePanel?.querySelectorAll('.panel-close').forEach((btn) => {
    btn.addEventListener('click', () => {
      sidePanel.classList.remove('open');
      document.querySelectorAll('#iconbar button').forEach((b) => b.classList.remove('active'));
    });
  });

  sidePanel?.querySelectorAll('[data-scalar]').forEach((card) => {
    card.addEventListener('click', () => {
      const layer = card.dataset.scalar;
      if (layer === cachedState.activeScalar) return;
      cachedState.activeScalar = layer;
      sidePanel.querySelectorAll('[data-scalar]').forEach((c) => c.classList.remove('active'));
      card.classList.add('active');
      // Disable all other scalar layers and enable selected one.
      SCALAR_LAYERS.forEach((l) => {
        if (l.id === layer) {
          emit({ cmd: 'set_layer', layer: l.id, active: true });
        } else {
          emit({ cmd: 'set_layer', layer: l.id, active: false });
        }
      });
    });
  });

  sidePanel?.querySelectorAll('input[data-vector]').forEach((cb) => {
    cb.addEventListener('change', () => {
      const layer = cb.dataset.vector;
      const active = cb.checked;
      emit({ cmd: 'set_layer', layer, active });
      const chip = cb.closest('[data-vector-chip]');
      if (chip) chip.classList.toggle('active', active);
      if (active) {
        cachedState.activeVectors = [...new Set([...cachedState.activeVectors, layer])];
      } else {
        cachedState.activeVectors = cachedState.activeVectors.filter((l) => l !== layer);
      }
    });
  });

  const opacityInput = document.getElementById('opacity');
  opacityInput?.addEventListener('input', () => {
    const value = parseFloat(opacityInput.value);
    cachedState.opacity = value;
    const opacityVal = document.getElementById('opacity-val');
    if (opacityVal) opacityVal.textContent = value.toFixed(2);
    emit({ cmd: 'set_opacity', value });
  });

  const arrowScaleInput = document.getElementById('arrow-scale');
  arrowScaleInput?.addEventListener('input', () => {
    const value = parseFloat(arrowScaleInput.value);
    cachedState.arrowScale = value;
    const arrowScaleVal = document.getElementById('arrow-scale-val');
    if (arrowScaleVal) arrowScaleVal.textContent = value.toFixed(2);
    emit({ cmd: 'set_arrow_scale', value });
  });

  const timeScaleInput = document.getElementById('time-scale');
  timeScaleInput?.addEventListener('input', () => {
    const value = parseInt(timeScaleInput.value, 10);
    cachedState.timeScale = value;
    const timeScaleVal = document.getElementById('time-scale-val');
    if (timeScaleVal) timeScaleVal.textContent = String(value);
    emit({ cmd: 'set_time_scale', value });
  });

  const csAxis = document.getElementById('cs-axis');
  const csPos = document.getElementById('cs-pos');
  const csPosVal = document.getElementById('cs-pos-val');

  function updateCrossSection() {
    const axis = csAxis?.value ?? 'off';
    const pos = parseFloat(csPos?.value ?? '0');
    cachedState.csAxis = axis;
    cachedState.csPos = pos;
    if (csPosVal) csPosVal.textContent = pos.toFixed(2);
    emit({ cmd: 'set_cross_section', axis, pos });
  }

  csAxis?.addEventListener('change', updateCrossSection);
  csPos?.addEventListener('input', updateCrossSection);
}

export function initGui(getWs) {
  const sidePanel = document.getElementById('side-panel');
  const status = document.getElementById('status');

  if (typeof getWs === 'function') {
    window.voxsym = window.voxsym || {};
    window.voxsym.getWs = getWs;
  }

  // Render the initial panel so layers are visible without needing to click the iconbar.
  renderPanel('layers', sidePanel);
  bindPanelEvents();

  document.querySelectorAll('#iconbar button[data-panel]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const panel = btn.dataset.panel;
      const isSame = currentPanel === panel && sidePanel.classList.contains('open');
      document.querySelectorAll('#iconbar button').forEach((b) => b.classList.remove('active'));

      if (window.innerWidth <= 700 && isSame) {
        sidePanel.classList.remove('open');
        return;
      }

      btn.classList.add('active');
      sidePanel.classList.add('open');
      renderPanel(panel, sidePanel);
      bindPanelEvents();
    });
  });

  return {
    setStatus(text) {
      if (status) status.textContent = text;
    },
    setVoxelCount(n) {
      const el = document.getElementById('voxel-count');
      if (el) el.textContent = String(n);
    },
    setArrowCount(n) {
      const el = document.getElementById('arrow-count');
      if (el) el.textContent = String(n);
    },
    syncActiveLayers(activeLayers) {
      if (!Array.isArray(activeLayers)) return;
      cachedState.activeScalar = SCALAR_LAYERS.find((l) => activeLayers.includes(l.id))?.id || DEFAULT_SCALAR;
      cachedState.activeVectors = VECTOR_LAYERS.filter((l) => activeLayers.includes(l.id)).map((l) => l.id);
      // If currently visible, refresh selection highlights.
      if (currentPanel === 'layers') {
        renderPanel('layers', sidePanel);
        bindPanelEvents();
      }
    },
    syncStateFromPayload(payload) {
      if (payload.opacity !== undefined) cachedState.opacity = Number(payload.opacity);
      if (payload.time_scale !== undefined) cachedState.timeScale = Number(payload.time_scale);
      if (payload.arrow_scale !== undefined) cachedState.arrowScale = Number(payload.arrow_scale);
      if (payload.cross_section) {
        cachedState.csAxis = payload.cross_section.axis ?? cachedState.csAxis;
        cachedState.csPos = payload.cross_section.pos ?? cachedState.csPos;
      }
    },
    getTimelineElements() {
      return {
        timeline: document.getElementById('timeline'),
        frameVal: document.getElementById('frame-val'),
        frameTotal: document.getElementById('frame-total'),
        pbPlay: document.getElementById('pb-play'),
        pbPause: document.getElementById('pb-pause'),
        timelineWrap: document.getElementById('timeline-wrap'),
      };
    },
    getUploadElements() {
      return {
        uploadZone: document.getElementById('upload-zone'),
        fileInput: document.getElementById('file-input'),
      };
    },
    getSidePanel() {
      return sidePanel;
    },
  };
}
