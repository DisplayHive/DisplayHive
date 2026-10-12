/**
 * E2E tests for the Content Types admin page (/contenttypes).
 *
 * Covered:
 *  Setup
 *  0.  Seed a container + layout via socket (a Contenttype now requires a Layout)
 *
 *  1.  "New Content Type" button opens dialog; fill name, pick layout → row appears in table
 *  2.  Text filter narrows the contenttypes table
 *  3.  Edit dialog renames the content type and updates the row
 *  4.  A second content type is created for delete testing (to avoid deleting
 *      the main one mid-suite)
 *  5.  Delete button removes the disposable content type after confirmation
 *
 * Strategy:
 *  - A container + layout are seeded via socket (needed for the Layout dropdown).
 *  - One content type is seeded via the UI dialog (test 1) and mutated in place.
 *  - A second disposable content type is created via socket for the delete test.
 *  - All tests run serially on the same worker / isolated DB.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(45_000)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function gotoContentTypes(page: Page, workerBackendUrl: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, workerBackendUrl)
  await page.goto(`${adminUrl}/contenttypes`)
  await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })
}

/** Create a standalone ContentContainer and return its id. */
async function seedContainer(page: Page, name: string): Promise<number> {
  return page.evaluate(
    ({ name }: { name: string }) =>
      new Promise<number>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { reject(new Error('Socket not available')); return }
        const t = setTimeout(() => reject(new Error('Timed out waiting for create_container result')), 10_000)
        socket.emit('displayhive:admin:cts:create_container', {
          name, order: 0, top: 0, left: 0, width: 100, height: 100,
        }, (ack: any) => {
          clearTimeout(t)
          resolve(ack?.id ? Number(ack.id) : 0)
        })
      }),
    { name },
  )
}

async function deleteContainer(page: Page, id: number): Promise<void> {
  await page.evaluate(
    ({ id }: { id: number }) => {
      const socket = (window as any).__displayhive_socket__
      if (socket) socket.emit('displayhive:admin:cts:delete_container', { id })
    },
    { id },
  )
}

/** Create a Layout containing *containerId* and return the layout id. */
async function seedLayout(page: Page, name: string, containerId: number): Promise<number> {
  return page.evaluate(
    ({ name, containerId }: { name: string; containerId: number }) =>
      new Promise<number>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { reject(new Error('Socket not available')); return }
        const t = setTimeout(() => reject(new Error('Timed out waiting for create_layout result')), 10_000)
        socket.emit('displayhive:admin:cts:create_layout', {
          name, description: '', container_ids: [containerId],
        }, (ack: any) => {
          clearTimeout(t)
          resolve(ack?.id ? Number(ack.id) : 0)
        })
      }),
    { name, containerId },
  )
}

async function deleteLayout(page: Page, id: number): Promise<void> {
  await page.evaluate(
    ({ id }: { id: number }) => {
      const socket = (window as any).__displayhive_socket__
      if (socket) socket.emit('displayhive:admin:cts:delete_layout', { id })
    },
    { id },
  )
}

/** Create a content type via socket and return its name. Returns the name on success. */
async function seedContentType(page: Page, name: string, layoutId: number): Promise<void> {
  await page.evaluate(
    ({ name, layoutId }: { name: string; layoutId: number }) =>
      new Promise<void>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { reject(new Error('Socket not available')); return }
        const t = setTimeout(() => reject(new Error('Timed out waiting for upd_contenttypes')), 10_000)
        socket.once('displayhive:admin:stc:upd_contenttypes', () => {
          clearTimeout(t)
          resolve()
        })
        socket.emit('displayhive:admin:cts:create_contenttype', { name, description: '', layout_id: layoutId })
      }),
    { name, layoutId },
  )
}

/** Delete a content type by id via socket. */
async function deleteContentTypeById(page: Page, id: number): Promise<void> {
  await page.evaluate(
    ({ id }: { id: number }) =>
      new Promise<void>((resolve) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { resolve(); return }
        const t = setTimeout(() => resolve(), 8_000)
        socket.once('displayhive:admin:stc:upd_contenttypes', () => {
          clearTimeout(t)
          resolve()
        })
        socket.emit('displayhive:admin:cts:delete_contenttype', { id })
      }),
    { id },
  )
}

// ---------------------------------------------------------------------------
// Suite state
// ---------------------------------------------------------------------------

