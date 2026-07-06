import { test, expect } from '@playwright/test';
import { startBackend, stopBackend } from './helpers.js';

let backend;

test.beforeAll(async () => {
  backend = await startBackend();
});

test.afterAll(() => {
  stopBackend(backend);
});

test('white background and top bar items', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('#topbar', { timeout: 10000 });

  for (const label of ['Files', 'Layers', 'Fields', 'Settings']) {
    await expect(page.locator(`#topbar button:has-text("${label}")`)).toBeVisible();
  }

  const bg = await page.evaluate(() => {
    const body = document.body;
    const topbar = document.getElementById('topbar');
    return {
      bodyBg: window.getComputedStyle(body).backgroundColor,
      topbarBg: window.getComputedStyle(topbar).backgroundColor,
    };
  });
  expect(bg.bodyBg).toBe('rgb(255, 255, 255)');
  expect(bg.topbarBg).toBe('rgb(255, 255, 255)');
});
