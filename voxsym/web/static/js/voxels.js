import * as THREE from 'three';

const dummy = new THREE.Object3D();
const _color = new THREE.Color();
let hasCenteredCamera = false;

export function updateFromPayload(sceneApi, payload) {
  const voxels = payload.voxels;
  if (!voxels) return;

  let count = 0;
  let data = [];
  if (Array.isArray(voxels)) {
    data = voxels;
    count = voxels.length;
  } else if (voxels.count !== undefined) {
    count = voxels.count;
    data = voxels;
  }

  let mesh = sceneApi.getVoxelMesh();
  if (!mesh || mesh.count !== count) {
    if (mesh) sceneApi.scene.remove(mesh);
    const geometry = new THREE.BoxGeometry(1, 1, 1);
    const material = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.9,
      roughness: 0.5,
      metalness: 0.1,
    });
    mesh = new THREE.InstancedMesh(geometry, material, Math.max(count, 1));
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    sceneApi.setVoxelMesh(mesh);
    hasCenteredCamera = false;
  }
  if (count <= 0) {
    mesh.count = 0;
    mesh.visible = false;
    return;
  }
  mesh.visible = true;
  mesh.count = count;

  const positions = data.positions;
  const sizes = data.sizes;
  const colors = data.colors;
  const opacities = data.opacities;

  for (let i = 0; i < count; i++) {
    let x = 0, y = 0, z = 0, size = 1.0;
    if (positions && positions.length >= i * 3 + 3) {
      x = positions[i * 3];
      y = positions[i * 3 + 1];
      z = positions[i * 3 + 2];
    } else if (Array.isArray(data)) {
      const v = data[i];
      x = v.x ?? 0;
      y = v.y ?? 0;
      z = v.z ?? 0;
      size = v.size ?? 1.0;
    }
    if (sizes && sizes.length > i) size = sizes[i];

    dummy.position.set(x, y, z);
    dummy.scale.set(size, size, size);
    dummy.updateMatrix();
    mesh.setMatrixAt(i, dummy.matrix);

    let r = 255, g = 255, b = 255;
    if (colors && colors.length >= i * 3 + 3) {
      r = colors[i * 3];
      g = colors[i * 3 + 1];
      b = colors[i * 3 + 2];
    } else if (Array.isArray(data)) {
      const v = data[i];
      r = v.r ?? 255;
      g = v.g ?? 255;
      b = v.b ?? 255;
    }
    _color.setRGB(r / 255, g / 255, b / 255);
    mesh.setColorAt(i, _color);
  }

  // Per-frame opacity updates
  if (payload.opacity !== undefined) {
    mesh.material.opacity = Math.max(0, Math.min(1, payload.opacity));
  }
  if (Array.isArray(opacities) && opacities.length > 0) {
    const avg = opacities.reduce((a, b) => a + b, 0) / opacities.length;
    mesh.material.opacity = Math.max(0, Math.min(1, avg));
  }

  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;

  if (!hasCenteredCamera) {
    centerCamera(sceneApi.camera, sceneApi.controls, data, positions);
    hasCenteredCamera = true;
  }
}

function centerCamera(camera, controls, data, positions) {
  if (!data) return;
  let minX = Infinity, maxX = -Infinity;
  let minY = Infinity, maxY = -Infinity;
  let minZ = Infinity, maxZ = -Infinity;

  if (positions && positions.length >= 3) {
    for (let i = 0; i < positions.length; i += 3) {
      const x = positions[i], y = positions[i + 1], z = positions[i + 2];
      if (x < minX) minX = x; if (x > maxX) maxX = x;
      if (y < minY) minY = y; if (y > maxY) maxY = y;
      if (z < minZ) minZ = z; if (z > maxZ) maxZ = z;
    }
  } else if (Array.isArray(data)) {
    for (const v of data) {
      const x = v.x ?? 0, y = v.y ?? 0, z = v.z ?? 0;
      if (x < minX) minX = x; if (x > maxX) maxX = x;
      if (y < minY) minY = y; if (y > maxY) maxY = y;
      if (z < minZ) minZ = z; if (z > maxZ) maxZ = z;
    }
  }

  if (!isFinite(minX)) return;
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const cz = (minZ + maxZ) / 2;
  const span = Math.max(maxX - minX, maxY - minY, maxZ - minZ);
  const radius = span / 2 + Math.max(span * 0.6, 4);
  camera.position.set(cx + radius, cy + radius, cz + radius);
  camera.lookAt(cx, cy, cz);
  camera.updateProjectionMatrix();
  if (controls && controls.target) {
    controls.target.set(cx, cy, cz);
    controls.update();
  }
}
