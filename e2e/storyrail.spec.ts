import { test, expect } from '@playwright/test';

test('StoryRail preview is reachable', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('body')).toBeVisible();
});
