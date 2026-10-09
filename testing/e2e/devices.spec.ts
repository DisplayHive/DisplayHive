/**
 * E2E tests for the Devices admin page.
 *
 * Covered:
 *  1.  Text filter narrows the table
 *  2.  Device-key tooltip appears on hover over the key icon
 *  3.  Copy-key button shows toast "Device key copied to clipboard"
 *  4.  Edit dialog renames a device
 *  5.  Edit dialog assigns a screen; Screen column updates
 *  6.  Refresh button reloads the device list
 *  7.  The "Play" (impersonation) button opens a new tab showing the screen
 *  8.  Online / offline filter tags hide and reveal rows
 *  9.  "Locate Device" button toggles the find state on a connected screen
 *  10. Locate Device button is absent when the device is offline
 *
 * Strategy:
 *  - Seed one device via Socket.IO before the suite and keep it for all tests.
 *  - Open a real screen page (localStorage injection) once and reuse it for
 *    tests 8 and 9, avoiding repeated context creation.
 *  - All tests run serially on the same worker / isolated DB.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Browser, BrowserContext, Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(45_000)

// ---------------------------------------------------------------------------
// Helpers (shared with device-active.spec.ts pattern)
// ---------------------------------------------------------------------------

async function gotoDevices(page: Page, workerBackendUrl: string) {
  console.log('[devices.spec] gotoDevices')
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, workerBackendUrl)
  await page.goto(`${adminUrl}/devices`)
  await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })
}

/** Seed a device and return its devicekey. */
async function seedDevice(page: Page, deviceName: string): Promise<string> {
  const token = `e2e-dev-${Math.random().toString(36).slice(2, 10)}`

  const devicekey: string = await page.evaluate(
    ({ token, deviceName }: { token: string; deviceName: string }) => {
      return new Promise<string>((resolve, reject) => {
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
      })
    },
    { token, deviceName },
  )

  return devicekey
}

/**
 * Open a screen page as a real adopted device by injecting localStorage.deviceKey
 * before navigation so the client joins device_<key> room (non-impersonation).
 */
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

/** Create a screen via socket and return its name. */
async function seedScreen(page: Page, screenName: string): Promise<void> {
  await page.evaluate(
    ({ screenName }: { screenName: string }) =>
      new Promise<void>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) {
          reject(new Error('Socket not available'))
          return
        }
        const t = setTimeout(
          () => reject(new Error('Timed out waiting for screen creation')),
          10_000,
        )
        // create_screen does not ack; listen for the updated screens list
        socket.once('displayhive:admin:stc:upd_admin_screen', () => {
          clearTimeout(t)
          resolve()
        })
        socket.emit('displayhive:screens:cts:create_screen', { name: screenName })
      }),
    { screenName },
  )
}

/** Delete a screen by name via socket. */
async function deleteScreenBySocket(page: Page, screenName: string): Promise<void> {
  // We need the screen_id; find it from the screens list already loaded in the page
  await page.evaluate(
    ({ screenName }: { screenName: string }) =>
      new Promise<void>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) {
          reject(new Error('Socket not available'))
          return
        }
        const t = setTimeout(() => reject(new Error('Timed out waiting for screens list')), 10_000)
        socket.once('displayhive:admin:stc:upd_admin_screen', (data: any) => {
          clearTimeout(t)
          const screen = (data?.data || []).find((s: any) => s.name === screenName)
          if (screen) socket.emit('displayhive:screens:cts:delete_screen', { screen_id: screen.id })
          resolve()
        })
        socket.emit('displayhive:admin:cts:get_admin_screen')
      }),
    { screenName },
  )
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

// ---------------------------------------------------------------------------
// Suite state shared across serial tests
// ---------------------------------------------------------------------------

