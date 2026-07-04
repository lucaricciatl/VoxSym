import * as THREE from 'https://unpkg.com/three@0.160.0/build/three.module.js';
import { OrbitControls } from 'https://unpkg.com/three@0.160.0/examples/jsm/controls/OrbitControls.js';

let renderer, scene, camera, controls;
let voxelMesh = null;

export function initScene(container) {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x111111);

  camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
  camera.position.set(8, 8, 12);
  camera.lookAt(0, 0, 0);

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.shadowMap.enabled = true;
  container.appendChild(renderer.domElement);

  // OrbitControls: left-drag orbit, right-drag pan, scroll zoom
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.1;
  controls.mouseButtons = {
    LEFT: THREE.MOUSE.ROTATE,
    MIDDLE: THREE.MOUSE.DOLLY,
    RIGHT: THREE.MOUSE.PAN,
  };
  controls.minDistance = 0.5;
  controls.maxDistance = 500;

  const ambient = new THREE.AmbientLight(0xffffff, 0.4);
  scene.add(ambient);
  const dir = new THREE.DirectionalLight(0xffffff, 1.0);
  dir.position.set(10, 20, 10);
  dir.castShadow = true;
  scene.add(dir);
  scene.add(new THREE.HemisphereLight(0x8888ff, 0x444422, 0.3));

  const grid = new THREE.GridHelper(20, 20, 0x444444, 0x222222);
  scene.add(grid);

  window.addEventListener('resize', onResize);
  animate();

  return {
    scene,
    camera,
    renderer,
    controls,
    getVoxelMesh: () => voxelMesh,
    setVoxelMesh: (m) => {
      if (voxelMesh) scene.remove(voxelMesh);
      voxelMesh = m;
      if (m) scene.add(m);
    },
    getMeshLimit: () => voxelMesh?.count ?? 0,
  };
}

function onResize() {
  if (!renderer || !camera || !renderer.domElement) return;
  const parent = renderer.domElement.parentElement;
  if (!parent) return;
  const w = parent.clientWidth;
  const h = parent.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}

function animate() {
  requestAnimationFrame(animate);
  if (controls) controls.update();
  if (renderer && scene && camera) renderer.render(scene, camera);
}

export { THREE, voxelMesh };
