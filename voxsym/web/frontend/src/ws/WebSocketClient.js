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
    console.log('[WS] connecting to', url.href);
    this.ws = new WebSocket(url.href);

    this.ws.addEventListener('open', () => {
      console.log('[WS] open');
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
      if (data.type === 'voxel') {
        this.store.setInspectedVoxel(data.data);
      } else if (this.onFrame) {
        this.onFrame(data);
      }
    });

    this.ws.addEventListener('close', (ev) => {
      console.warn('[WS] close', ev.code, ev.reason);
      this.store.setConnected(false);
      setTimeout(() => this._connect(), 1500);
    });

    this.ws.addEventListener('error', (err) => {
      console.error('[WS] error', err);
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
