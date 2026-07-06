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
    this.camera.position.set(8, 8, 12);
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

    this.scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(10, 20, 10);
    this.scene.add(dir);

    this.voxelMesh = null;
    this.arrowRoot = null;

    this._gridHelper = new THREE.GridHelper(20, 20, 0x888888, 0xcccccc);
    this._gridHelper.visible = true;
    this.scene.add(this._gridHelper);

    this._axesGroup = new THREE.Group();
    this._axesGroup.visible = true;
    this.scene.add(this._axesGroup);
    this._buildAxes();

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
    this.camera.aspect = w / h;
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
    if (mesh) this.scene.add(mesh);
  }

  setArrowRoot(root) {
    if (this.arrowRoot) this.scene.remove(this.arrowRoot);
    this.arrowRoot = root;
    if (root) this.scene.add(root);
  }

  showGrid(visible) {
    if (this._gridHelper) this._gridHelper.visible = visible;
  }

  showAxes(visible) {
    if (this._axesGroup) this._axesGroup.visible = visible;
  }
}
