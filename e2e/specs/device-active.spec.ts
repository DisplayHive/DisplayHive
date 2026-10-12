/**
 * E2E tests: activate and deactivate a device via the Devices admin page.
 *
 * Strategy: seed a device directly through the Socket.IO
 * `displayhive:devices:cts:approve_registration` event (same path the admin UI
 * uses), then toggle the ToggleSwitch in the table and assert both the UI
 * state and the toast confirmation.  The device is cleaned up at the end.
 *
 * These tests mutate shared state (DB rows) so they run serially on a single
 * worker with its own isolated database (Option B global-setup).
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Browser } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(45_000)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Navigate to the Devices page with the worker-specific backend URL injected
 * so useSocket.ts connects to the right isolated Flask instance and exposes
 * the socket on window.__displayhive_socket__ for page.evaluate helpers.
 */
async function gotoDevices(page: any, workerBackendUrl: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, workerBackendUrl)
  await page.goto(`${adminUrl}/devices`)
  await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })
}

/**
 * Open a screen page that connects to the worker backend as an adopted device.
 *
 * We inject `localStorage.deviceKey` via addInitScript before navigation so
 * the screen's auth_helper reads it immediately and connects as a real
 * authenticated device (not impersonation).  This ensures the client joins
 * the `device_<key>` room on the server and receives `connection_rejected` /
 * `device_authenticated` events when the admin toggles the active state.
 *
 * We also remove any stale `adoptionToken` so the adoption overlay never
 * appears.
 */
async function openScreenPage(browser: Browser, workerBackendUrl: string, devicekey: string) {
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true })
  const screenPage = await ctx.newPage()

  // Inject localStorage before the page JS runs
  await screenPage.addInitScript((key: string) => {
    try {
      localStorage.setItem('deviceKey', key)
      localStorage.removeItem('adoptionToken')
      ;(window as any).deviceKey = key
    } catch (e) {}
  }, devicekey)

  await screenPage.goto(workerBackendUrl)
  return { ctx, screenPage }
}

/**
 * Seed a device via Socket.IO from within the Playwright page context.
 * Uses `displayhive:devices:cts:approve_registration` — the same event the admin
 * UI sends when adopting a device.  Returns the server-assigned devicekey.
 */
async function seedDevice(page: any, deviceName: string): Promise<string> {
  const token = `e2e-tok-${Math.random().toString(36).slice(2, 10)}`

  const devicekey: string = await page.evaluate(
    ({ token, deviceName }: { token: string; deviceName: string }) => {
      return new Promise<string>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) {
          reject(
            new Error(
              'Socket not available — ensure __DISPLAYHIVE_TEST_BACKEND_URL__ is injected before navigation',
            ),
          )
          return
        }
        const timeout = setTimeout(
          () => reject(new Error('Timed out waiting for registration_approved')),
          10_000,
        )
        socket.once('displayhive:devices:stc:registration_approved', (data: any) => {
          clearTimeout(timeout)
          if (data?.success && data?.devicekey) resolve(data.devicekey)
          else reject(new Error(`registration_approved failed: ${JSON.stringify(data)}`))
        })
        socket.emit('displayhive:devices:cts:approve_registration', {
          token,
          device_name: deviceName,
        })
      })
    },
    { token, deviceName },
  )

  return devicekey
}

/**
 * Delete a test device by locating its table row and confirming deletion.
 */
async function deleteDeviceByRow(page: any, deviceName: string) {
  const row = page.locator('tr', { hasText: deviceName })
  await expect(row).toHaveCount(1, { timeout: 5_000 })
  await row.locator('button[title="Delete"]').click()

  const confirmMsg = page.getByText(`Are you sure you want to delete device "${deviceName}"?`)
  await expect(confirmMsg).toBeVisible({ timeout: 5_000 })

  const acceptBtn = page.getByRole('button', { name: /^(Yes|Confirm|Delete|OK|Accept)$/i })
  if ((await acceptBtn.count()) > 0) {
    await acceptBtn.first().click()
  } else {
    await page
      .locator(
        '.p-confirm-dialog .p-button-danger, .p-confirm-dialog .p-confirm-dialog-accept, button.p-button-danger',
      )
      .first()
      .click()
  }

  await expect(page.getByText(deviceName)).toHaveCount(0, { timeout: 10_000 })
}

