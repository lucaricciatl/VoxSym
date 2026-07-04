import * as THREE from 'three';

const dummy = new THREE.Object3D();
const shaftUp = new THREE.Vector3(0, 1, 0);
const _color = new THREE.Color();
const _origin = new THREE.Vector3();
const _tip = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _quat = new THREE.Quaternion();

export function createArrowRenderer(sceneApi) {
  const scene = sceneApi.scene;

  const shaftGeo = new THREE.CylinderGeometry(0.12, 0.12, 0.75, 12, 1);
  shaftGeo.translate(0, 0.375, 0);
  const headGeo = new THREE.ConeGeometry(0.36, 0.5, 16, 1);
  headGeo.translate(0, 0.875, 0);

  const material = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    transparent: false,
    opacity: 1.0,
    depthTest: false,
  });

  let shaftMesh = new THREE.InstancedMesh(shaftGeo, material, 1);
  let headMesh = new THREE.InstancedMesh(headGeo, material, 1);
  shaftMesh.count = 0;
  headMesh.count = 0;
  shaftMesh.visible = false;
  headMesh.visible = false;
  scene.add(shaftMesh);
  scene.add(headMesh);

  function resize(mesh, geo, needed) {
    const newMesh = new THREE.InstancedMesh(geo, material, Math.max(needed, 1));
    newMesh.count = needed;
    scene.remove(mesh);
    mesh.dispose();
    scene.add(newMesh);
    return newMesh;
  }

  function update(arrows) {
    if (!arrows || arrows.count <= 0 || !Array.isArray(arrows.points) || arrows.points.length < 6) {
      shaftMesh.count = 0;
      headMesh.count = 0;
      shaftMesh.visible = false;
      headMesh.visible = false;
      return 0;
    }

    const count = arrows.count;
    const points = arrows.points;
    const colors = arrows.colors || [];
    const baseSize = Number(arrows.base_size ?? 1.0);

    if (shaftMesh.count !== count) {
      shaftMesh = resize(shaftMesh, shaftGeo, count);
      headMesh = resize(headMesh, headGeo, count);
    }

    const halfVoxel = 0.5 * baseSize;
    const minLen = Math.max(0.2, 0.5 * baseSize);
    const maxLen = Math.max(2.0, 3.0 * baseSize);
    const geoHeight = 1.25; // cylinder 0.75 + cone 0.5 after translation
    const baseScale = Math.max(0.05, baseSize * 0.12); // arrow thickness scales with voxel size

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
        // Place arrow on the voxel surface: tail at -halfVoxel, tip beyond.
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
      const b2 = (colors[i3 + 2] ?? 255) / 255;
      _color.setRGB(r, g, b2);
      shaftMesh.setColorAt(i, _color);
      headMesh.setColorAt(i, _color);
    }

    shaftMesh.count = count;
    headMesh.count = count;
    shaftMesh.visible = true;
    headMesh.visible = true;
    shaftMesh.instanceMatrix.needsUpdate = true;
    headMesh.instanceMatrix.needsUpdate = true;
    if (shaftMesh.instanceColor) shaftMesh.instanceColor.needsUpdate = true;
    if (headMesh.instanceColor) headMesh.instanceColor.needsUpdate = true;

    return count;
  }

  return { update };
}
