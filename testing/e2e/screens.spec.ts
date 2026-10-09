/**
 * E2E tests for the Screens admin page.
 *
 * Covered:
 *  1. Add Screen dialog: filling the form and submitting creates a row in the table
 *  2. Online / offline filter tags hide and reveal matching rows
 *
 * Strategy:
 *  - Test 1 creates a screen via the UI; tests 2 seeds a device+assigns it to
 *    the screen so the device can come online. The screen is cleaned up at the end.
 *  - A real screen page (localStorage injection) is opened once for the filter
 *    test and closed during cleanup to cut context overhead.
 *  - All tests run serially on the same worker / isolated DB.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Browser, BrowserContext, Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(45_000)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function gotoScreens(page: Page, workerBackendUrl: string) {
  console.log('[screens.spec] gotoScreens')
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, workerBackendUrl)
  await page.goto(`${adminUrl}/screens`)
  await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })
}

async function gotoDevices(page: Page, workerBackendUrl: string) {
  console.log('[screens.spec] gotoDevices')
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, workerBackendUrl)
  await page.goto(`${adminUrl}/devices`)
  await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })
}

/** Seed a device via socket and return the server-assigned devicekey. */
async function seedDevice(page: Page, deviceName: string): Promise<string> {
  const token = `e2e-scr-${Math.random().toString(36).slice(2, 10)}`

  return page.evaluate(
    ({ token, deviceName }: { token: string; deviceName: string }) =>
      new Promise<string>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) {
          reject(new Error('Socket not available'))
          return
        }
        const t = setTimeout(
          () => reject(new Error('Timed out waiting for registration_approved')),
          10_000,
        )
        socket.once('displayhive:devices:stc:registration_approved', (data: any) => {
          clearTimeout(t)
          if (data?.success && data?.devicekey) resolve(data.devicekey)
          else reject(new Error(`registration_approved failed: ${JSON.stringify(data)}`))
        })
        socket.emit('displayhive:devices:cts:approve_registration', { token, device_name: deviceName })
      }),
    { token, deviceName },
  )
}

/** Open the screen client as a real (non-impersonation) adopted device. */
async function openScreenPage(browser: Browser, workerBackendUrl: string, devicekey: string) {
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true })
  const screenPage = await ctx.newPage()
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

async function deleteDeviceByRow(page: Page, deviceName: string) {
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

async function deleteScreenByRow(page: Page, screenName: string) {
  const row = page.locator('tr', { hasText: screenName })
  await expect(row).toHaveCount(1, { timeout: 5_000 })
  await row.locator('button[title="Delete"]').click()
  const confirmMsg = page.getByText(`Are you sure you want to delete screen "${screenName}"?`)
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
  await expect(page.getByText(screenName)).toHaveCount(0, { timeout: 10_000 })
}

// ---------------------------------------------------------------------------
// Suite state shared across serial tests
// ---------------------------------------------------------------------------

test.describe('Screens page', () => {
  const screenName = `e2e-scr-${Math.random().toString(36).slice(2, 8)}`
  const deviceName = `e2e-scrdev-${Math.random().toString(36).slice(2, 8)}`
  let devicekey = ''

  // Screen context reused across filter test, closed in cleanup
  let screenCtx: BrowserContext | null = null

  // ---------------------------------------------------------------------------
  // 1. Add Screen via dialog
  // ---------------------------------------------------------------------------

  test('add screen dialog creates a new row in the table', async ({ page, backendUrl }) => {
    console.log('[screens.spec] init socket handlers')
    await gotoScreens(page, backendUrl)

    // Click the "Add Screen" button to open the create dialog
    await page.getByRole('button', { name: 'Add Screen' }).click()

    // Dialog should be visible with the create form
    const dialog = page.locator('.p-dialog', { hasText: 'Add Screen' })
    await expect(dialog).toBeVisible({ timeout: 5_000 })

    // Fill in the screen name (required)
    await dialog.locator('#create-name').fill(screenName)

    // Submit
    await dialog.getByRole('button', { name: 'Create' }).click()

    // Dialog closes and a success toast appears
    await expect(dialog).toBeHidden({ timeout: 5_000 })
    await expect(page.locator('.p-toast')).toContainText(/created/i, { timeout: 8_000 })

    // The new row appears in the table
    const row = page.locator('tr', { hasText: screenName })
    await expect(row).toBeVisible({ timeout: 10_000 })
  })

  // ---------------------------------------------------------------------------
  // 2. Online / offline filter — seed a device, assign it to the screen,
  //    open a real screen page so it comes online, then toggle filter tags
  // ---------------------------------------------------------------------------

  test('online/offline filter tags hide and reveal matching rows', async ({
    page,
    backendUrl,
    browser,
  }) => {
    console.log('[screens.spec] init socket handlers')

    // Seed a device on the Devices page (socket available there)
    await gotoDevices(page, backendUrl)
    devicekey = await seedDevice(page, deviceName)

    // Assign the device to the screen we created in test 1 via the Edit dialog
    const devRow = page.locator('tr', { hasText: deviceName })
    await expect(devRow).toBeVisible({ timeout: 10_000 })
    await devRow.locator('button[title="Assign to Screen"]').click()

    const editDialog = page.locator('.p-dialog', { hasText: 'Assign to Screen' })
    await expect(editDialog).toBeVisible({ timeout: 5_000 })

    // Select the screen in the dropdown
    const screenSelect = editDialog.locator('#assign-screen')
    await screenSelect.click()
    // Pick option matching screenName
    await page.locator('.p-select-option', { hasText: screenName }).click()
    await editDialog.getByRole('button', { name: 'Save' }).click()
    await expect(editDialog).toBeHidden({ timeout: 5_000 })

    // Open the screen client as the real device so it goes online
    const opened = await openScreenPage(browser, backendUrl, devicekey)
    screenCtx = opened.ctx

    // Navigate to the Screens page
    await gotoScreens(page, backendUrl)

    const scrRow = page.locator('tr', { hasText: screenName })
    await expect(scrRow).toBeVisible({ timeout: 10_000 })

    // Wait for the screen to become online (device connected)
    const statusTag = scrRow.locator('.p-tag')
    await expect(statusTag).toContainText('Online', { timeout: 15_000 })

    // --- Hide online screens ---
    const onlineTag = page
      .locator('.clickable-tag')
      .filter({ hasText: /Online/ })
      .first()
    await onlineTag.click()
    // Our screen is online so it should be hidden
    await expect(scrRow).toBeHidden({ timeout: 5_000 })

    // --- Restore online screens ---
    await onlineTag.click()
    await expect(scrRow).toBeVisible({ timeout: 5_000 })

    // --- Hide offline screens ---
    const offlineTag = page
      .locator('.clickable-tag')
      .filter({ hasText: /Offline/ })
      .first()
    await offlineTag.click()
    // Our screen is online so it should still be visible
    await expect(scrRow).toBeVisible({ timeout: 3_000 })

    // Restore
    await offlineTag.click()
  })

  // ---------------------------------------------------------------------------
  // 3. Cleanup: delete device and screen
  // ---------------------------------------------------------------------------

  test('cleanup: delete test device and screen', async ({ page, backendUrl }) => {
    console.log('[screens.spec] init socket handlers')
    if (screenCtx) {
      await screenCtx.close()
      screenCtx = null
    }

    // Delete device first (unlinks the screen assignment)
    await gotoDevices(page, backendUrl)
    if (devicekey) {
      await deleteDeviceByRow(page, deviceName)
    }

    // Delete screen
    await gotoScreens(page, backendUrl)
    await deleteScreenByRow(page, screenName)
  })
})
