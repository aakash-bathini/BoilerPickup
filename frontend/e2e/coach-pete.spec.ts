import { test, expect } from '@playwright/test';

/**
 * Coach Pete E2E tests.
 * Coach Pete only renders when logged in. Use E2E_TEST_EMAIL + E2E_TEST_PASSWORD
 * to run authenticated tests (create user via backend first).
 */
test.describe('Coach Pete (unauthenticated)', () => {
  test('landing page loads', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('body')).toBeVisible();
  });
});

test.describe('Coach Pete (authenticated)', () => {
  const testEmail = process.env.E2E_TEST_EMAIL;
  const testPassword = process.env.E2E_TEST_PASSWORD;

  test.beforeEach(async ({ page }) => {
    if (!testEmail || !testPassword) {
      test.skip();
    }
    await page.goto('/login');
    await page.getByLabel(/email/i).fill(testEmail);
    await page.getByLabel(/password/i).fill(testPassword);
    await page.getByRole('button', { name: /log in|sign in/i }).click();
    await page.waitForURL(/dashboard|/);
  });

  test('Coach Pete mascot visible when logged in', async ({ page }) => {
    await page.goto('/dashboard');
    const peteButton = page.locator('button[title="Coach Pete"]');
    await expect(peteButton).toBeVisible({ timeout: 5000 });
  });

  test('Coach Pete panel opens and has quick actions', async ({ page }) => {
    await page.goto('/dashboard');
    await page.locator('button[title="Coach Pete"]').click();
    await expect(page.getByText('Coach Pete')).toBeVisible();
    await expect(page.getByText('Find teammate')).toBeVisible();
    await expect(page.getByText('Weather')).toBeVisible();
  });
});
