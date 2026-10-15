// Passkeys (WebAuthn): add one in "My passkeys", sign out, sign in with it — no username, no password.
// Chromium's virtual authenticator plays the device; other browsers have no such test hook.

import test, { expect } from './fixtures.js'
import { TEST_ADMIN_USERNAME } from './testAdminCredentials.js'
import { adminUrl } from './urls.js'

test.describe.configure({ mode: 'serial' })
test.setTimeout(60_000)

test('add a passkey, sign out and sign in with it', async ({ page, browserName }) => {
  test.skip(browserName !== 'chromium', 'needs the virtual authenticator of Chromium')

  const cdp = await page.context().newCDPSession(page)
  await cdp.send('WebAuthn.enable')
  await cdp.send('WebAuthn.addVirtualAuthenticator', {
    options: {
      protocol: 'ctap2',
      transport: 'internal',
      hasResidentKey: true,
      hasUserVerification: true,
      isUserVerified: true,
      automaticPresenceSimulation: true,
    },
  })

  await page.goto(adminUrl)
  await expect(page.locator('[data-testid="current-username"]')).toContainText(TEST_ADMIN_USERNAME, { timeout: 10_000 })

  // Add one (on the My account page, opened by clicking the name in the top bar)
  await page.locator('[data-testid="current-username"]').click()
  await expect(page).toHaveURL(/\/account$/)
  const dialog = page.locator('[data-testid="passkeys-card"]')
  await expect(dialog).toBeVisible()
  const name = `e2e-key-${Math.random().toString(36).slice(2, 6)}`
  await dialog.getByPlaceholder('Name, e.g. Work laptop').fill(name)
  await dialog.locator('[data-testid="passkey-add"]').click()
  await expect(dialog.locator('[data-testid="passkey-list"]')).toContainText(name, { timeout: 10_000 })

  // Rename it
  await dialog.getByTitle('Rename').click()
  await dialog.getByLabel('Passkey name').fill(`${name}-renamed`)
  await dialog.getByTitle('Save the name').click()
  await expect(dialog.locator('[data-testid="passkey-list"]')).toContainText(`${name}-renamed`)

  // Sign out: the login page offers the passkey
  await page.locator('[data-testid="logout-button"]').click()
  const passkeyButton = page.locator('[data-testid="login-passkey"]')
  await expect(passkeyButton).toBeVisible({ timeout: 10_000 })

  // Sign in with it: no username, no password
  await passkeyButton.click()
  await expect(page.locator('[data-testid="current-username"]')).toContainText(TEST_ADMIN_USERNAME, { timeout: 15_000 })

  // Clean up: remove it again
  await page.locator('[data-testid="current-username"]').click()
  await expect(dialog).toBeVisible()
  await dialog.getByTitle('Remove this passkey').click()
  await page.getByRole('button', { name: /Delete|Yes|OK|Remove/i }).last().click()
  await expect(dialog.locator('[data-testid="passkey-list"]')).toHaveCount(0, { timeout: 10_000 })
})
