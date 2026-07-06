import { test, expect } from '@playwright/test';
import { startBackend, stopBackend } from './helpers.js';

let backend;

test.beforeAll(async () => {
  backend = await startBackend();
});

test.afterAll(() => {
  stopBackend(backend);
});

test('white background and empty top bar', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('#topbar', { timeout: 10000 });
  await page.waitForSelector('#panel', { timeout: 10000 });

  const topbarText = await page.locator('#topbar').textContent();
  expect(topbarText?.trim() || '').toBe('');

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