test.describe('Content Types page', () => {
  const containerName = `e2e-ct-container-${Math.random().toString(36).slice(2, 8)}`
  const layoutName = `e2e-ct-layout-${Math.random().toString(36).slice(2, 8)}`
  const ctName = `e2e-ct-${Math.random().toString(36).slice(2, 8)}`
  const ctNameHolder = { current: ctName }
  let containerId = 0
  let layoutId = 0
  let ctId = 0

  // ---------------------------------------------------------------------------
  // 0. Seed a container + layout (a Contenttype now requires a Layout)
  // ---------------------------------------------------------------------------

  test('seed: container and layout created', async ({ page, backendUrl }) => {
    await gotoContentTypes(page, backendUrl)
    containerId = await seedContainer(page, containerName)
    expect(containerId).toBeGreaterThan(0)
    layoutId = await seedLayout(page, layoutName, containerId)
    expect(layoutId).toBeGreaterThan(0)
  })

  // ---------------------------------------------------------------------------
  // 1. Create content type via UI dialog
  // ---------------------------------------------------------------------------

  test('"New Content Type" button opens dialog, fill name, pick layout, save → row appears', async ({
    page,
    backendUrl,
  }) => {
    await gotoContentTypes(page, backendUrl)

    await page.getByRole('button', { name: 'New Content Type' }).click()

    const dialog = page.locator('.p-dialog', { hasText: 'New Content Type' })
    await expect(dialog).toBeVisible({ timeout: 5_000 })

    await dialog.locator('#ct-name').fill(ctName)

    // Pick the seeded Layout from the dropdown (required field)
    await dialog.locator('#ct-layout').click()
    await page.locator('.p-select-option', { hasText: layoutName }).click()

    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden({ timeout: 5_000 })

    const row = page.locator('tr', { hasText: ctName })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // Capture the id from the row by fetching the contenttypes list via socket
    ctId = await page.evaluate(
      ({ name }: { name: string }) =>
        new Promise<number>((resolve) => {
          const socket = (window as any).__displayhive_socket__
          if (!socket) { resolve(0); return }
          const t = setTimeout(() => resolve(0), 8_000)
          socket.once('displayhive:admin:stc:upd_contenttypes', (data: any) => {
            clearTimeout(t)
            const list: any[] = data?.data || []
            const ct = list.find((c: any) => c.name === name)
            resolve(ct ? Number(ct.id) : 0)
          })
          socket.emit('displayhive:admin:cts:get_contenttypes')
        }),
      { name: ctName },
    )
  })

  // ---------------------------------------------------------------------------
  // 2. Text filter narrows the content types table
  // ---------------------------------------------------------------------------

  test('text filter hides non-matching rows and reveals matching ones', async ({
    page,
    backendUrl,
  }) => {
    await gotoContentTypes(page, backendUrl)

    const row = page.locator('tr', { hasText: ctNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    const filterInput = page.locator('.filter-input input, input[placeholder*="filter" i], input[placeholder*="search" i]').first()
    await filterInput.fill('__no_match_xyz__')
    await expect(row).toBeHidden({ timeout: 3_000 })

    await filterInput.fill(ctNameHolder.current.slice(0, 8))
    await expect(row).toBeVisible({ timeout: 3_000 })

    await filterInput.fill('')
  })

  // ---------------------------------------------------------------------------
  // 3. Edit dialog renames the content type
  // ---------------------------------------------------------------------------

  test('edit dialog renames the content type and updates the row', async ({
    page,
    backendUrl,
  }) => {
    await gotoContentTypes(page, backendUrl)

    const row = page.locator('tr', { hasText: ctNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })
    await row.locator('button[title="Edit"]').click()

    const dialog = page.locator('.p-dialog', { hasText: 'Edit Content Type' })
    await expect(dialog).toBeVisible({ timeout: 5_000 })

    const newName = `${ctNameHolder.current}-ren`
    await dialog.locator('#ct-name').clear()
    await dialog.locator('#ct-name').fill(newName)
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden({ timeout: 5_000 })

    await expect(page.locator('tr', { hasText: newName })).toBeVisible({ timeout: 10_000 })
    ctNameHolder.current = newName
  })

  // ---------------------------------------------------------------------------
  // 4 + 5. Create a disposable content type via socket, then delete it via UI
  // ---------------------------------------------------------------------------

  test('delete button removes a content type after confirmation', async ({
    page,
    backendUrl,
  }) => {
    await gotoContentTypes(page, backendUrl)

    // Seed a disposable content type to delete (avoids deleting the main one)
    const delName = `e2e-ct-del-${Math.random().toString(36).slice(2, 8)}`
    await seedContentType(page, delName, layoutId)

    await page.reload()
    await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })

    const row = page.locator('tr', { hasText: delName })
    await expect(row).toBeVisible({ timeout: 10_000 })
    await row.locator('button[title="Delete"]').click()

    // Confirm deletion
    await expect(page.getByText(/delete.*content type|are you sure/i)).toBeVisible({ timeout: 5_000 })
    await page.getByRole('button', { name: /yes|confirm|delete|ok/i }).first().click()

    await expect(page.locator('tr', { hasText: delName })).toHaveCount(0, { timeout: 10_000 })
  })

  // ---------------------------------------------------------------------------
  // Cleanup
  // ---------------------------------------------------------------------------

  test('cleanup: delete the main seeded content type, layout, and container', async ({ page, backendUrl }) => {
    await gotoContentTypes(page, backendUrl)
    if (ctId > 0) {
      await deleteContentTypeById(page, ctId)
      await page.reload()
      await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })
      await expect(page.locator('tr', { hasText: ctNameHolder.current })).toHaveCount(0, {
        timeout: 5_000,
      })
    }
    if (layoutId > 0) await deleteLayout(page, layoutId)
    if (containerId > 0) await deleteContainer(page, containerId)
  })
})