/** Assert the ToggleSwitch state for a given table row (checked or unchecked). */
async function expectToggle(row: any, checked: boolean) {
  const input = row.locator('.p-toggleswitch input[type="checkbox"]')
  if ((await input.count()) > 0) {
    if (checked) {
      await expect(input).toBeChecked({ timeout: 5_000 })
    } else {
      await expect(input).not.toBeChecked({ timeout: 5_000 })
    }
  } else {
    // Fallback for PrimeVue versions that render role="switch" without a checkbox input
    await expect(row.locator('[role="switch"]')).toHaveAttribute(
      'aria-checked',
      checked ? 'true' : 'false',
      { timeout: 5_000 },
    )
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe('Device activate / deactivate', () => {
  // Unique name and key shared across the serial steps
  const deviceName = `e2e-active-${Math.random().toString(36).slice(2, 8)}`
  let devicekey = ''

  test('seed device and verify it appears in devices list as active', async ({
    page,
    backendUrl,
  }) => {
    console.log('[device-active.spec] init socket handlers')
    await gotoDevices(page, backendUrl)

    // Seed the device via socket — server pushes updated list to admins room
    devicekey = await seedDevice(page, deviceName)

    // Row must appear in the table (socket push updates the reactive list)
    const row = page.locator('tr', { hasText: deviceName })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // is_active defaults to true on creation
    await expectToggle(row, true)
  })

  test('deactivate device — toggle turns off, screen shows deactivation overlay', async ({
    page,
    backendUrl,
    browser,
  }) => {
    console.log('[device-active.spec] init socket handlers')
    await gotoDevices(page, backendUrl)

    const row = page.locator('tr', { hasText: deviceName })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // Open a screen page connected as the seeded device so we can observe the
    // deactivation overlay appearing when the admin toggles the device off.
    const { ctx: screenCtx, screenPage } = await openScreenPage(browser, backendUrl, devicekey)

    // Click the ToggleSwitch to deactivate
    await row.locator('.p-toggleswitch').first().click()

    // Admin UI: toast must confirm deactivation
    await expect(page.locator('.p-toast')).toContainText(/deactivated/i, { timeout: 8_000 })

    // Admin UI: toggle must now be off
    await expectToggle(row, false)

    // Admin UI: row must still be present — deactivation ≠ deletion
    await expect(row).toBeVisible()

    // Screen: #deactivated-overlay must appear with the "Device Deactivated" message.
    // The overlay stays in the DOM and toggles via opacity (not display:none), so
    // toBeVisible() would trivially pass regardless of state — assert on the
    // "show" class instead (see adoption.spec.ts for the same pattern).
    await expect(screenPage.locator('#deactivated-overlay')).toHaveClass(/show/, { timeout: 15_000 })
    await expect(screenPage.locator('#deactivated-overlay')).toContainText('Device Deactivated')

    await screenCtx.close()
  })

  test('reactivate device — toggle turns back on, screen deactivation overlay disappears', async ({
    page,
    backendUrl,
    browser,
  }) => {
    console.log('[device-active.spec] init socket handlers')
    await gotoDevices(page, backendUrl)

    const row = page.locator('tr', { hasText: deviceName })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // Open a screen page — at this point the device is still inactive (from
    // the previous step), so the overlay should appear immediately on connect.
    const { ctx: screenCtx, screenPage } = await openScreenPage(browser, backendUrl, devicekey)
    await expect(screenPage.locator('#deactivated-overlay')).toHaveClass(/show/, { timeout: 15_000 })

    // Click to reactivate in admin UI
    await row.locator('.p-toggleswitch').first().click()

    // Admin UI: toast must confirm activation
    await expect(page.locator('.p-toast')).toContainText(/activated/i, { timeout: 8_000 })

    // Admin UI: toggle must be on again
    await expectToggle(row, true)

    // Screen: the server sends `displayhive:devices:stc:device_authenticated` which
    // triggers hideDeactivationOverlay() — overlay must disappear. The overlay
    // stays in the DOM and toggles via opacity, so toBeHidden() never succeeds —
    // assert on the class instead (see adoption.spec.ts for the same pattern).
    await expect(screenPage.locator('#deactivated-overlay')).not.toHaveClass(/show/, { timeout: 40_000 })

    await screenCtx.close()
  })

  test('cleanup — delete the test device', async ({ page, backendUrl }) => {
    console.log('[device-active.spec] init socket handlers')
    await gotoDevices(page, backendUrl)
    await deleteDeviceByRow(page, deviceName)
  })
})
