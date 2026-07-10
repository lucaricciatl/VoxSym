import * as THREE from 'three';

const dummy = new THREE.Object3D();
const _color = new THREE.Color();

export function updateVoxels(scene, payload) {
  const voxels = payload?.voxels;
  if (!voxels) return;

  const count = voxels.count ?? 0;

  let mesh = scene.voxelMesh;
  if (!mesh || mesh.count !== count) {
    if (mesh) scene.setVoxelMesh(null);
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
    scene.setVoxelMesh(mesh);
  }

  if (count <= 0) {
    mesh.count = 0;
    mesh.visible = false;
    return;
  }
  mesh.visible = true;
  mesh.count = count;

  // Order: render arrows last so they sit on top of transparent voxels.
  if (scene.arrowRoot) {
    scene.scene.add(scene.arrowRoot);
  }

  // Keep payload for hover/selection and probing.
  mesh.userData.voxels = voxels;
  mesh.userData.scalar_values = payload.scalar_values || [];
  mesh.userData.scalar_layer = payload.scalar_layer || 'material';

  const positions = voxels.positions || [];
  const sizes = voxels.sizes || [];
  const colors = voxels.colors || [];
  const globalOpacity = payload.opacity ?? 1.0;

  mesh.material.opacity = Math.max(0, Math.min(1, globalOpacity));

  const opacities = voxels.opacities || [];
  for (let i = 0; i < count; i++) {
    const x = positions[i * 3] ?? 0;
    const y = positions[i * 3 + 1] ?? 0;
    const z = positions[i * 3 + 2] ?? 0;
    const size = sizes[i] ?? 1.0;
    const alpha = opacities[i] ?? 1.0;
    dummy.position.set(x, y, z);
    // Per-voxel opacity via scale: hidden/sliced voxels collapse to zero.
    const scale = alpha > 0.01 ? size : 0;
    dummy.scale.set(scale, scale, scale);
    dummy.updateMatrix();
    mesh.setMatrixAt(i, dummy.matrix);

    const r = colors[i * 3] ?? 200;
    const g = colors[i * 3 + 1] ?? 200;
    const b = colors[i * 3 + 2] ?? 200;
    _color.setRGB(r / 255, g / 255, b / 255);
    mesh.setColorAt(i, _color);
  }
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
}
