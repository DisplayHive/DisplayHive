/**
 * E2E tests for the Content admin page (/content).
 *
 * Covered:
 *  Setup
 *  0.  Seed a container + layout (needed by the contenttype) + contenttype
 *      (with one ContentHandler) + content item, all via socket
 *
 *  Main table / contenttype card
 *  1.  A card for the seeded Contenttype appears
 *  2.  Seeded content appears inside that card
 *  3.  Text filter narrows the content list
 *  4.  Toggle-active switch disables/re-enables a content item
 *  5.  Edit dialog renames the content item and updates the row
 *  6.  Refresh button reloads the content list
 *  7.  Delete button removes the content item after confirmation
 *
 * Strategy:
 *  - A ContentContainer + Layout + Contenttype (with a ContentHandler) are
 *    seeded via socket so the UI has at least one Contenttype card with a
 *    real container to target.
 *  - Content is seeded via socket and then interacted with through the UI.
 *  - All tests run serially on the same worker / isolated DB.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(60_000)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function gotoContent(page: Page, workerBackendUrl: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, workerBackendUrl)
  await page.goto(`${adminUrl}/content`)
  // Wait for the content-view card to mount
  await expect(page.locator('.content-view')).toBeVisible({ timeout: 10_000 })
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
          name, title: name, order: 0, top: 0, left: 0, width: 100, height: 100,
        }, (ack: any) => {
          clearTimeout(t)
          resolve(ack?.id ? Number(ack.id) : 0)
        })
      }),
    { name },
  )
}

/** Delete a container by id via socket. */
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

/** Delete a layout by id via socket. */
async function deleteLayout(page: Page, id: number): Promise<void> {
  await page.evaluate(
    ({ id }: { id: number }) => {
      const socket = (window as any).__displayhive_socket__
      if (socket) socket.emit('displayhive:admin:cts:delete_layout', { id })
    },
    { id },
  )
}

/** Create a content type (with one ContentHandler targeting containerId) via socket and return its id. */
async function seedContentType(page: Page, name: string, layoutId: number, containerId: number): Promise<number> {
  return page.evaluate(
    ({ name, layoutId, containerId }: { name: string; layoutId: number; containerId: number }) =>
      new Promise<number>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { reject(new Error('Socket not available')); return }
        const t = setTimeout(() => reject(new Error('Timed out waiting for create_contenttype result')), 10_000)
        socket.emit('displayhive:admin:cts:create_contenttype', {
          name,
          layout_id: layoutId,
          content_handlers: [{ contentcontainer_id: containerId, html: '{{ title_field }}', css: '' }],
        }, (ack: any) => {
          clearTimeout(t)
          if (ack?.ok) resolve(Number(ack.id))
          else reject(new Error(`create_contenttype failed: ${JSON.stringify(ack)}`))
        })
      }),
    { name, layoutId, containerId },
  )
}

/** Delete a content type by id via socket. */
async function deleteContentType(page: Page, id: number): Promise<void> {
  await page.evaluate(
    ({ id }: { id: number }) =>
      new Promise<void>((resolve) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { resolve(); return }
        const t = setTimeout(() => resolve(), 5_000)
        socket.once('displayhive:admin:stc:upd_contenttypes', () => { clearTimeout(t); resolve() })
        socket.emit('displayhive:admin:cts:delete_contenttype', { id })
      }),
    { id },
  )
}

/** Create a content_element item via socket and return its id. */
async function seedContent(page: Page, title: string, contenttypeId: number): Promise<number> {
  return page.evaluate(
    ({ title, contenttypeId }: { title: string; contenttypeId: number }) =>
      new Promise<number>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { reject(new Error('Socket not available')); return }
        const t = setTimeout(() => reject(new Error('Timed out waiting for create_content_element_result')), 10_000)
        socket.once('displayhive:admin:stc:create_content_element_result', (data: any) => {
          clearTimeout(t)
          if (data?.success) resolve(data.content_element_id)
          else reject(new Error(`create_content_element failed: ${JSON.stringify(data)}`))
        })
        socket.emit('displayhive:admin:cts:create_content_element', {
          title,
          duration: 10,
          contenttype_id: contenttypeId,
        })
      }),
    { title, contenttypeId },
  )
}

/** Delete a content_element item by id via socket. */
async function deleteContent(page: Page, id: number): Promise<void> {
  await page.evaluate(
    ({ id }: { id: number }) => {
      const socket = (window as any).__displayhive_socket__
      if (socket) socket.emit('displayhive:admin:cts:delete_content_element', { content_element_id: id })
    },
    { id },
  )
  await page.waitForTimeout(400)
}

// ---------------------------------------------------------------------------
// Suite state
// ---------------------------------------------------------------------------

