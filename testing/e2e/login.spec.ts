// Exercises the actual login form UI: the `page` fixture pre-seeds a valid
// admin session for every test (see fixtures.ts), so these tests explicitly
// clear it first to force the LoginView to render.

import test, { expect } from './fixtures.js'
import { TEST_ADMIN_USERNAME, TEST_ADMIN_PASSWORD } from './testAdminCredentials.js'
import { adminUrl } from './urls.js'

test.describe('Login form', () => {
  test.beforeEach(async ({ page }) => {
    // Takes away the session the fixture seeded (the cookie and the "signed in" hint) —
    // the page loads unauthenticated from here on. (The init script runs after the
    // fixture's own, so it also wins over the hint it seeded.)
    await page.context().clearCookies()
    await page.addInitScript(() => {
      ;(globalThis as any).localStorage.removeItem('displayhive_admin_session')
    })
  })

  test('shows the login form when not authenticated', async ({ page }) => {
    await page.goto(adminUrl)
    await expect(page.locator('[data-testid="login-username"]')).toBeVisible()
    await expect(page.locator('[data-testid="login-password"]')).toBeVisible()
  })

  test('wrong password shows an error and does not log in', async ({ page }) => {
    await page.goto(adminUrl)
    await page.locator('[data-testid="login-username"] input, [data-testid="login-username"]').fill(
      TEST_ADMIN_USERNAME,
    )
    await page.locator('[data-testid="login-password"] input').fill('definitely-wrong-password')
    await page.locator('[data-testid="login-submit"]').click()

    await expect(page.locator('[data-testid="login-error"]')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('[data-testid="login-username"]')).toBeVisible()
  })

  test('correct credentials log in and show the app with the username in the top bar', async ({
    page,
  }) => {
    await page.goto(adminUrl)
    await page.locator('[data-testid="login-username"] input, [data-testid="login-username"]').fill(
      TEST_ADMIN_USERNAME,
    )
    await page.locator('[data-testid="login-password"] input').fill(TEST_ADMIN_PASSWORD)
    await page.locator('[data-testid="login-submit"]').click()

    await expect(page.locator('.app-header')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('[data-testid="current-username"]')).toContainText(TEST_ADMIN_USERNAME)
  })

  test('logout returns to the login form', async ({ page }) => {
    await page.goto(adminUrl)
    await page.locator('[data-testid="login-username"] input, [data-testid="login-username"]').fill(
      TEST_ADMIN_USERNAME,
    )
    await page.locator('[data-testid="login-password"] input').fill(TEST_ADMIN_PASSWORD)
    await page.locator('[data-testid="login-submit"]').click()
    await expect(page.locator('[data-testid="logout-button"]')).toBeVisible({ timeout: 10000 })

    await page.locator('[data-testid="logout-button"]').click()

    await expect(page.locator('[data-testid="login-username"]')).toBeVisible({ timeout: 5000 })
    // Nothing of the session is left: not the hint, and the server removed the cookie.
    const hint = await page.evaluate(() =>
      (globalThis as any).localStorage.getItem('displayhive_admin_session'),
    )
    expect(hint).toBeNull()
    const cookies = await page.context().cookies()
    expect(cookies.filter((c) => c.name.endsWith('dh_session'))).toEqual([])
  })
})
