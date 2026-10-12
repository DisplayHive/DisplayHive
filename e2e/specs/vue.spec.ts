import { test, expect } from './fixtures.js'
import { adminUrl } from './urls.js'

test('visits the app root url', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin(page)
  await expect(page.locator('h1')).toHaveText('Dashboard')
})
