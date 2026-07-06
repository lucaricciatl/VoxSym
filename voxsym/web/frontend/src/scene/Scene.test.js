import { test, expect } from '@playwright/test';

test('scene renders white background', async ({ page }) => {
  await page.goto('/');
  const canvas = page.locator('canvas');
  await expect(canvas).toHaveCount(1);
  const bg = await page.evaluate(() => {
    const app = window.voxsymApp;
    return app.scene.scene.background.getHexString();
  });
  expect(bg).toBe('ffffff');
});

test('topbar is empty', async ({ page }) => {
  await page.goto('/');
  const topbar = page.locator('#topbar');
  await expect(topbar).toHaveCount(1);
  const text = await topbar.evaluate((el) => el.textContent);
  expect(text.trim()).toBe('');
});
