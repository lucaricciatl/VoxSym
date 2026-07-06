import * as THREE from 'three';

const dummy = new THREE.Object3D();
const shaftUp = new THREE.Vector3(0, 1, 0);
const _color = new THREE.Color();
const _origin = new THREE.Vector3();
const _tip = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _quat = new THREE.Quaternion();

export function updateArrows(scene, arrows) {
  if (!arrows || arrows.count <= 0 || !Array.isArray(arrows.points) || arrows.points.length < 6) {
    scene.setArrowRoot(null);
    return 0;
  }

  const count = arrows.count;
  const points = arrows.points.flat ? arrows.points.flat() : arrows.points;
  const colors = (arrows.colors || []).flat ? (arrows.colors || []).flat() : (arrows.colors || []);
  const baseSize = Number(arrows.base_size ?? 1.0);

  const root = new THREE.Group();
  const material = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.95,
    depthTest: false,
    depthWrite: false,
  });

  const shaftGeo = new THREE.CylinderGeometry(0.12, 0.12, 0.75, 12, 1);
  shaftGeo.translate(0, 0.375, 0);
  const headGeo = new THREE.ConeGeometry(0.36, 0.5, 16, 1);
  headGeo.translate(0, 0.875, 0);

  const shaftMesh = new THREE.InstancedMesh(shaftGeo, material, count);
  const headMesh = new THREE.InstancedMesh(headGeo, material, count);
  shaftMesh.count = count;
  headMesh.count = count;
  shaftMesh.castShadow = false;
  headMesh.castShadow = false;
  shaftMesh.frustumCulled = false;
  headMesh.frustumCulled = false;

  const halfVoxel = 0.5 * baseSize;
  const minLen = Math.max(0.4, 0.6 * baseSize);
  const maxLen = Math.max(2.0, 2.5 * baseSize);
  const geoHeight = 1.25;
  const baseScale = Math.max(0.08, baseSize * 0.15);

  for (let i = 0; i < count; i++) {
    const i6 = i * 6;
    const i3 = i * 3;
    const ax = points[i6];
    const ay = points[i6 + 1];
    const az = points[i6 + 2];
    const bx = points[i6 + 3];
    const by = points[i6 + 4];
    const bz = points[i6 + 5];

    _origin.set(ax, ay, az);
    _tip.set(bx, by, bz);
    _dir.subVectors(_tip, _origin);
    let len = _dir.length();

    if (len < 1e-6) {
      dummy.scale.set(0, 0, 0);
      dummy.position.copy(_origin);
      dummy.rotation.set(0, 0, 0);
    } else {
      _dir.normalize();
      len = Math.max(minLen, Math.min(maxLen, len));
      const tail = _dir.clone().multiplyScalar(-halfVoxel).add(_origin);
      const tip = _dir.clone().multiplyScalar(halfVoxel + len).add(_origin);
      const renderedLen = tip.distanceTo(tail);
      const scale = renderedLen / geoHeight;

      dummy.scale.set(scale * baseScale, scale, scale * baseScale);
      dummy.position.copy(tail);
      _quat.setFromUnitVectors(shaftUp, _dir);
      dummy.setRotationFromQuaternion(_quat);
    }
    dummy.updateMatrix();

    shaftMesh.setMatrixAt(i, dummy.matrix);
    headMesh.setMatrixAt(i, dummy.matrix);

    const r = (colors[i3] ?? 255) / 255;
    const g = (colors[i3 + 1] ?? 255) / 255;
    const b = (colors[i3 + 2] ?? 255) / 255;
    _color.setRGB(r, g, b);
    shaftMesh.setColorAt(i, _color);
    headMesh.setColorAt(i, _color);
  }

  shaftMesh.instanceMatrix.needsUpdate = true;
  headMesh.instanceMatrix.needsUpdate = true;
  if (shaftMesh.instanceColor) shaftMesh.instanceColor.needsUpdate = true;
  if (headMesh.instanceColor) headMesh.instanceColor.needsUpdate = true;

  shaftMesh.renderOrder = 999;
  headMesh.renderOrder = 999;

  root.add(shaftMesh);
  root.add(headMesh);
  scene.setArrowRoot(root);

  // Ensure arrows are rendered after voxels so they draw on top.
  scene.scene.remove(scene.arrowRoot);
  scene.scene.add(scene.arrowRoot);

  return count;
}
