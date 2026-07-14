import * as THREE from 'three';

export class Recorder {
  constructor(store, scene) {
    this.store = store;
    this.scene = scene;
    this.mediaRecorder = null;
    this.recordedChunks = [];
    this._offscreenRenderer = null;
    this._recordInterval = null;
    this._offscreenCanvas = null;
    this.lastError = '';
  }

  isSupported() {
    return typeof MediaRecorder !== 'undefined' && HTMLCanvasElement.prototype.captureStream;
  }

  start(scale = 2) {
    if (this.mediaRecorder) {
      this.lastError = 'A recording is already in progress';
      return false;
    }
    if (!this.isSupported()) {
      this.lastError = 'MediaRecorder or canvas.captureStream is not available';
      return false;
    }

    try {
      const renderer = this.scene.renderer;
      const baseW = renderer.domElement.width;
      const baseH = renderer.domElement.height;
      const w = Math.max(1, Math.round(baseW * scale));
      const h = Math.max(1, Math.round(baseH * scale));

      this._offscreenCanvas = document.createElement('canvas');
      this._offscreenCanvas.width = w;
      this._offscreenCanvas.height = h;

      this._offscreenRenderer = new THREE.WebGLRenderer({
        canvas: this._offscreenCanvas,
        antialias: true,
        preserveDrawingBuffer: true,
      });
      this._offscreenRenderer.setPixelRatio(1);
      this._offscreenRenderer.setSize(w, h, false);

      const stream = this._offscreenCanvas.captureStream(30);
      const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
        ? 'video/webm;codecs=vp9'
        : MediaRecorder.isTypeSupported('video/webm;codecs=vp8')
        ? 'video/webm;codecs=vp8'
        : 'video/webm';
      this.mediaRecorder = new MediaRecorder(stream, { mimeType: mime });
      this.recordedChunks = [];
      this.mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) this.recordedChunks.push(e.data);
      };
      this.mediaRecorder.onstop = () => this._download();
      this.mediaRecorder.start();

      this._recordInterval = window.setInterval(() => {
        if (this._offscreenRenderer && this.scene) {
          this._offscreenRenderer.render(this.scene.scene, this.scene.camera);
        }
      }, 1000 / 30);
      this.lastError = '';
      return true;
    } catch (err) {
      this.lastError = err?.message || String(err);
      console.error('Recorder start failed:', err);
      this.stop(true);
      return false;
    }
  }

  stop(skipDownload = false) {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      if (skipDownload) {
        this.mediaRecorder.onstop = null;
      }
      this.mediaRecorder.stop();
    }
    if (this._recordInterval) {
      window.clearInterval(this._recordInterval);
      this._recordInterval = null;
    }
    if (this._offscreenRenderer) {
      this._offscreenRenderer.dispose();
      this._offscreenRenderer = null;
    }
    this._offscreenCanvas = null;
  }

  _download() {
    if (this.recordedChunks.length === 0) {
      this.mediaRecorder = null;
      return;
    }
    const blob = new Blob(this.recordedChunks, { type: 'video/webm' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `voxsym-capture-${Date.now()}.webm`;
    a.click();
    URL.revokeObjectURL(url);
    this.mediaRecorder = null;
    this.recordedChunks = [];
  }
}
