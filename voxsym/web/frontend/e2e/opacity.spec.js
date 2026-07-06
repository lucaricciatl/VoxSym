import { test, expect } from '@playwright/test';
import { startBackend, stopBackend } from './helpers.js';

let backend;

test.beforeAll(async () => {
  backend = await startBackend();
});

test.afterAll(() => {
  stopBackend(backend);
});

test('opacity slider changes mesh opacity in real time', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('#opacity', { timeout: 10000 });
  const input = page.locator('#opacity');
  await input.fill('0.2');
  await input.dispatchEvent('input');
  await page.waitForTimeout(150);

  const opacity = await page.evaluate(() => {
    const mesh = window.voxsymApp?.scene?.voxelMesh;
    return mesh?.material?.opacity;
  });
  expect(opacity).toBeCloseTo(0.2, 1);
});
