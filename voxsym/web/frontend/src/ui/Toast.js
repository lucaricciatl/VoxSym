export class Toast {
  constructor(root) {
    this.root = root;
    this.el = document.createElement('div');
    this.el.className = 'toast-container';
    this.el.setAttribute('aria-live', 'polite');
    this.root.appendChild(this.el);
    this._timers = new Map();
  }

  show(message, type = 'info', duration = 3000) {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const item = document.createElement('div');
    item.className = `toast toast-${type}`;
    item.id = id;
    item.innerHTML = `
      <span class="toast-message">${this._escape(message)}</span>
      <button class="toast-close" aria-label="Dismiss">×</button>
    `;
    item.querySelector('.toast-close')?.addEventListener('click', () => this.dismiss(id));
    this.el.appendChild(item);

    if (duration > 0) {
      const timer = setTimeout(() => this.dismiss(id), duration);
      this._timers.set(id, timer);
    }
    return id;
  }

  success(message, duration) { return this.show(message, 'success', duration); }
  error(message, duration = 5000) { return this.show(message, 'error', duration); }
  warn(message, duration) { return this.show(message, 'warn', duration); }

  dismiss(id) {
    const item = this.el.querySelector(`#${id}`);
    if (!item) return;
    item.classList.add('toast-exit');
    item.addEventListener('transitionend', () => {
      if (item.parentNode === this.el) this.el.removeChild(item);
    });
    const timer = this._timers.get(id);
    if (timer) clearTimeout(timer);
    this._timers.delete(id);
  }

  _escape(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }
}