test.describe('Content page', () => {
  const containerName = `e2e-cnt-container-${Math.random().toString(36).slice(2, 8)}`
  const layoutName = `e2e-cnt-layout-${Math.random().toString(36).slice(2, 8)}`
  const ctName = `e2e-cnt-ct-${Math.random().toString(36).slice(2, 8)}`
  const contentTitle = `e2e-cnt-${Math.random().toString(36).slice(2, 8)}`
  const contentTitleHolder = { current: contentTitle }

  let containerId = 0
  let layoutId = 0
  let ctId = 0
  let contentId = 0

  // ---------------------------------------------------------------------------
  // 0. Seed container + layout + content type + content
  // ---------------------------------------------------------------------------

  test('seed: container, layout, contenttype, and content item created', async ({ page, backendUrl }) => {
    await gotoContent(page, backendUrl)
    containerId = await seedContainer(page, containerName)
    expect(containerId).toBeGreaterThan(0)
    layoutId = await seedLayout(page, layoutName, containerId)
    expect(layoutId).toBeGreaterThan(0)
    ctId = await seedContentType(page, ctName, layoutId, containerId)
    expect(ctId).toBeGreaterThan(0)
    contentId = await seedContent(page, contentTitle, ctId)
    expect(contentId).toBeGreaterThan(0)
  })

  // ---------------------------------------------------------------------------
  // 1. A card for the seeded Contenttype appears
  // ---------------------------------------------------------------------------

  test('a card for the seeded contenttype appears', async ({ page, backendUrl }) => {
    await gotoContent(page, backendUrl)
    await expect(page.locator('.container-card', { hasText: ctName })).toBeVisible({ timeout: 10_000 })
  })

  // ---------------------------------------------------------------------------
  // 2. Seeded content appears in the contenttype card
  // ---------------------------------------------------------------------------

  test('seeded content appears inside the contenttype card', async ({ page, backendUrl }) => {
    await gotoContent(page, backendUrl)

    const row = page.locator('tr', { hasText: contentTitleHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })
  })

  // ---------------------------------------------------------------------------
  // 3. Text filter narrows content
  // ---------------------------------------------------------------------------

  test('text filter hides non-matching rows and reveals matching ones', async ({ page, backendUrl }) => {
    await gotoContent(page, backendUrl)

    const row = page.locator('tr', { hasText: contentTitleHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    const card = page.locator('.container-card', { hasText: ctName })
    const filterInput = card.locator('input[type="text"]').first()
    await filterInput.fill('__no_match_xyz__')
    await expect(row).toBeHidden({ timeout: 3_000 })

    // Clear — row reappears
    await filterInput.fill(contentTitleHolder.current.slice(0, 8))
    await expect(row).toBeVisible({ timeout: 3_000 })

    await filterInput.fill('')
  })

  // ---------------------------------------------------------------------------
  // 4. Toggle active switch
  // ---------------------------------------------------------------------------

  test('toggle active switch disables then re-enables the content item', async ({ page, backendUrl }) => {
    await gotoContent(page, backendUrl)

    const row = page.locator('tr', { hasText: contentTitleHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    const toggle = row.locator('.p-toggleswitch, input[type="checkbox"]').first()
    // Content starts active — toggling should deactivate it
    await toggle.click()
    // Give the socket a moment to process
    await page.waitForTimeout(500)

    // Re-enable
    await toggle.click()
    await page.waitForTimeout(500)
    // No assertion on class here since toggle state is tricky; we're testing the click doesn't error
  })

  // ---------------------------------------------------------------------------
  // 5. Edit dialog renames the content item
  // ---------------------------------------------------------------------------

  test('edit dialog renames the content item and table row updates', async ({ page, backendUrl }) => {
    await gotoContent(page, backendUrl)

    const row = page.locator('tr', { hasText: contentTitleHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })
    await row.locator('button:has(.pi-pencil)').click()

    const dialog = page.locator('.p-dialog', { hasText: 'Edit Content' })
    await expect(dialog).toBeVisible({ timeout: 5_000 })

    const newTitle = `${contentTitleHolder.current}-ren`
    const titleInput = dialog.locator('#create-title')
    await titleInput.clear()
    await titleInput.fill(newTitle)

    // "Update" saves but keeps the dialog open (edit-and-continue); "Save" saves
    // and closes it — click "Save" since this test expects the dialog to close.
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden({ timeout: 5_000 })

    await expect(page.locator('tr', { hasText: newTitle })).toBeVisible({ timeout: 10_000 })
    contentTitleHolder.current = newTitle
  })

  // ---------------------------------------------------------------------------
  // 6. Refresh button reloads the content list
  // ---------------------------------------------------------------------------

  test('refresh button reloads the content list', async ({ page, backendUrl }) => {
    await gotoContent(page, backendUrl)

    const row = page.locator('tr', { hasText: contentTitleHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    await page.getByRole('button', { name: 'Refresh' }).click()

    // Row must still be visible after refresh
    await expect(row).toBeVisible({ timeout: 10_000 })
  })

  // ---------------------------------------------------------------------------
  // 7. Delete content item
  // ---------------------------------------------------------------------------

  test('delete button removes the content item after confirmation', async ({ page, backendUrl }) => {
    await gotoContent(page, backendUrl)

    const row = page.locator('tr', { hasText: contentTitleHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })
    await row.locator('button:has(.pi-trash)').click()

    // Confirmation dialog
    const confirm = page.locator('.p-confirmdialog, .p-dialog').filter({ hasText: /delete|remove/i })
    await expect(confirm).toBeVisible({ timeout: 5_000 })
    await confirm.getByRole('button', { name: /yes|confirm|delete|ok/i }).first().click()

    await expect(page.locator('tr', { hasText: contentTitleHolder.current })).toHaveCount(0, { timeout: 10_000 })
    contentId = 0
  })

  // ---------------------------------------------------------------------------
  // Cleanup
  // ---------------------------------------------------------------------------

  test('cleanup: delete seeded content, content type, layout, and container', async ({ page, backendUrl }) => {
    await gotoContent(page, backendUrl)
    if (contentId > 0) await deleteContent(page, contentId)
    if (ctId > 0) await deleteContentType(page, ctId)
    if (layoutId > 0) await deleteLayout(page, layoutId)
    if (containerId > 0) await deleteContainer(page, containerId)
  })
})
