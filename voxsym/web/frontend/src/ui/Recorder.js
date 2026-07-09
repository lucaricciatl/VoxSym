export class Recorder {
  constructor(store, canvas) {
    this.store = store;
    this.canvas = canvas;
    this.mediaRecorder = null;
    this.recordedChunks = [];
  }

  isSupported() {
    return typeof MediaRecorder !== 'undefined' && this.canvas?.captureStream;
  }

  start() {
    if (this.mediaRecorder || !this.isSupported()) return false;
    const stream = this.canvas.captureStream(30);
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
    return true;
  }

  stop() {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    }
  }

  downloadFrame() {
    if (!this.canvas) return;
    this.canvas.toBlob(
      (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `voxsym-frame-${Date.now()}.png`;
        a.click();
        URL.revokeObjectURL(url);
      },
      'image/png'
    );
  }

  _download() {
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
