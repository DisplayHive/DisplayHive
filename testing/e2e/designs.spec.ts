/**
 * E2E tests for the Designs admin page (/designs).
 *
 * Covered:
 *  1.  "New Design" button opens dialog; fill name + HTML → row appears
 *  2.  Edit dialog renames the design and updates the row
 *  3.  Delete button removes a disposable design after confirmation
 *
 * Strategy:
 *  - Designs are created via the UI dialogs.
 *  - Socket helpers are used only for cleanup to avoid coupling test assertions
 *    to socket internals.
 *  - All tests run serially on the same worker / isolated DB.
 *
 * Note: Magic Tags now have their own dedicated page (/magictags,
 * MagicTagsView.vue) and are covered separately — they used to be tested
 * from this same spec when they lived on the Templates page.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(60_000)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function gotoDesigns(page: Page, workerBackendUrl: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, workerBackendUrl)
  await page.goto(`${adminUrl}/designs`)
  await expect(page.locator('.p-datatable').first()).toBeVisible({ timeout: 10_000 })
}

/** Delete a design by id via socket. */
async function deleteDesignById(page: Page, id: number): Promise<void> {
  await page.evaluate(
    ({ id }: { id: number }) =>
      new Promise<void>((resolve) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { resolve(); return }
        const t = setTimeout(() => resolve(), 8_000)
        socket.once('displayhive:admin:stc:upd_designs', () => {
          clearTimeout(t)
          resolve()
        })
        socket.emit('displayhive:admin:cts:delete_design', { id })
      }),
    { id },
  )
}

// ---------------------------------------------------------------------------
// Suite state
// ---------------------------------------------------------------------------

test.describe('Designs page', () => {
  const designName = `e2e-design-${Math.random().toString(36).slice(2, 8)}`
  const designNameHolder = { current: designName }
  let designId = 0

  // ---------------------------------------------------------------------------
  // 1. Create design via UI
  // ---------------------------------------------------------------------------

  test('"New Design" button opens dialog, fill name + HTML → row appears', async ({
    page,
    backendUrl,
  }) => {
    await gotoDesigns(page, backendUrl)

    await page.getByRole('button', { name: 'New Design' }).click()

    const dialog = page.locator('.p-dialog', { hasText: 'New Design' })
    await expect(dialog).toBeVisible({ timeout: 5_000 })

    await dialog.locator('#design-name').fill(designName)

    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden({ timeout: 5_000 })

    const row = page.locator('tr', { hasText: designName })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // Capture the design id
    designId = await page.evaluate(
      ({ name }: { name: string }) =>
        new Promise<number>((resolve) => {
          const socket = (window as any).__displayhive_socket__
          if (!socket) { resolve(0); return }
          const t = setTimeout(() => resolve(0), 8_000)
          socket.once('displayhive:admin:stc:upd_designs', (data: any) => {
            clearTimeout(t)
            const list: any[] = data?.data || []
            const d = list.find((d: any) => d.name === name)
            resolve(d ? Number(d.id) : 0)
          })
          socket.emit('displayhive:admin:cts:get_designs')
        }),
      { name: designName },
    )
  })

  // ---------------------------------------------------------------------------
  // 2. Edit design — rename
  // ---------------------------------------------------------------------------

  test('edit dialog renames the design and updates the row', async ({ page, backendUrl }) => {
    await gotoDesigns(page, backendUrl)

    const row = page.locator('tr', { hasText: designNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })
    await row.locator('button[title="Edit"]').click()

    const dialog = page.locator('.p-dialog', { hasText: 'Edit Design' })
    await expect(dialog).toBeVisible({ timeout: 5_000 })

    const newName = `${designNameHolder.current}-ren`
    await dialog.locator('#design-name').clear()
    await dialog.locator('#design-name').fill(newName)
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden({ timeout: 5_000 })

    await expect(page.locator('tr', { hasText: newName })).toBeVisible({ timeout: 10_000 })
    designNameHolder.current = newName
  })

  // ---------------------------------------------------------------------------
  // 3. Delete a disposable design via UI
  // ---------------------------------------------------------------------------

  test('delete button removes a design after confirmation', async ({ page, backendUrl }) => {
    await gotoDesigns(page, backendUrl)

    // Seed a disposable design via socket to avoid deleting the main one
    const delName = `e2e-design-del-${Math.random().toString(36).slice(2, 8)}`
    await page.evaluate(
      ({ delName }: { delName: string }) =>
        new Promise<void>((resolve) => {
          const socket = (window as any).__displayhive_socket__
          if (!socket) { resolve(); return }
          const t = setTimeout(() => resolve(), 8_000)
          socket.once('displayhive:admin:stc:upd_designs', () => {
            clearTimeout(t)
            resolve()
          })
          socket.emit('displayhive:admin:cts:create_design', { name: delName, html: '', css: '' })
        }),
      { delName },
    )

    await page.reload()
    await expect(page.locator('.p-datatable').first()).toBeVisible({ timeout: 10_000 })

    const delRow = page.locator('tr', { hasText: delName })
    await expect(delRow).toBeVisible({ timeout: 10_000 })
    await delRow.locator('button[title="Delete"]').click()

    await expect(page.getByText(/delete.*design|are you sure/i)).toBeVisible({ timeout: 5_000 })
    await page.getByRole('button', { name: /yes|confirm|delete|ok/i }).first().click()

    await expect(page.locator('tr', { hasText: delName })).toHaveCount(0, { timeout: 10_000 })
  })

  // ---------------------------------------------------------------------------
  // Cleanup
  // ---------------------------------------------------------------------------

  test('cleanup: delete seeded design', async ({ page, backendUrl }) => {
    await gotoDesigns(page, backendUrl)
    if (designId > 0) await deleteDesignById(page, designId)
  })
})
