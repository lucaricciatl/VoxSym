import { test, expect } from '@playwright/test';
import { startBackend, stopBackend } from './helpers.js';

let backend;

test.beforeAll(async () => {
  backend = await startBackend();
});

test.afterAll(async () => {
  await stopBackend(backend);
});

function waitForOpacity(page, target) {
  return page.waitForFunction(
    (tgt) => {
      const m = window.voxsymApp?.scene?.voxelMesh?.material;
      const s = window.voxsymApp?.store?.state;
      return m?.opacity === tgt && s?.opacity === tgt;
    },
    target,
    { timeout: 3000 }
  );
}

test('opacity slider updates voxel transparency after WS round-trip', async ({ page }) => {
  await page.goto('/');
  await page.waitForFunction(() => window.voxsymApp?.store?.state?.connected, null, { timeout: 5000 });

  // Open Layers panel
  await page.click('[data-menu="layers"]');
  await expect(page.locator('#opacity')).toBeVisible();

  // Use fill + explicit input event for reliable slider updates.
  await page.locator('#opacity').fill('0.25');
  await page.locator('#opacity').dispatchEvent('input');

  await waitForOpacity(page, 0.25);

  await page.locator('#opacity').fill('1');
  await page.locator('#opacity').dispatchEvent('input');
  await waitForOpacity(page, 1.0);
});
