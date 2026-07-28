/**
 * E2E tests for additional Screens admin page features (/screens).
 *
 * Covered (extending the existing screens.spec.ts):
 *  1.  Edit screen name — dialog renames the screen and the row updates
 *  2.  Text filter narrows the screens table
 *  3.  Screen resolution is displayed in the row after creation with dimensions
 *
 * Strategy:
 *  - One screen is seeded via the UI dialog (Add Screen) and used across tests.
 *  - All tests run serially on the same worker / isolated DB.
 *
 * Note: there used to be a per-screen "Template override" test here. Design
 * is now a single instance-wide setting (see designs.spec.ts) with no
 * per-screen override, so ScreensView.vue no longer has a template dropdown
 * and that test was removed.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(45_000)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function gotoScreens(page: Page, workerBackendUrl: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, workerBackendUrl)
  await page.goto(`${adminUrl}/screens`)
  await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })
}

async function deleteScreenByRow(page: Page, screenName: string) {
  const row = page.locator('tr', { hasText: screenName })
  await expect(row).toBeVisible({ timeout: 5_000 })
  await row.locator('button:has(.pi-trash)').click()
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
  await expect(page.locator('tr', { hasText: screenName })).toHaveCount(0, { timeout: 10_000 })
}

// ---------------------------------------------------------------------------
// Suite state
// ---------------------------------------------------------------------------

test.describe('Screens page — extra tests', () => {
  const screenName = `e2e-scrx-${Math.random().toString(36).slice(2, 8)}`
  const screenNameHolder = { current: screenName }

  // ---------------------------------------------------------------------------
  // 0. Create screen via UI (setup for subsequent tests)
  // ---------------------------------------------------------------------------

  test('add screen with resolution — row shows resolution', async ({ page, backendUrl }) => {
    await gotoScreens(page, backendUrl)

    await page.getByRole('button', { name: 'Add Screen' }).click()
    const dialog = page.locator('.p-dialog', { hasText: 'Add Screen' })
    await expect(dialog).toBeVisible({ timeout: 5_000 })

    await dialog.locator('#create-name').fill(screenName)
    await dialog.locator('#create-width').fill('1280')
    await dialog.locator('#create-height').fill('720')
    await dialog.getByRole('button', { name: 'Create' }).click()
    await expect(dialog).toBeHidden({ timeout: 5_000 })

    const row = page.locator('tr', { hasText: screenName })
    await expect(row).toBeVisible({ timeout: 10_000 })
    // Resolution should be visible in the row
    await expect(row).toContainText('1280')
  })

  // ---------------------------------------------------------------------------
  // 1. Edit screen name
  // ---------------------------------------------------------------------------

  test('edit dialog renames the screen and row updates', async ({ page, backendUrl }) => {
    await gotoScreens(page, backendUrl)

    const row = page.locator('tr', { hasText: screenNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })
    // The DataTable overlays a loading mask (screensStore.loading) that can
    // intercept clicks on rows underneath it.
    await expect(page.locator('.p-datatable-mask')).toBeHidden({ timeout: 10_000 })
    await row.locator('button:has(.pi-pencil)').click()

    const dialog = page.locator('.p-dialog', { hasText: 'Rename Screen' })
    await expect(dialog).toBeVisible({ timeout: 5_000 })

    const newName = `${screenNameHolder.current}-ren`
    const nameInput = dialog.locator('input[id*="name"], input[placeholder*="name" i]').first()
    await nameInput.clear()
    await nameInput.fill(newName)
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden({ timeout: 5_000 })

    await expect(page.locator('tr', { hasText: newName })).toBeVisible({ timeout: 10_000 })
    screenNameHolder.current = newName
  })

  // ---------------------------------------------------------------------------
  // 2. Text filter narrows the screens table
  // ---------------------------------------------------------------------------

  test('text filter hides non-matching rows and reveals matching ones', async ({
    page,
    backendUrl,
  }) => {
    await gotoScreens(page, backendUrl)

    const row = page.locator('tr', { hasText: screenNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    const filterInput = page
      .locator('.filter-input input, input[placeholder*="filter" i], input[placeholder*="search" i]')
      .first()
    await filterInput.fill('__no_match_xyz__')
    await expect(row).toBeHidden({ timeout: 3_000 })

    await filterInput.fill(screenNameHolder.current.slice(0, 8))
    await expect(row).toBeVisible({ timeout: 3_000 })

    await filterInput.fill('')
  })

  // ---------------------------------------------------------------------------
  // Cleanup
  // ---------------------------------------------------------------------------

  test('cleanup: delete seeded screen', async ({ page, backendUrl }) => {
    await gotoScreens(page, backendUrl)
    await deleteScreenByRow(page, screenNameHolder.current)
  })
})
