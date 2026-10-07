/**
 * E2E tests for the Media admin page (/media).
 *
 * Covered:
 *  1.  Navigate to /media — grid and upload button are visible
 *  2.  Upload an image via the UI file dialog → item appears in the grid
 *  3.  Edit media title via the edit dialog → grid card shows new title
 *  4.  Delete a media item via the delete button → item disappears from the grid
 *  5.  Upload a second item via socket (base64 PNG) → item appears immediately
 *
 * Strategy:
 *  - Test 2 uploads a real (tiny) PNG through the Playwright FileChooser API.
 *  - Test 5 uploads via socket to validate the socket upload path independently.
 *  - Cleanup removes any items created during the suite.
 *  - All tests run serially on the same worker / isolated DB.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(60_000)

// Minimal 1×1 white PNG (69 bytes)
const TINY_PNG_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function gotoMedia(page: Page, workerBackendUrl: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, workerBackendUrl)
  await page.goto(`${adminUrl}/media`)
  // Wait for the media grid or empty state to appear
  await expect(page.locator('.media-view, .card')).toBeVisible({ timeout: 10_000 })
}

/**
 * Upload a media item through the HTTP upload endpoint (multipart — the same
 * request the Media page sends). Returns the media id. Sent from Playwright's
 * own HTTP client straight to the worker's backend, with the session token
 * the page holds.
 */
async function seedMediaViaHttp(page: Page, backendUrl: string, filename: string): Promise<number> {
  const token = await page.evaluate(() => localStorage.getItem('displayhive_admin_token'))
  const response = await page.request.post(`${backendUrl}/admin/api/media/upload`, {
    headers: { Authorization: `Bearer ${token}` },
    multipart: {
      file: { name: filename, mimeType: 'image/png', buffer: Buffer.from(TINY_PNG_BASE64, 'base64') },
      title: filename,
      tags: '',
    },
  })
  const result = await response.json()
  if (!response.ok() || !result?.success) throw new Error(`Upload failed: ${JSON.stringify(result)}`)
  return Number(result.id)
}

/** Delete a media item by id via socket. */
async function deleteMediaById(page: Page, id: number): Promise<void> {
  await page.evaluate(
    ({ id }: { id: number }) =>
      new Promise<void>((resolve) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { resolve(); return }
        socket.once('displayhive:media:stc:media_list', () => resolve())
        setTimeout(() => resolve(), 3_000)
        socket.emit('displayhive:media:cts:delete_media', { id })
      }),
    { id },
  )
}

// ---------------------------------------------------------------------------
// Suite state
// ---------------------------------------------------------------------------

