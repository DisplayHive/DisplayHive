// The My account page: opened by clicking the name in the top bar.

import test, { expect } from './fixtures.js'
import { TEST_ADMIN_USERNAME } from './testAdminCredentials.js'
import { adminUrl } from './urls.js'

test('clicking the name opens the My account page', async ({ page }) => {
  await page.goto(adminUrl)
  await page.locator('[data-testid="current-username"]').click()
  await expect(page).toHaveURL(/\/account$/)
  await expect(page.getByRole('heading', { name: 'My account' })).toBeVisible()
  await expect(page.locator('[data-testid="account-username"]')).toHaveText(TEST_ADMIN_USERNAME)
  await expect(page.locator('[data-testid="passkeys-card"]')).toBeVisible()
  await expect(page.locator('[data-testid="password-card"]')).toBeVisible({ timeout: 10_000 })
})

test('the password form checks its input before asking the server', async ({ page }) => {
  await page.goto(`${adminUrl}/account`)
  const card = page.locator('[data-testid="password-card"]')
  await expect(card).toBeVisible({ timeout: 10_000 })

  await card.locator('[data-testid="account-password-submit"]').click()
  await expect(card.locator('[data-testid="account-password-error"]')).toContainText('required')

  await card.locator('#account-password-current').fill('whatever-current')
  await card.locator('#account-password-new').fill('a-long-enough-new-password')
  await card.locator('#account-password-confirm').fill('something-else-entirely')
  await card.locator('[data-testid="account-password-submit"]').click()
  await expect(card.locator('[data-testid="account-password-error"]')).toContainText('do not match')
})

test('the theme can be chosen on the page', async ({ page }) => {
  await page.goto(`${adminUrl}/account`)
  const theme = page.locator('[data-testid="account-theme"]')
  await expect(theme).toBeVisible({ timeout: 10_000 })
  await theme.getByText('Dark', { exact: true }).click()
  await expect(page.locator('html')).toHaveClass(/dark-mode/, { timeout: 10_000 })
  await theme.getByText('System', { exact: true }).click()
})
