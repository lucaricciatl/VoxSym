import { test, expect } from '@playwright/test';
import { startBackend, stopBackend } from './helpers.js';

let backend;

test.beforeAll(async () => {
  backend = await startBackend();
});

test.afterAll(() => {
  stopBackend(backend);
});

function getVoxelColor(page) {
  return page.evaluate(() => {
    const mesh = window.voxsymApp?.scene?.voxelMesh;
    if (!mesh || !mesh.instanceColor) return null;
    const arr = mesh.instanceColor.array;
    return { r: arr[0], g: arr[1], b: arr[2] };
  });
}

async function waitForVoxelColor(page) {
  await page.waitForFunction(() => {
    const mesh = window.voxsymApp?.scene?.voxelMesh;
    return mesh && mesh.instanceColor;
  }, { timeout: 10000 });
  return getVoxelColor(page);
}

function getActiveScalar(page) {
  return page.evaluate(() => window.voxsymApp?.store?.state?.activeScalar);
}

function getOpacity(page) {
  return page.evaluate(() => window.voxsymApp?.scene?.voxelMesh?.material?.opacity);
}

test('topbar shows Files, Layers, Fields, Settings', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('[data-menu="files"]')).toBeVisible();
  await expect(page.locator('[data-menu="layers"]')).toBeVisible();
  await expect(page.locator('[data-menu="fields"]')).toBeVisible();
  await expect(page.locator('[data-menu="settings"]')).toBeVisible();
});

test('layers menu shows opacity and scalar layer cards', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-menu="layers"]');
  await expect(page.locator('#layers-panel')).toBeVisible();
  await expect(page.locator('#opacity')).toBeVisible();
  await expect(page.locator('[data-scalar="temperature"]')).toBeVisible();
});

test('fields menu opens the same layer panel', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-menu="fields"]');
  await expect(page.locator('#layers-panel')).toBeVisible();
  await expect(page.locator('[data-vector="electric_field"]')).toBeVisible();
});

test('settings menu opens settings panel', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-menu="settings"]', { timeout: 10000 });
  await page.click('[data-menu="settings"]');
  await expect(page.locator('#settings-panel')).toBeVisible({ timeout: 10000 });
});

test('selecting temperature layer shows plasma heatmap', async ({ page }) => {
  await page.goto('/');
  const tempBtn = page.locator('[data-scalar="temperature"]');
  await expect(tempBtn).toBeVisible({ timeout: 10000 });

  const base = await waitForVoxelColor(page);
  expect(base).not.toBeNull();
  await tempBtn.click();

  await page.waitForFunction(
    () => window.voxsymApp?.store?.state?.activeScalar === 'temperature',
    { timeout: 10000 },
  );

  await page.waitForFunction(
    (baseColor) => {
      const mesh = window.voxsymApp.scene.voxelMesh;
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
  expect(Math.abs(temp.r - base.r) > 0.05).toBe(true);
});

test('opacity slider changes mesh opacity in real time', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('#opacity', { timeout: 10000 });
  const input = page.locator('#opacity');
  await input.fill('0.2');
  await input.dispatchEvent('input');
  await page.waitForTimeout(150);
  expect(await getOpacity(page)).toBeCloseTo(0.2, 1);
});

test('activating vector field shows arrows', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-menu="fields"]');
  const cb = page.locator('[data-vector="electric_field"] input');
  await expect(cb).toBeVisible();
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
  await page.waitForFunction(
    () => window.voxsymApp?.scene?._gridHelper?.visible === false,
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
  const tempBtn = page.locator('[data-scalar="temperature"]');
  const baseBtn = page.locator('[data-scalar="voxel_color"]');
  await expect(tempBtn).toBeVisible({ timeout: 10000 });

  const base = await waitForVoxelColor(page);
  expect(base).not.toBeNull();
  await tempBtn.click();
  await page.waitForFunction(
    () => window.voxsymApp?.store?.state?.activeScalar === 'temperature',
    { timeout: 10000 },
  );

  await page.waitForFunction(
    (baseColor) => {
      const mesh = window.voxsymApp.scene.voxelMesh;
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

  await baseBtn.click();
  await page.waitForFunction(
    () => window.voxsymApp?.store?.state?.activeScalar === 'voxel_color',
    { timeout: 10000 },
  );

  await page.waitForFunction(
    () => {
      const mesh = window.voxsymApp.scene.voxelMesh;
      if (!mesh || !mesh.instanceColor) return false;
      const arr = mesh.instanceColor.array;
      const r = arr[0];
      const b = arr[2];
      return r > b && r > 0.5;
    },
    { timeout: 10000 },
  );

  const colors = await getVoxelColor(page);
  expect(colors).not.toBeNull();
  expect(colors.r).toBeGreaterThan(colors.b);
  expect(colors.r).toBeGreaterThan(0.5);
});
