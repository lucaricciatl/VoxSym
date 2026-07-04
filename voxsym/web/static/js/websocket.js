// WebSocket connection helpers with auto-reconnect and command queuing.

export function connectWebSocket(url, onMessage, onStatus) {
  let ws;
  let closed = false;
  const queue = [];

  function send(cmd) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(cmd));
    } else {
      queue.push(cmd);
    }
  }

  function flush() {
    while (ws && ws.readyState === WebSocket.OPEN && queue.length) {
      ws.send(JSON.stringify(queue.shift()));
    }
  }

  function open() {
    if (closed) return null;
    ws = new WebSocket(url);

    ws.addEventListener('open', () => {
      if (onStatus) onStatus('websocket open');
      flush();
    });

    ws.addEventListener('message', (ev) => {
      let data;
      try { data = JSON.parse(ev.data); } catch (err) { return; }
      if (onMessage) onMessage(data);
    });

    ws.addEventListener('close', () => {
      if (onStatus) onStatus('websocket closed; reconnecting…');
      setTimeout(open, 1500);
    });

    ws.addEventListener('error', (err) => {
      if (onStatus) onStatus('websocket error');
      console.error('websocket error', err);
    });

    return ws;
  }

  open();

  return {
    get ws() { return ws; },
    send,
    close() { closed = true; if (ws) ws.close(); },
  };
}

export function sendCommand(conn, cmd) {
  if (!conn) return;
  if (typeof conn.send === 'function') {
    conn.send(cmd);
    return;
  }
  if (conn && conn.readyState === WebSocket.OPEN) {
    conn.send(JSON.stringify(cmd));
  }
}