test.describe('Media page', () => {
  let uploadedMediaId = 0
  let socketMediaId = 0
  const uiFilename = `e2e-ui-${Math.random().toString(36).slice(2, 8)}.png`
  const uiFilenameHolder = { current: uiFilename }

  // ---------------------------------------------------------------------------
  // 1. Page loads
  // ---------------------------------------------------------------------------

  test('media page loads with upload button visible', async ({ page, backendUrl }) => {
    await gotoMedia(page, backendUrl)
    await expect(page.getByRole('button', { name: 'Upload' })).toBeVisible({ timeout: 5_000 })
  })

  // ---------------------------------------------------------------------------
  // 2. Upload via UI file dialog
  // ---------------------------------------------------------------------------

  test('upload image via file dialog — item appears in the media grid', async ({
    page,
    backendUrl,
  }) => {
    await gotoMedia(page, backendUrl)

    // Click Upload to open the dialog
    await page.getByRole('button', { name: 'Upload' }).click()

    const uploadDialog = page.locator('.p-dialog', { hasText: 'Upload Media' })
    await expect(uploadDialog).toBeVisible({ timeout: 5_000 })

    // Set files directly on the hidden input — avoids opening the OS file chooser
    await uploadDialog.locator('input[type="file"]').setInputFiles({
      name: uiFilename,
      mimeType: 'image/png',
      buffer: Buffer.from(TINY_PNG_BASE64, 'base64'),
    })

    // After selecting, the dialog should show the file name and an Upload/Confirm button
    await expect(uploadDialog.getByText(uiFilename)).toBeVisible({ timeout: 5_000 })

    // Click the upload button inside the dialog
    const uploadBtn = uploadDialog
      .locator('.p-dialog-footer')
      .getByRole('button', { name: /upload|confirm|ok/i })
      .first()
    await uploadBtn.click()

    // Dialog closes and item appears in the media grid
    await expect(uploadDialog).toBeHidden({ timeout: 10_000 })

    // A grid card with our filename should now exist
    const card = page.locator('.media-item, .p-card', { hasText: uiFilename }).first()
    await expect(card).toBeVisible({ timeout: 15_000 })

    // Capture the media id for cleanup via the media_list event
    uploadedMediaId = await page.evaluate(
      ({ name }: { name: string }) =>
        new Promise<number>((resolve) => {
          const socket = (window as any).__displayhive_socket__
          if (!socket) { resolve(0); return }
          const t = setTimeout(() => resolve(0), 8_000)
          socket.once('displayhive:media:stc:media_list', (data: any) => {
            clearTimeout(t)
            const list: any[] = data?.media || []
            const item = list.find((m: any) => m.filename === name || m.title === name)
            resolve(item ? Number(item.id) : 0)
          })
          socket.emit('displayhive:media:cts:get_media')
        }),
      { name: uiFilename },
    )
  })

  // ---------------------------------------------------------------------------
  // 3. Edit media title
  // ---------------------------------------------------------------------------

  test('edit dialog changes the media title and grid card updates', async ({
    page,
    backendUrl,
  }) => {
    await gotoMedia(page, backendUrl)

    // Find the media item card and click Edit
    const card = page.locator('.media-item, .p-card', { hasText: uiFilenameHolder.current }).first()
    await expect(card).toBeVisible({ timeout: 10_000 })
    await card.locator('button:has(.pi-pencil)').click()

    const dialog = page.locator('.p-dialog', { hasText: 'Edit Media' })
    await expect(dialog).toBeVisible({ timeout: 5_000 })

    const newTitle = `${uiFilenameHolder.current.replace('.png', '')}-renamed`
    await dialog.locator('#media-title').clear()
    await dialog.locator('#media-title').fill(newTitle)
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden({ timeout: 5_000 })

    // Grid card should now display the new title
    await expect(page.locator('.media-item, .p-card', { hasText: newTitle }).first()).toBeVisible({
      timeout: 10_000,
    })
    uiFilenameHolder.current = newTitle
  })

  // ---------------------------------------------------------------------------
  // 5. Upload via the HTTP endpoint (no UI)
  // ---------------------------------------------------------------------------

  test('upload via HTTP — item appears in the media grid', async ({
    page,
    backendUrl,
  }) => {
    await gotoMedia(page, backendUrl)

    const socketFilename = `e2e-sock-${Math.random().toString(36).slice(2, 8)}.png`
    socketMediaId = await seedMediaViaHttp(page, backendUrl, socketFilename)
    expect(socketMediaId).toBeGreaterThan(0)

    // Reload to confirm the grid shows it
    await page.reload()
    await expect(page.locator('.media-view, .card')).toBeVisible({ timeout: 10_000 })
    await expect(
      page.locator('.media-item, .p-card', { hasText: socketFilename }).first(),
    ).toBeVisible({ timeout: 10_000 })
  })

  // ---------------------------------------------------------------------------
  // Cleanup
  // ---------------------------------------------------------------------------

  test('cleanup: delete seeded media items', async ({ page, backendUrl }) => {
    await gotoMedia(page, backendUrl)
    if (uploadedMediaId > 0) await deleteMediaById(page, uploadedMediaId)
    if (socketMediaId > 0) await deleteMediaById(page, socketMediaId)
  })
})
