import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

function makeLabelTexture(text, color = '#000000') {
  const canvas = document.createElement('canvas');
  const size = 128;
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = 'rgba(255,255,255,0.7)';
  ctx.fillRect(0, 0, size, size);
  ctx.font = 'bold 48px system-ui, sans-serif';
  ctx.fillStyle = color;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, size / 2, size / 2);
  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

export class Scene {
  constructor(container) {
    this.container = container;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xffffff);

    this.camera = new THREE.PerspectiveCamera(
      45,
      container.clientWidth / container.clientHeight,
      0.1,
      1000,
    );
    this.camera.position.set(15, 15, 12);
    this.camera.up.set(0, 0, 1);
    this.camera.lookAt(0, 0, 0);

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    this.renderer.shadowMap.enabled = true;
    container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.1;
    this.controls.mouseButtons = {
      LEFT: THREE.MOUSE.ROTATE,
      MIDDLE: THREE.MOUSE.DOLLY,
      RIGHT: THREE.MOUSE.PAN,
    };
    // Orbit around the Z-axis (camera.up is already Z-up).
    this.controls.target.set(0, 0, 0);
    this.controls.screenSpacePanning = false;
    this.controls.maxPolarAngle = Math.PI;

    this.scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    this._dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    this._dirLight.position.set(10, 20, 10);
    this._dirLight.castShadow = true;
    this.scene.add(this._dirLight);

    this.voxelMesh = null;
    this.arrowRoot = null;
    this.shadowEnabled = true;

    this._isOrtho = false;
    this._defaultCam = {
      fov: this.camera.fov,
      near: this.camera.near,
      far: this.camera.far,
      position: this.camera.position.clone(),
      target: this.controls.target.clone(),
      up: this.camera.up.clone(),
    };

    // Grid on the XY plane so Z is the vertical (up) axis.
    this._gridHelper = new THREE.GridHelper(20, 20, 0x888888, 0xcccccc);
    this._gridHelper.rotation.x = -Math.PI / 2;
    this._gridHelper.visible = true;
    this.scene.add(this._gridHelper);

    this._axesGroup = new THREE.Group();
    this._axesGroup.visible = true;
    this.scene.add(this._axesGroup);
    this._buildAxes();
    // Z-up convention: camera.up is already (0,0,1), so the +Z arrow points up.

