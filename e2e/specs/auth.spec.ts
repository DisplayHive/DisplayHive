// Smoke test for the `page` fixture's automatic admin-session seeding
// (see fixtures.ts). For the login *form* itself (wrong password, logout,
// session restore), see login.spec.ts.

import test, { expect } from './fixtures.js'
import type { Page } from '@playwright/test'

test('admin session is authenticated via the page fixture', async ({
  page,
  loginAsAdmin,
}: {
  page: Page
  loginAsAdmin: (page: Page) => Promise<void>
}) => {
  await loginAsAdmin(page)

  // The helper navigates to the admin SPA; ensure it initialized past the login form.
  await expect(page.locator('#app')).toBeVisible()
  await expect(page.locator('[data-testid="current-username"]')).toBeVisible()

  // If login caused presence of a connected indicator, assert it (example)
  const conn = page.locator('.connection-status')
  await expect(conn).toBeVisible()
})
