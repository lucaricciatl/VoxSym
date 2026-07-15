import * as THREE from 'three';

const dummy = new THREE.Object3D();
const shaftUp = new THREE.Vector3(0, 1, 0);
const _color = new THREE.Color();
const _origin = new THREE.Vector3();
const _tip = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _quat = new THREE.Quaternion();

function makeArrowMeshes(count, shadowEnabled) {
  const material = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.95,
    depthTest: false,
    depthWrite: false,
  });

  const shaftGeo = new THREE.CylinderGeometry(0.12, 0.12, 1.0, 12, 1);
  shaftGeo.translate(0, 0.5, 0);
  const headGeo = new THREE.ConeGeometry(0.25, 0.25, 16, 1);
  headGeo.translate(0, 1.125, 0);

  const shaftMesh = new THREE.InstancedMesh(shaftGeo, material, count);
  const headMesh = new THREE.InstancedMesh(headGeo, material, count);
  shaftMesh.count = count;
  headMesh.count = count;
  shaftMesh.castShadow = shadowEnabled;
  headMesh.castShadow = shadowEnabled;
  shaftMesh.receiveShadow = shadowEnabled;
  headMesh.receiveShadow = shadowEnabled;
  shaftMesh.frustumCulled = false;
  headMesh.frustumCulled = false;
  shaftMesh.renderOrder = 999;
  headMesh.renderOrder = 999;
  return { root: new THREE.Group(), shaftMesh, headMesh };
}

export function updateArrows(scene, arrows, shadowEnabled = false) {
  if (!arrows || arrows.count <= 0 || !Array.isArray(arrows.points) || arrows.points.length < 6) {
    scene.setArrowRoot(null);
    return 0;
  }

  const count = arrows.count;
  const points = arrows.points.flat ? arrows.points.flat() : arrows.points;
  const colors = (arrows.colors || []).flat ? (arrows.colors || []).flat() : (arrows.colors || []);
  const strengths = arrows.strengths && arrows.strengths.length ?
    (arrows.strengths.flat ? arrows.strengths.flat() : arrows.strengths) :
    null;
  const baseSize = Number(arrows.base_size ?? 1.0);
  const arrowScale = Number(arrows.arrow_scale ?? 1.0);

  let root = scene.arrowRoot;
  let shaftMesh = root?.userData?.shaftMesh;
  let headMesh = root?.userData?.headMesh;

  if (!root || !shaftMesh || !headMesh || shaftMesh.count !== count) {
    if (root) scene.setArrowRoot(null);
    const made = makeArrowMeshes(count, shadowEnabled);
    root = made.root;
    shaftMesh = made.shaftMesh;
    headMesh = made.headMesh;
    root.userData.shaftMesh = shaftMesh;
    root.userData.headMesh = headMesh;
    root.add(shaftMesh);
    root.add(headMesh);
    scene.setArrowRoot(root);
  } else {
    const cast = Boolean(shadowEnabled);
    if (shaftMesh.castShadow !== cast || shaftMesh.receiveShadow !== cast) {
      shaftMesh.castShadow = cast;
      headMesh.castShadow = cast;
      shaftMesh.receiveShadow = cast;
      headMesh.receiveShadow = cast;
    }
  }

  const halfVoxel = 0.5 * baseSize;
  const geoHeight = 1.25;
  const minRadius = Math.max(0.02, baseSize * 0.04 * arrowScale);
  const maxRadius = Math.max(0.08, baseSize * 0.22 * arrowScale);

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
      const strength = strengths ? Math.max(0, Math.min(1, strengths[i] ?? 1)) : 1.0;
      const minLen = 0.12 * baseSize * arrowScale;
      const renderedLen = Math.max(minLen, len * arrowScale);
      const radius = minRadius + (maxRadius - minRadius) * strength;

      const tail = _dir.clone().multiplyScalar(-halfVoxel).add(_origin);
      const tip = _dir.clone().multiplyScalar(halfVoxel + renderedLen).add(_origin);
      const actualLen = tip.distanceTo(tail);
      const scaleY = actualLen / geoHeight;

      dummy.scale.set(radius, scaleY, radius);
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

  return count;
}
