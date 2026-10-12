import test, { expect, seedAdminAuth } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Browser, APIRequestContext } from '@playwright/test'

// This suite mutates shared state (adopts + deletes a device) so tests within
// it must run one at a time on the same worker (and therefore the same isolated DB).
test.describe.configure({ mode: 'serial' })

// Allow up to 45s for this end-to-end adoption flow (overlay may wait for server actions)
test.setTimeout(45000)

test('Screen: Check adoption', async ({
  browser,
  backendUrl,
  request,
}: {
  browser: Browser
  backendUrl: string
  request: APIRequestContext
}) => {
  // Open the screen page in its own context (separate localStorage)
  const screenContext = await browser.newContext()
  const screenPage = await screenContext.newPage()
  await screenPage.goto(backendUrl)

  // Wait for registration overlay / QR to appear
  const overlay = screenPage.locator('#registration-overlay')
  await expect(overlay).toHaveClass(/show/, { timeout: 5000 })

  // Check adoption token stored in localStorage (screen-side key is 'adoptionToken')
  const adoptionToken = await screenPage.evaluate(() => localStorage.getItem('adoptionToken'))
  expect(adoptionToken).toBeTruthy()

  // Check QR code container is visible
  const qr = screenPage.locator('#qr-code')
  await expect(qr).toBeVisible({ timeout: 5000 })

  // Open admin UI in a separate context and navigate to Devices page. This
  // context bypasses the `page` fixture override, so it must be seeded with
  // an admin session explicitly.
  const adminContext = await browser.newContext()
  const adminPage = await adminContext.newPage()
  await seedAdminAuth(adminPage, request, backendUrl)
  await adminPage.goto(`${adminUrl}/devices`)

  // Open the Adopt Device modal
  const adoptButton = adminPage.getByRole('button', { name: 'Adopt Device' })
  await adoptButton.click()

  // Wait for the modal input and fill it with the token from the screen
  const adoptInput = adminPage.locator('#adopt-key')
  await adoptInput.fill(adoptionToken || '')

  // Fill a random device name so we can assert it appears in the list
  const deviceName = `e2e-adopt-${Math.random().toString(36).slice(2, 8)}`
  const adoptNameInput = adminPage.locator('#adopt-name')
  await adoptNameInput.fill(deviceName)

  // Click the Adopt button in the modal footer
  // Disambiguate between the header button and the modal button by using exact match
  const modalAdopt = adminPage.getByRole('button', { name: 'Adopt', exact: true })
  await modalAdopt.click()

  // Wait for the registration overlay to lose its 'show' class (fades to opacity:0).
  // The element stays in the DOM so state:'hidden' won't work — the overlay uses
  // opacity:0 (not display:none) which Playwright does not count as hidden.
  await expect(screenPage.locator('#registration-overlay')).not.toHaveClass(/show/, { timeout: 35000 })

  // Now check the admin devices list shows the newly adopted device name
  // Allow some time for the server->client update and table refresh
  const adoptedLocator = adminPage.getByText(deviceName)
  await expect(adoptedLocator).toBeVisible({ timeout: 20000 })

  // Find the table row containing our device and click its delete button
  const row = adminPage.locator('tr', { hasText: deviceName })
  await expect(row).toHaveCount(1)
  await row.locator('button:has(.pi-trash)').click()

  // Wait for the confirm message and confirm deletion
  const confirmMessage = `Are you sure you want to delete device "${deviceName}"?`
  const confirmMsgLocator = adminPage.getByText(confirmMessage)

  await expect(confirmMsgLocator).toBeVisible({ timeout: 5000 })

  // Click the accept button. Try a role-based lookup first (common labels),
  // then fall back to class-based selectors used by PrimeVue confirm dialogs.
  const acceptBtnByRole = adminPage.getByRole('button', {
    name: /^(Yes|Confirm|Delete|OK|Accept)$/i,
  })
  if ((await acceptBtnByRole.count()) > 0) {
    await acceptBtnByRole.first().click()
  } else {
    const fallback = adminPage.locator(
      '.p-confirm-dialog .p-button-danger, .p-confirm-dialog .p-confirm-dialog-accept, button.p-button-danger',
    )
    await fallback.first().click()
  }

  // Assert the device name is gone from the table
  await expect(adminPage.getByText(deviceName)).toHaveCount(0)

  // Cleanup contexts
  await adminContext.close()
  await screenContext.close()
})

export {}
