import { initScene } from './scene.js?v=2';
import { updateFromPayload } from './voxels.js?v=3';
import { createArrowRenderer } from './arrows.js?v=4';
import { initGui } from './gui.js?v=5';
import { initPlayback } from './playback.js?v=2';
import { connectWebSocket } from './websocket.js?v=4';

let isPlaying = false;
let mediaRecorder = null;
let recordedChunks = [];
let recordStart = 0;
let recordTimer = null;

const wsUrl = new URL('/ws', window.location.href);
wsUrl.protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';

const conn = connectWebSocket(wsUrl.href, onFrame, (status) => gui.setStatus(status));
const gui = initGui(() => conn);

const sceneApi = initScene(document.getElementById('viewport'));
const arrowsApi = createArrowRenderer(sceneApi);

const playbackApi = initPlayback(gui, onPlaybackFrame);

function formatTime(t) {
  const abs = Math.abs(Number(t) || 0);
  if (abs >= 1) return `${t.toFixed(3)} s`;
  if (abs >= 1e-3) return `${(t * 1e3).toFixed(2)} ms`;
  if (abs >= 1e-6) return `${(t * 1e6).toFixed(2)} µs`;
  return `${(t * 1e9).toFixed(2)} ns`;
}

function setPlayButton(playing) {
  isPlaying = Boolean(playing);
  const btn = document.getElementById('tb-play');
  if (btn) btn.textContent = isPlaying ? '⏸' : '▶';
}

function onFrame(payload) {
  if (!payload || payload.type !== 'frame') return;

  gui.syncStateFromPayload(payload);
  gui.syncActiveLayers(payload.active_layers);

  if (payload.voxels) {
    updateFromPayload(sceneApi, payload);
    gui.setVoxelCount(payload.voxels.count ?? 0);
  }

  if (payload.arrows) {
    const arrowCount = arrowsApi.update(payload.arrows);
    gui.setArrowCount(arrowCount);
  } else {
    arrowsApi.update({ count: 0 });
    gui.setArrowCount(0);
  }

  if (payload.playing !== undefined) {
    setPlayButton(payload.playing);
  }

  if (payload.time !== undefined) {
    const timeDisplay = document.getElementById('time-display');
    const status = document.getElementById('status');
    const frameIdx = payload.frame_index ?? 0;
    if (timeDisplay) timeDisplay.textContent = `t = ${formatTime(payload.time)}`;
    if (status) {
      status.textContent = `${formatTime(payload.time)} | frame=${frameIdx} | ${payload.voxels?.count ?? 0} voxels`;
    }
  }

  if (playbackApi && payload.frame_index !== undefined) {
    playbackApi.pushFrame(payload);
  }
}

function onPlaybackFrame(frame) {
  onFrame(frame);
}

async function loadTestFrame() {
  try {
    const resp = await fetch('data/test_frame.json?nocache=' + Date.now());
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const payload = await resp.json();
    onFrame(payload);
  } catch (err) {
    gui.setStatus('test frame error: ' + err.message);
    console.error(err);
  }
}

function emit(cmd) {
  if (conn) conn.send(cmd);
}

function bindTopBar() {
  const playBtn = document.getElementById('tb-play');
  const resetBtn = document.getElementById('tb-reset');
  const stopBtn = document.getElementById('tb-stop');
  const recordBtn = document.getElementById('tb-record');
  const helpBtn = document.getElementById('tb-help');

  playBtn?.addEventListener('click', () => {
    isPlaying = !isPlaying;
    emit({ cmd: isPlaying ? 'play' : 'pause' });
    setPlayButton(isPlaying);
  });

  resetBtn?.addEventListener('click', () => {
    isPlaying = false;
    setPlayButton(false);
    emit({ cmd: 'reset' });
  });

  stopBtn?.addEventListener('click', () => {
    isPlaying = false;
    setPlayButton(false);
    emit({ cmd: 'stop' });
  });

  recordBtn?.addEventListener('click', () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
      if (recordTimer) {
        clearInterval(recordTimer);
        recordTimer = null;
      }
      recordBtn.textContent = '●';
      recordBtn.classList.remove('recording');
      mediaRecorder = null;
    } else {
      try {
        const stream = sceneApi.renderer.domElement.captureStream(30);
        const options = MediaRecorder.isTypeSupported('video/webm')
          ? { mimeType: 'video/webm' }
          : undefined;
        mediaRecorder = new MediaRecorder(stream, options);
        recordedChunks = [];
        mediaRecorder.ondataavailable = (e) => {
          if (e.data && e.data.size) recordedChunks.push(e.data);
        };
        mediaRecorder.onstop = () => {
          if (!recordedChunks.length) return;
          const blob = new Blob(recordedChunks, { type: 'video/webm' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `voxsym-${Date.now()}.webm`;
          a.click();
          URL.revokeObjectURL(url);
        };
        mediaRecorder.start(100);
        recordStart = performance.now();
        recordBtn.classList.add('recording');
        recordTimer = setInterval(() => {
          const s = ((performance.now() - recordStart) / 1000).toFixed(1);
          recordBtn.textContent = `● ${s}s`;
        }, 500);
      } catch (err) {
        console.error('Failed to start recording:', err);
        gui.setStatus('record failed: ' + err.message);
      }
    }
  });

  helpBtn?.addEventListener('click', () => {
    const helpText = [
      'Controls:',
      '▶ / ⏸ — play or pause the simulation',
      '↺ — reset the simulation',
      '⏹ — stop the simulation',
      '● — record the canvas to a .webm video',
      '🎨 — choose scalar layer and vector overlays',
      '⚙️ — opacity, arrow scale, steps/frame',
      '✂️ — cross-section slicing',
      '💾 — upload a recording for playback',
    ].join('\n');
    alert(helpText);
  });
}

bindTopBar();
loadTestFrame();

window.voxsym = window.voxsym || {};
window.voxsym.conn = conn;
window.voxsym.getWs = () => conn?.ws ?? null;
window.voxsym.sceneApi = sceneApi;
window.voxsym.arrowsApi = arrowsApi;
window.voxsym.gui = gui;
window.voxsym.onFrame = onFrame;

window.addEventListener('resize', () => {
  const viewport = document.getElementById('viewport');
  if (sceneApi && viewport) {
    const w = viewport.clientWidth;
    const h = viewport.clientHeight;
    sceneApi.camera.aspect = w / h;
    sceneApi.camera.updateProjectionMatrix();
    sceneApi.renderer.setSize(w, h);
  }
});
