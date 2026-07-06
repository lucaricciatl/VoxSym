import { test, expect } from '@playwright/test';
import { startBackend, stopBackend } from './helpers.js';

let backend;

test.beforeAll(async () => {
  backend = await startBackend();
});

test.afterAll(() => {
  stopBackend(backend);
});

function waitForVoxelMesh(page) {
  return page.waitForFunction(() => {
    const mesh = window.voxsymApp?.scene?.voxelMesh;
    return mesh && mesh.instanceColor;
  }, { timeout: 10000 });
}

function getVoxelColor(page) {
  return page.evaluate(() => {
    const mesh = window.voxsymApp?.scene?.voxelMesh;
    if (!mesh || !mesh.instanceColor) return null;
    const arr = mesh.instanceColor.array;
    return { r: arr[0], g: arr[1], b: arr[2] };
  });
}

test('topbar shows Files, Layers, Fields, Simulation, Settings', async ({ page }) => {
  await page.goto('/');
  for (const m of ['files', 'layers', 'fields', 'simulation', 'settings']) {
    await expect(page.locator(`[data-menu="${m}"]`)).toBeVisible();
  }
});

test('files panel shows load simulation data and load simulation buttons', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-menu="files"]');
  await expect(page.locator('#files-panel')).toBeVisible();
  await expect(page.locator('#load-sim-data')).toBeVisible();
  await expect(page.locator('#load-sim')).toBeVisible();
});

test('simulation panel shows Play, Stop, Record, Restart buttons', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-menu="simulation"]');
  await expect(page.locator('#simulation-panel')).toBeVisible();
  for (const id of ['sim-play', 'sim-stop', 'sim-record', 'sim-restart']) {
    await expect(page.locator(`#${id}`)).toBeVisible();
  }
});

test('selecting temperature layer shows plasma heatmap', async ({ page }) => {
  await page.goto('/');
  await waitForVoxelMesh(page);
  const base = await getVoxelColor(page);
  expect(base).not.toBeNull();

  await page.click('[data-menu="layers"]');
  const tempBtn = page.locator('[data-scalar="temperature"]');
  await expect(tempBtn).toBeVisible({ timeout: 10000 });
  await tempBtn.click();

  await page.waitForFunction(
    () => window.voxsymApp?.store?.state?.activeScalar === 'temperature',
    { timeout: 10000 },
  );

  await page.waitForFunction(
    (baseColor) => {
      const mesh = window.voxsymApp?.scene?.voxelMesh;
      if (!mesh || !mesh.instanceColor) return false;
      const arr = mesh.instanceColor.array;
      return (
        Math.abs(arr[0] - baseColor.r) > 0.05 ||
        Math.abs(arr[1] - baseColor.g) > 0.05 ||
        Math.abs(arr[2] - baseColor.b) > 0.05
      );
    },
    base,
    { timeout: 10000 },
  );

  const temp = await getVoxelColor(page);
  expect(temp).not.toBeNull();
});

test('activating vector field shows arrows', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-menu="fields"]');
  const cb = page.locator('[data-vector="electric_field"] input');
  await expect(cb).toBeVisible({ timeout: 10000 });
  await cb.click();

  await page.waitForFunction(
    () => window.voxsymApp?.store?.state?.activeVectors.has('electric_field'),
    { timeout: 10000 },
  );

  await page.waitForFunction(
    () => {
      const app = window.voxsymApp;
      return app?.store?.state?.arrowCount > 0 && app?.scene?.arrowRoot?.children?.length > 0;
    },
    { timeout: 10000 },
  );
});

test('bottom grid/axis toggles control helper visibility', async ({ page }) => {
  await page.goto('/');
  const gridBtn = page.locator('#toggle-grid');
  const axesBtn = page.locator('#toggle-axes');
  await expect(gridBtn).toBeVisible();
  await expect(axesBtn).toBeVisible();

  await gridBtn.click();
  await page.waitForFunction(
    () => window.voxsymApp?.store?.state?.showGrid === false,
    { timeout: 10000 },
  );

  await axesBtn.click();
  await page.waitForFunction(
    () => window.voxsymApp?.store?.state?.showAxes === false,
    { timeout: 10000 },
  );
});

test('selecting base color restores copper-like color', async ({ page }) => {
  await page.goto('/');
  await waitForVoxelMesh(page);
  const base = await getVoxelColor(page);
  expect(base).not.toBeNull();

  await page.click('[data-menu="layers"]');
  const tempBtn = page.locator('[data-scalar="temperature"]');
  const baseBtn = page.locator('[data-scalar="voxel_color"]');
  await expect(tempBtn).toBeVisible({ timeout: 10000 });

  await tempBtn.click();
  await page.waitForFunction(
    () => window.voxsymApp?.store?.state?.activeScalar === 'temperature',
    { timeout: 10000 },
  );

  await baseBtn.click();
  await page.waitForFunction(
    () => window.voxsymApp?.store?.state?.activeScalar === 'voxel_color',
    { timeout: 10000 },
  );

  await page.waitForFunction(
    () => {
      const mesh = window.voxsymApp?.scene?.voxelMesh;
      if (!mesh || !mesh.instanceColor) return false;
      const arr = mesh.instanceColor.array;
      return arr[0] > arr[2] && arr[0] > 0.5;
    },
    { timeout: 10000 },
  );
});
