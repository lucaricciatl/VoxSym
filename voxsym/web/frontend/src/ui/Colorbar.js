import { SCALAR_LABELS } from '../store/Store.js';

const STOPS = {
  viridis: [
    [0.00, '#440154'], [0.13, '#472878'], [0.25, '#3e4a89'], [0.38, '#31688e'],
    [0.50, '#26828e'], [0.63, '#1f9e89'], [0.75, '#35b779'], [0.88, '#6ece58'], [1.00, '#fde725'],
  ],
  plasma: [
    [0.00, '#0d0887'], [0.13, '#41049d'], [0.25, '#6a00a8'], [0.38, '#8f0da4'],
    [0.50, '#b12a90'], [0.63, '#cc4778'], [0.75, '#e16462'], [0.88, '#f2844b'], [1.00, '#f0f921'],
  ],
};

export class Colorbar {
  constructor(root, store) {
    this.root = root;
    this.store = store;
    this.el = document.createElement('div');
    this.el.className = 'colorbar';
    this.el.innerHTML = `
      <div class="colorbar-label"><span class="colorbar-name"></span></div>
      <canvas class="colorbar-gradient"></canvas>
      <div class="colorbar-ticks"><span class="colorbar-min">0</span><span class="colorbar-max">1</span></div>
    `;
    this.root.appendChild(this.el);
    this.canvas = this.el.querySelector('.colorbar-gradient');
    this.store.subscribe((state, patch) => {
      if (
        patch.scalarLayer !== undefined ||
        patch.scalarRange !== undefined ||
        patch.colormap !== undefined
      ) {
        this.render();
      }
    });
    window.addEventListener('resize', () => this.render());
  }

  render() {
    const { activeScalar, scalarRange, colormap } = this.store.state;
    this.el.style.display = activeScalar === 'material' ? 'none' : 'flex';
    const nameEl = this.el.querySelector('.colorbar-name');
    nameEl.textContent = SCALAR_LABELS[activeScalar] ?? activeScalar;
    const minEl = this.el.querySelector('.colorbar-min');
    const maxEl = this.el.querySelector('.colorbar-max');
    const [lo, hi] = scalarRange ?? [0, 1];
    minEl.textContent = this._fmt(lo);
    maxEl.textContent = this._fmt(hi);

    const dpr = window.devicePixelRatio || 1;
    const rect = this.el.getBoundingClientRect();
    const width = Math.max(120, Math.floor(rect.width - 24));
    const height = 12;
    this.canvas.width = width * dpr;
    this.canvas.height = height * dpr;
    this.canvas.style.width = `${width}px`;
    this.canvas.style.height = `${height}px`;
    const ctx = this.canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    const grad = ctx.createLinearGradient(0, 0, width, 0);
    const stops = STOPS[colormap] ?? STOPS.viridis;
    for (const [t, color] of stops) grad.addColorStop(t, color);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, width, height);
  }

  _fmt(v) {
    const t = Math.abs(v);
    if (t === 0) return '0';
    if (t < 1e-3 || t >= 1e3) return v.toExponential(2);
    return v.toFixed(3).replace(/\.?0+$/, '');
  }
}
