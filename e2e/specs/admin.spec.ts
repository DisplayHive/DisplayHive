import { test, expect } from './fixtures.js'
import { adminUrl } from './urls.js'

test.describe('Admin UI smoke', () => {
  test('loads main app and shows header', async ({ page, loginAsAdmin }) => {
    await loginAsAdmin(page)

    // Wait for app root
    await page.waitForSelector('#app')

    // Check for a header element or the presence of the Menubar
    const header = await page.locator('.app-header')
    await expect(header).toBeVisible()

    // If logo exists, it should be visible
    const logo = page.locator('.header-logo')
    if ((await logo.count()) > 0) {
      await expect(logo).toBeVisible()
    }
  })
})
