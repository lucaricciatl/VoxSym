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
    const mesh = window.voxsymApp.scene.voxelMesh;
    const arr = mesh.instanceColor.array;
    return { r: arr[0], g: arr[1], b: arr[2] };
  });
}

test('selecting temperature layer shows plasma heatmap', async ({ page }) => {
  await page.goto('/');
  const tempBtn = page.locator('[data-scalar="temperature"]');
  await expect(tempBtn).toBeVisible({ timeout: 10000 });

  const base = await getVoxelColor(page);
  await tempBtn.click();

  // Wait until the backend has broadcast a frame with temperature active.
  await page.waitForFunction(
    () => window.voxsymApp?.store?.state?.activeScalar === 'temperature',
    { timeout: 10000 },
  );

  // Wait for the next frame to actually re-render the voxel colors.
  await page.waitForFunction(
    (baseColor) => {
      const mesh = window.voxsymApp.scene.voxelMesh;
      const arr = mesh.instanceColor.array;
      const r = arr[0];
      const g = arr[1];
      const b = arr[2];
      return (
        Math.abs(r - baseColor.r) > 0.05 ||
        Math.abs(g - baseColor.g) > 0.05 ||
        Math.abs(b - baseColor.b) > 0.05
      );
    },
    base,
    { timeout: 10000 },
  );

  const temp = await getVoxelColor(page);
  expect(Math.abs(temp.r - base.r) > 0.05).toBe(true);
});

test('selecting base color restores copper-like color', async ({ page }) => {
  await page.goto('/');
  const tempBtn = page.locator('[data-scalar="temperature"]');
  const baseBtn = page.locator('[data-scalar="voxel_color"]');
  await expect(tempBtn).toBeVisible({ timeout: 10000 });

  const base = await getVoxelColor(page);
  await tempBtn.click();
  await page.waitForFunction(
    () => window.voxsymApp?.store?.state?.activeScalar === 'temperature',
    { timeout: 10000 },
  );

  // Wait for plasma colors to render.
  await page.waitForFunction(
    (baseColor) => {
      const mesh = window.voxsymApp.scene.voxelMesh;
      const arr = mesh.instanceColor.array;
      const r = arr[0];
      const g = arr[1];
      const b = arr[2];
      return (
        Math.abs(r - baseColor.r) > 0.05 ||
        Math.abs(g - baseColor.g) > 0.05 ||
        Math.abs(b - baseColor.b) > 0.05
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

  // Wait for base copper colors to restore.
  await page.waitForFunction(
    () => {
      const mesh = window.voxsymApp.scene.voxelMesh;
      const arr = mesh.instanceColor.array;
      const r = arr[0];
      const b = arr[2];
      return r > b && r > 0.5;
    },
    { timeout: 10000 },
  );

  const colors = await getVoxelColor(page);
  expect(colors.r).toBeGreaterThan(colors.b);
  expect(colors.r).toBeGreaterThan(0.5);
});
