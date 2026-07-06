export class WebSocketClient {
  constructor(store, onFrame) {
    this.store = store;
    this.onFrame = onFrame;
    this.ws = null;
    this.queue = [];
    this.closed = false;
    this._connect();
  }

  _connect() {
    if (this.closed) return;
    const url = new URL('/ws', window.location.href);
    url.protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.ws = new WebSocket(url.href);

    this.ws.addEventListener('open', () => {
      this.store.setConnected(true);
      this._flush();
    });

    this.ws.addEventListener('message', (ev) => {
      let data;
      try {
        data = JSON.parse(ev.data);
      } catch (err) {
        return;
      }
      if (this.onFrame) this.onFrame(data);
    });

    this.ws.addEventListener('close', () => {
      this.store.setConnected(false);
      setTimeout(() => this._connect(), 1500);
    });

    this.ws.addEventListener('error', () => {
      this.store.setConnected(false);
    });
  }

  _flush() {
    while (this.ws && this.ws.readyState === WebSocket.OPEN && this.queue.length) {
      this.ws.send(JSON.stringify(this.queue.shift()));
    }
  }

  send(cmd) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(cmd));
    } else {
      this.queue.push(cmd);
    }
  }
}
