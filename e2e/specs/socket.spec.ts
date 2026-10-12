import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'

test('socket connection is established', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin(page)

  // Wait for the header connection status to indicate connected
  const status = page.locator('.connection-status')
  await expect(status).toHaveText(/Connected/, { timeout: 5000 })
  await expect(status).toHaveClass(/connected/)
})

test('disconnect overlay appears when socket disconnects', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin(page)

  // Wait until the socket is connected before testing disconnection
  await expect(page.locator('.connection-status')).toHaveText(/Connected/, { timeout: 5000 })
  await expect(page.locator('[data-testid="disconnect-overlay"]')).not.toBeVisible()

  // Programmatically disconnect the socket
  await page.evaluate(() => (window as any).__displayhive_socket__.disconnect())

  // Overlay must become visible
  await expect(page.locator('[data-testid="disconnect-overlay"]')).toBeVisible({ timeout: 5000 })
  await expect(page.locator('[data-testid="disconnect-overlay"]')).toContainText(
    'No connection to Server',
  )
  // Header indicator must also reflect disconnected state
  await expect(page.locator('.connection-status')).toHaveText(/Disconnected/)
})

test('page reloads when connection is recovered', async ({ page, loginAsAdmin, backendUrl }) => {
  await loginAsAdmin(page)

  // Wait until connected
  await expect(page.locator('.connection-status')).toHaveText(/Connected/, { timeout: 5000 })

  // Navigate to a specific route so we can confirm the URL survives the reload
  await page.goto(`${adminUrl}/screens`)
  await expect(page.locator('.connection-status')).toHaveText(/Connected/, { timeout: 5000 })

  // Disconnect
  await page.evaluate(() => (window as any).__displayhive_socket__.disconnect())
  await expect(page.locator('[data-testid="disconnect-overlay"]')).toBeVisible({ timeout: 5000 })

  // Wait past the 3-second grace period so the watcher marks this as a real
  // disconnect (not a transient polling hiccup) before we reconnect.
  await page.waitForTimeout(3_500)

  // Reconnect — this should trigger window.location.reload() in the Vue watcher
  await Promise.all([
    page.waitForNavigation({ timeout: 15_000 }),
    page.evaluate(() => (window as any).__displayhive_socket__.connect()),
  ])

  // After the reload the app reconnects; overlay must not be present
  await expect(page.locator('.connection-status')).toHaveText(/Connected/, { timeout: 10_000 })
  await expect(page.locator('[data-testid="disconnect-overlay"]')).not.toBeVisible()
})

export {}
