import { test, expect } from '@playwright/test';
import { Store } from './Store.js';

test('scalar layers are mutually exclusive', async () => {
  const s = new Store();
  expect(s.state.activeScalar).toBe('voxel_color');
  s.setActiveScalar('temperature');
  expect(s.state.activeScalar).toBe('temperature');
  s.setActiveScalar('material');
  expect(s.state.activeScalar).toBe('material');
});

test('vectors can be toggled independently', async () => {
  const s = new Store();
  s.setVectorActive('electric_field', true);
  s.setVectorActive('current', true);
  expect(s.state.activeVectors.has('electric_field')).toBe(true);
  expect(s.state.activeVectors.has('current')).toBe(true);
  s.setVectorActive('electric_field', false);
  expect(s.state.activeVectors.has('electric_field')).toBe(false);
});

test('opacity is clamped to [0,1]', async () => {
  const s = new Store();
  s.setOpacity(2);
  expect(s.state.opacity).toBe(1);
  s.setOpacity(-0.5);
  expect(s.state.opacity).toBe(0);
  s.setOpacity(0.5);
  expect(s.state.opacity).toBe(0.5);
});

test('layer panel buttons and opacity slider exist', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('[data-scalar="temperature"]')).toHaveCount(1);
  await expect(page.locator('[data-vector="electric_field"] input')).toHaveCount(1);
  await expect(page.locator('#opacity')).toHaveCount(1);
});
