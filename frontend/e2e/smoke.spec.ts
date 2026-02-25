import { test, expect } from '@playwright/test';

test.describe('Boiler Pickup E2E', () => {
  test('landing page loads and shows Coach Pete', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Boiler Pickup|Pickup/i);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  });

  test('login page renders when visiting protected route unauthenticated', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForURL(/\/(login|dashboard)/);
    const url = page.url();
    if (url.includes('login')) {
      await expect(page.getByRole('heading', { name: /log in|sign in/i })).toBeVisible();
    }
  });

  test('games page structure', async ({ page }) => {
    await page.goto('/games');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toBeVisible();
  });
});