    window.addEventListener('resize', () => this.onResize());
    this.animate();
  }

  _buildAxes() {
    const axisLength = 5;
    const shaftRadius = 0.12;
    const headRadius = 0.32;
    const headLength = 0.7;
    const axes = [
      { dir: new THREE.Vector3(1, 0, 0), color: 0xff0000, label: 'X' },
      { dir: new THREE.Vector3(0, 1, 0), color: 0x00aa00, label: 'Y' },
      { dir: new THREE.Vector3(0, 0, 1), color: 0x0066ff, label: 'Z' },
    ];

    for (const { dir, color, label } of axes) {
      const material = new THREE.MeshStandardMaterial({
        color,
        roughness: 0.3,
        metalness: 0.2,
      });
      const shaftGeo = new THREE.CylinderGeometry(shaftRadius, shaftRadius, axisLength, 16, 1);
      shaftGeo.translate(0, axisLength / 2, 0);
      const headGeo = new THREE.ConeGeometry(headRadius, headLength, 16, 1);
      headGeo.translate(0, axisLength + headLength / 2, 0);

      const shaft = new THREE.Mesh(shaftGeo, material);
      const head = new THREE.Mesh(headGeo, material);
      const group = new THREE.Group();
      group.add(shaft);
      group.add(head);

      const quaternion = new THREE.Quaternion();
      quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
      group.setRotationFromQuaternion(quaternion);
      this._axesGroup.add(group);

      const spriteMat = new THREE.SpriteMaterial({ map: makeLabelTexture(label, '#000') });
      const sprite = new THREE.Sprite(spriteMat);
      sprite.position.copy(dir.clone().multiplyScalar(axisLength + 1.0));
      sprite.scale.set(0.8, 0.8, 1);
      this._axesGroup.add(sprite);
    }
  }

  onResize() {
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    if (w === 0 || h === 0) return;
    const aspect = w / h;
    if (this.camera.isOrthographicCamera) {
      const size = 16;
      this.camera.left = -size;
      this.camera.right = size;
      this.camera.top = size / aspect;
      this.camera.bottom = -size / aspect;
    } else {
      this.camera.aspect = aspect;
    }
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  setVoxelMesh(mesh) {
    if (this.voxelMesh) this.scene.remove(this.voxelMesh);
    this.voxelMesh = mesh;
    if (mesh) {
      this.scene.add(mesh);
      this._applyShadowToMesh(mesh);
    }
  }

  setArrowRoot(root) {
    if (this.arrowRoot) this.scene.remove(this.arrowRoot);
    this.arrowRoot = root;
    if (root) this.scene.add(root);
  }

  setShadowEnabled(value) {
    const v = Boolean(value);
    if (this.shadowEnabled === v) return;
    this.shadowEnabled = v;
    this.renderer.shadowMap.enabled = v;
    this._dirLight.castShadow = v;
    if (this.voxelMesh) this._applyShadowToMesh(this.voxelMesh);
    if (this.arrowRoot) {
      const shaft = this.arrowRoot.userData?.shaftMesh;
      const head = this.arrowRoot.userData?.headMesh;
      if (shaft) {
        shaft.castShadow = v;
        shaft.receiveShadow = v;
      }
      if (head) {
        head.castShadow = v;
        head.receiveShadow = v;
      }
    }
  }

  _applyShadowToMesh(mesh) {
    if (!mesh) return;
    mesh.castShadow = this.shadowEnabled;
    mesh.receiveShadow = this.shadowEnabled;
  }

  showGrid(visible) {
    if (this._gridHelper) this._gridHelper.visible = visible;
  }

  showAxes(visible) {
    if (this._axesGroup) this._axesGroup.visible = visible;
  }

  /**
   * Render the current view at `scale` times the canvas resolution and
   * return a PNG blob.  Uses an offscreen render target so the displayed
   * canvas size and pixel ratio are left untouched.
   *
   * If `overlay` is provided it is called with the 2-D canvas context and
   * the high-res width/height so callers can paint a time stamp, legend,
   * colorbar, etc. on top of the rendered scene.
   */
  capturePng(scale = 2, overlay = null) {
    const renderer = this.renderer;
    const w = Math.max(1, Math.round(renderer.domElement.width * scale));
    const h = Math.max(1, Math.round(renderer.domElement.height * scale));

    const target = new THREE.WebGLRenderTarget(w, h);
    const prevTarget = renderer.getRenderTarget();
    renderer.setRenderTarget(target);
    renderer.render(this.scene, this.camera);

    const pixels = new Uint8Array(w * h * 4);
    renderer.readRenderTargetPixels(target, 0, 0, w, h, pixels);
    renderer.setRenderTarget(prevTarget);
    target.dispose();

    // WebGL pixels are bottom-up; flip to top-down for the PNG.
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    const imgData = ctx.createImageData(w, h);
    for (let y = 0; y < h; y++) {
      const src = (h - 1 - y) * w * 4;
      const dst = y * w * 4;
      for (let x = 0; x < w * 4; x++) {
        imgData.data[dst + x] = pixels[src + x];
      }
    }
    ctx.putImageData(imgData, 0, 0);

    if (overlay) {
      try {
        overlay(ctx, w, h);
      } catch (err) {
        console.error('capturePng overlay failed:', err);
      }
    }

    return new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
  }

  setSelectionBox(position, size, color, name = 'selection') {
    if (size <= 0) {
      this.removeSelectionBox(name);
      return;
    }
    const boxName = `_selBox_${name}`;
    let box = this[boxName];
    if (!box) {
      const geometry = new THREE.BoxGeometry(1, 1, 1);
      const edges = new THREE.EdgesGeometry(geometry);
      box = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color }));
      this.scene.add(box);
      this[boxName] = box;
    }
    box.material.color.setHex(color);
    box.position.copy(position);
    box.scale.set(size, size, size);
    box.visible = true;
  }

  removeSelectionBox(name = 'selection') {
    const boxName = `_selBox_${name}`;
    if (this[boxName]) {
      this.scene.remove(this[boxName]);
      this[boxName].geometry.dispose();
      this[boxName].material.dispose();
      this[boxName] = null;
    }
  }

  resetCamera() {
    const cam = this.camera;
    cam.position.copy(this._defaultCam.position);
    cam.up.copy(this._defaultCam.up);
    this.controls.target.copy(this._defaultCam.target);
    cam.lookAt(this._defaultCam.target);
    if (this._isOrtho) {
      const size = 16;
      cam.left = -size;
      cam.right = size;
      cam.top = size / cam.aspect;
      cam.bottom = -size / cam.aspect;
    }
    cam.updateProjectionMatrix();
    this.controls.update();
    this.controls.saveState();
  }

  _makeOrthographicCamera() {
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    const aspect = w / h;
    const size = 16;
    const cam = new THREE.OrthographicCamera(
      -size, size, size / aspect, -size / aspect, this._defaultCam.near, this._defaultCam.far,
    );
    cam.position.copy(this.camera.position);
    cam.up.copy(this.camera.up);
    cam.lookAt(this.controls.target);
    return cam;
  }

  toggleOrthographic() {
    this._isOrtho = !this._isOrtho;
    const oldCam = this.camera;
    if (this._isOrtho) {
      this.camera = this._makeOrthographicCamera();
    } else {
      this.camera = new THREE.PerspectiveCamera(
        this._defaultCam.fov,
        this.container.clientWidth / this.container.clientHeight,
        this._defaultCam.near,
        this._defaultCam.far,
      );
      this.camera.position.copy(oldCam.position);
      this.camera.up.copy(oldCam.up);
      this.camera.lookAt(this.controls.target);
    }
    this.controls.object = this.camera;
    this.onResize();
    this.controls.update();
    return this._isOrtho;
  }

  getVoxelValueAt(instanceId) {
    const mesh = this.voxelMesh;
    const voxels = mesh?.userData?.voxels;
    if (!voxels || instanceId < 0 || instanceId >= (voxels.count ?? 0)) return null;
    const i = instanceId;
    const positions = voxels.positions || [];
    const sizes = voxels.sizes || [];
    const colors = voxels.colors || [];
    return {
      id: i,
      x: positions[i * 3] ?? 0,
      y: positions[i * 3 + 1] ?? 0,
      z: positions[i * 3 + 2] ?? 0,
      size: sizes[i] ?? 1.0,
      color: [colors[i * 3] ?? 0, colors[i * 3 + 1] ?? 0, colors[i * 3 + 2] ?? 0],
    };
  }
}
