import { sendCommand } from './websocket.js?v=1';

/**
 * Upload a recording file and manage a local frame cache / timeline scrub.
 *
 * Because NPZ parsing in browser JS is non-trivial, we rely on the server
 * endpoint `POST /upload` to parse the file and then stream `frame` messages
 * back over the WebSocket.  The module also stores received frames in a local
 * cache so that scrubbing backward/forward is instantaneous once frames have
 * been received.
 */
export function initPlayback(gui, onFrame) {
  const { uploadZone, fileInput } = gui.getUploadElements();
  const { timeline, frameVal, frameTotal, pbPlay, pbPause, timelineWrap } = gui.getTimelineElements();

  let cache = [];
  let playInterval = null;

  function setTimelineVisible(visible, totalFrames = 0) {
    if (!timelineWrap) return;
    timelineWrap.classList.toggle('hidden', !visible);
    if (frameTotal) frameTotal.textContent = String(totalFrames);
    if (timeline) {
      timeline.min = 0;
      timeline.max = Math.max(0, totalFrames - 1);
      timeline.value = 0;
    }
    if (frameVal) frameVal.textContent = '0';
  }

  function showFrame(index) {
    if (!cache.length) return;
    const idx = Math.max(0, Math.min(cache.length - 1, index));
    const frame = cache[idx];
    if (timeline) timeline.value = idx;
    if (frameVal) frameVal.textContent = String(idx);
    onFrame(frame);
  }

  function stopPlayback() {
    if (playInterval) {
      clearInterval(playInterval);
      playInterval = null;
    }
  }

  function startPlayback() {
    if (!cache.length) return;
    stopPlayback();
    playInterval = setInterval(() => {
      let idx = parseInt(timeline?.value ?? '0', 10) + 1;
      if (idx >= cache.length) idx = 0;
      showFrame(idx);
    }, 200);
  }

  pbPlay?.addEventListener('click', startPlayback);
  pbPause?.addEventListener('click', stopPlayback);

  timeline?.addEventListener('input', () => {
    stopPlayback();
    const idx = parseInt(timeline.value, 10);
    showFrame(idx);
    sendCommand(gui.ws, { cmd: 'seek', frame: idx });
  });

  function handleFile(file) {
    gui.setStatus(`uploading ${file.name}…`);
    const form = new FormData();
    form.append('recording', file);

    fetch('/upload', { method: 'POST', body: form })
      .then((resp) => {
        if (!resp.ok) {
          if (resp.status === 404) {
            throw new Error('server upload not implemented');
          }
          throw new Error(`HTTP ${resp.status}`);
        }
        return resp.json();
      })
      .then((meta) => {
        cache = [];
        setTimelineVisible(false);
        gui.setStatus(meta.message || 'uploaded; awaiting frames…');
        // Request server to stream all frames as separate `frame` messages.
        sendCommand(gui.ws, { cmd: 'playback', filename: file.name });
      })
      .catch((err) => {
        gui.setStatus('upload failed: ' + err.message);
        console.error(err);
      });
  }

  fileInput?.addEventListener('change', () => {
    const file = fileInput.files?.[0];
    if (file) handleFile(file);
  });

  uploadZone?.addEventListener('dragover', (ev) => {
    ev.preventDefault();
    uploadZone.classList.add('dragover');
  });
  uploadZone?.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
  });
  uploadZone?.addEventListener('drop', (ev) => {
    ev.preventDefault();
    uploadZone.classList.remove('dragover');
    const file = ev.dataTransfer?.files?.[0];
    if (file) handleFile(file);
  });

  // Allow external code to push frames into the cache and update timeline.
  return {
    pushFrame(payload) {
      if (!payload || payload.type !== 'frame') return;
      const idx = payload.frame_index;
      const total = payload.num_frames;
      if (idx === undefined || total === undefined) return;
      cache[idx] = payload;
      setTimelineVisible(true, total);
      showFrame(idx);
    },
  };
}

export function makePlaybackCache() {
  return { cache: [] };
}