test.describe('Devices page', () => {
  const deviceName = `e2e-dev-${Math.random().toString(36).slice(2, 8)}`
  let devicekey = ''

  // Mutable name holder: edit-rename test updates this so later tests find
  // the row under the new name without reseeding.
  const deviceNameHolder = { current: deviceName }

  // Screen name chosen in the "assign screen" test (may be empty if no screens exist)
  let assignedScreenName = ''

  // Screen context is opened once in the filter test and reused for locate test
  let screenCtx: BrowserContext | null = null
  let screenPage: Page | null = null

  // ---------------------------------------------------------------------------
  // 1. Seed
  // ---------------------------------------------------------------------------

  test('seed: device appears in the devices table', async ({ page, backendUrl }) => {
    console.log('[devices.spec] init socket handlers')
    await gotoDevices(page, backendUrl)
    devicekey = await seedDevice(page, deviceName)

    const row = page.locator('tr', { hasText: deviceName })
    await expect(row).toBeVisible({ timeout: 10_000 })
  })

  // ---------------------------------------------------------------------------
  // 1b. Locate Device button is absent when device is offline (checked right
  //     after seeding while the device is still offline)
  // ---------------------------------------------------------------------------

  test('locate button is not visible when device is offline', async ({ page, backendUrl }) => {
    console.log('[devices.spec] init socket handlers')
    await gotoDevices(page, backendUrl)

    const row = page.locator('tr', { hasText: deviceName })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // Device is offline at this point — the button is conditionally rendered
    // with v-if="data.is_online" so it must not be in the DOM
    await expect(row.locator('button[title="Locate Device"]')).toHaveCount(0)
  })

  // ---------------------------------------------------------------------------
  // 2. Text filter narrows the table
  // ---------------------------------------------------------------------------

  test('text filter hides non-matching rows and shows matching ones', async ({
    page,
    backendUrl,
  }) => {
    console.log('[devices.spec] init socket handlers')
    await gotoDevices(page, backendUrl)

    const row = page.locator('tr', { hasText: deviceName })
    await expect(row).toBeVisible({ timeout: 10_000 })

    const filterInput = page.locator('.filter-input input, .filter-input')

    // Type a string that won't match our device name
    await filterInput.fill('__no_match_xyz__')
    await expect(row).toBeHidden({ timeout: 3_000 })

    // Clear and type part of our device name
    await filterInput.fill(deviceName.slice(0, 8))
    await expect(row).toBeVisible({ timeout: 3_000 })

    // Clear filter to restore full list
    await filterInput.fill('')
  })

  // ---------------------------------------------------------------------------
  // 3. Devicekey tooltip on hover
  // ---------------------------------------------------------------------------

  test('devicekey is shown on hover over the key icon', async ({ page, backendUrl }) => {
    console.log('[devices.spec] init socket handlers')
    await gotoDevices(page, backendUrl)

    const row = page.locator('tr', { hasText: deviceName })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // The key-text span is inside .key-cell and becomes visible on :hover via CSS
    const keyCell = row.locator('.key-cell').first()
    const keyText = keyCell.locator('.key-text')

    // Before hover: CSS makes the span invisible (opacity:0 / visibility:hidden)
    // We use Playwright's hover() which moves the mouse over the element so CSS :hover fires
    await keyCell.hover()

    // After hover the .key-text should be visible and contain the devicekey value
    await expect(keyText).toBeVisible({ timeout: 3_000 })
    await expect(keyText).toContainText(devicekey)
  })

  // ---------------------------------------------------------------------------
  // 4. Copy device key — clicking the key button shows a toast
  // ---------------------------------------------------------------------------

  test('copy key button shows "Device key copied" toast', async ({ page, backendUrl }) => {
    console.log('[devices.spec] init socket handlers')
    // Mock clipboard API before navigation — Firefox ignores grantPermissions
    // for clipboard, so we patch navigator.clipboard directly to always resolve.
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: () => Promise.resolve() },
        configurable: true,
      })
    })
    await gotoDevices(page, backendUrl)

    const row = page.locator('tr', { hasText: deviceName })
    await expect(row).toBeVisible({ timeout: 10_000 })

    await row.locator('button[title="Copy key"]').click()

    await expect(page.locator('.p-toast')).toContainText(/Device key copied/i, { timeout: 5_000 })
  })

  // ---------------------------------------------------------------------------
  // 5. Edit dialog — rename device
  // ---------------------------------------------------------------------------

  test('edit dialog renames the device and updates the row', async ({ page, backendUrl }) => {
    console.log('[devices.spec] init socket handlers')
    await gotoDevices(page, backendUrl)

    const row = page.locator('tr', { hasText: deviceName })
    await expect(row).toBeVisible({ timeout: 10_000 })

    await row.locator('button[title="Edit"]').click()

    const dialog = page.locator('.p-dialog', { hasText: 'Edit Device' })
    await expect(dialog).toBeVisible({ timeout: 5_000 })

    // Clear and type the new name — keep a known prefix so later tests still match
    const newName = `${deviceName}-ren`
    const nameInput = dialog.locator('#edit-name')
    await nameInput.clear()
    await nameInput.fill(newName)

    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden({ timeout: 5_000 })
    await expect(page.locator('.p-toast')).toContainText(/Device updated/i, { timeout: 5_000 })

    // Row must now show the new name (socket push refreshes the list)
    const renamedRow = page.locator('tr', { hasText: newName })
    await expect(renamedRow).toBeVisible({ timeout: 10_000 })

    // Update shared state so subsequent tests find the row by its new name
    deviceNameHolder.current = newName
  })

  // ---------------------------------------------------------------------------
  // 6. Edit dialog — assign a screen and verify the Screen column updates
  // ---------------------------------------------------------------------------

  test('edit dialog assigns a screen and Screen column reflects it', async ({
    page,
    backendUrl,
  }) => {
    console.log('[devices.spec] init socket handlers')
    await gotoDevices(page, backendUrl)

    // Seed a dedicated screen so this test is self-contained regardless of
    // what other spec files have run against this worker's isolated DB.
    const testScreenName = `e2e-scr-assign-${Math.random().toString(36).slice(2, 8)}`
    await seedScreen(page, testScreenName)
    assignedScreenName = testScreenName

    // Use whichever name the device currently has
    const currentName = deviceNameHolder.current
    const row = page.locator('tr', { hasText: currentName })
    await expect(row).toBeVisible({ timeout: 10_000 })

    await row.locator('button[title="Edit"]').click()

    const dialog = page.locator('.p-dialog', { hasText: 'Edit Device' })
    await expect(dialog).toBeVisible({ timeout: 5_000 })

    // Open the screen dropdown
    await dialog.locator('#edit-screen').click()

    // Pick the option matching the screen we just created
    const option = page.locator('.p-select-option', { hasText: testScreenName })
    await expect(option).toBeVisible({ timeout: 5_000 })
    await option.click()

    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden({ timeout: 5_000 })
    await expect(page.locator('.p-toast')).toContainText(/Device updated/i, { timeout: 5_000 })

    // Screen column for this row must now show the assigned screen name
    await expect(row).toContainText(testScreenName, { timeout: 10_000 })

    // Unassign device from screen (set back to No Screen) so cleanup can delete the screen
    await row.locator('button[title="Edit"]').click()
    await expect(dialog).toBeVisible({ timeout: 5_000 })
    await dialog.locator('#edit-screen').click()
    await page.locator('.p-select-option', { hasText: '-- No Screen --' }).click()
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden({ timeout: 5_000 })

    // Delete the temporary screen
    await deleteScreenBySocket(page, testScreenName)
  })

  // ---------------------------------------------------------------------------
  // 7. Refresh button re-requests the device list
  // ---------------------------------------------------------------------------

  test('refresh button reloads the device list', async ({ page, backendUrl }) => {
    console.log('[devices.spec] init socket handlers')
    await gotoDevices(page, backendUrl)

    const currentName = deviceNameHolder.current
    const row = page.locator('tr', { hasText: currentName })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // Refresh is a secondary page action: in the "More actions" menu of the page header
    await page.getByRole('button', { name: 'More actions' }).click()
    await page.getByRole('menuitem', { name: 'Refresh' }).click()

    // Table briefly shows a loading state then repopulates
    // Row must still be visible after refresh
    await expect(row).toBeVisible({ timeout: 10_000 })
  })

  // ---------------------------------------------------------------------------
  // 8. Impersonation ("Play") button opens a new tab showing the screen
  // ---------------------------------------------------------------------------

  test('play button opens impersonation tab with screen content', async ({
    page,
    backendUrl,
    context,
  }) => {
    console.log('[devices.spec] init socket handlers')
    await gotoDevices(page, backendUrl)

    const row = page.locator('tr', { hasText: deviceNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // Wait for the new tab that window.open() creates
    const [newPage] = await Promise.all([
      context.waitForEvent('page'),
      row.locator('button[title="Play"]').click(),
    ])

    // The tab should navigate to the screen client URL (Flask root, not admin SPA)
    // It carries ?impersonate=true&devicekey=<key>
    await newPage.waitForLoadState('domcontentloaded', { timeout: 15_000 })
    const url = newPage.url()
    expect(url).toContain('impersonate=true')
    expect(url).toContain(encodeURIComponent(devicekey))

    // The screen page should render some content (not a blank/error page)
    // The screen root element or body must be present
    await expect(newPage.locator('body')).toBeVisible({ timeout: 8_000 })

    await newPage.close()
  })

  // ---------------------------------------------------------------------------
  // 9. Online / offline filter tags
  // ---------------------------------------------------------------------------

  test('online/offline filter tags hide and reveal matching rows', async ({
    page,
    backendUrl,
    browser,
  }) => {
    console.log('[devices.spec] init socket handlers')
    await gotoDevices(page, backendUrl)

    // Open a real screen page so the device becomes online
    const opened = await openScreenPage(browser, backendUrl, devicekey)
    screenCtx = opened.ctx
    screenPage = opened.screenPage

    // Wait for the device to appear online in the admin table
    const row = page.locator('tr', { hasText: deviceNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })
    const statusTag = row.locator('.p-tag')
    await expect(statusTag).toContainText('Online', { timeout: 15_000 })

    // --- Hide online devices ---
    const onlineTag = page
      .locator('.clickable-tag')
      .filter({ hasText: /Online/ })
      .first()
    await onlineTag.click()
    // Our device is online so it should now be hidden
    await expect(row).toBeHidden({ timeout: 5_000 })

    // Offline tag still visible so offline devices still shown (none here but tag still present)
    await expect(page.locator('.clickable-tag').filter({ hasText: /Offline/ })).toBeVisible()

    // --- Show online devices again ---
    await onlineTag.click()
    await expect(row).toBeVisible({ timeout: 5_000 })

    // --- Hide offline devices ---
    const offlineTag = page
      .locator('.clickable-tag')
      .filter({ hasText: /Offline/ })
      .first()
    await offlineTag.click()
    // Our device is online so it should remain visible
    await expect(row).toBeVisible({ timeout: 3_000 })

    // Restore
    await offlineTag.click()
  })

  // ---------------------------------------------------------------------------
  // 10. Locate ("find") button highlights the screen
  // ---------------------------------------------------------------------------

  test('locate button highlights the connected screen', async ({ page, backendUrl }) => {
    console.log('[devices.spec] init socket handlers')
    // Reuse the screen page already opened in the previous test
    if (!screenPage) {
      test.fail(true, 'Screen page was not opened in the filter test — tests must run serially')
      return
    }

    await gotoDevices(page, backendUrl)

    const row = page.locator('tr', { hasText: deviceNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // The locate button is only rendered when the device is online
    const locateBtn = row.locator('button[title="Locate Device"]')
    await expect(locateBtn).toBeVisible({ timeout: 5_000 })

    // Activate locate — button turns green (severity="success" → p-button-success class)
    await locateBtn.click()

    // Screen side: the debug panel or a find-highlight element should appear.
    // The screen renders a #find-overlay or adds a class when find=true.
    // We check that the button changed to "active" state first (optimistic UI).
    await expect(locateBtn).toHaveClass(/p-button-success/, { timeout: 5_000 })

    // Deactivate locate — click again
    await locateBtn.click()
    // Button should revert to secondary (not success)
    await expect(locateBtn).not.toHaveClass(/p-button-success/, { timeout: 5_000 })

    // Close the screen context now that both filter and locate tests are done
    if (screenCtx) {
      await screenCtx.close()
      screenCtx = null
      screenPage = null
    }
  })

  // ---------------------------------------------------------------------------
  // 11. Cleanup
  // ---------------------------------------------------------------------------

  test('cleanup: delete the test device', async ({ page, backendUrl }) => {
    console.log('[devices.spec] init socket handlers')
    if (screenCtx) {
      await screenCtx.close()
      screenCtx = null
      screenPage = null
    }
    await gotoDevices(page, backendUrl)
    await deleteDeviceByRow(page, deviceNameHolder.current)
  })
})
