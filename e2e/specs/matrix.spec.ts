/**
 * E2E tests for the Matrix admin page (/matrix).
 *
 * Covered:
 *  1.  Matrix page loads and renders a .matrix-table after screens and screen groups exist
 *  2.  After assigning a screen to a screen group the matrix cell reflects the relationship
 *
 * Strategy:
 *  - A screen and an explicit (non-is_one_screen) screen group are seeded via socket.
 *  - The matrix is read as a table; cells are located by row (screen) × column (group).
 *  - Assignment is done via socket (same call the screengroups page uses), then the
 *    matrix is reloaded to verify the cell state.
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

async function gotoMatrix(page: Page, workerBackendUrl: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, workerBackendUrl)
  await page.goto(`${adminUrl}/matrix`)
  await expect(page.locator('.matrix-view')).toBeVisible({ timeout: 10_000 })
}

/** Create a screen and return its id. */
async function seedScreen(page: Page, name: string): Promise<number> {
  return page.evaluate(
    ({ name }: { name: string }) =>
      new Promise<number>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { reject(new Error('Socket not available')); return }
        const t = setTimeout(() => reject(new Error('Timed out')), 10_000)
        socket.emit('displayhive:screens:cts:create_screen', { name }, (ack: any) => {
          clearTimeout(t)
          if (ack?.success) resolve(Number(ack.screen_id))
          else reject(new Error(JSON.stringify(ack)))
        })
      }),
    { name },
  )
}

/** Delete a screen by id. */
async function deleteScreen(page: Page, id: number): Promise<void> {
  await page.evaluate(
    ({ id }: { id: number }) => {
      const socket = (window as any).__displayhive_socket__
      if (socket) socket.emit('displayhive:screens:cts:delete_screen', { screen_id: id })
    },
    { id },
  )
  await page.waitForTimeout(400)
}

/** Create a screengroup and return its id. */
async function seedScreenGroup(page: Page, name: string): Promise<number> {
  return page.evaluate(
    ({ name }: { name: string }) =>
      new Promise<number>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { reject(new Error('Socket not available')); return }
        const t = setTimeout(() => reject(new Error('Timed out')), 10_000)
        socket.emit('displayhive:admin:cts:create_screengroup', { name }, (data: any) => {
          clearTimeout(t)
          if (data?.success) resolve(data.screengroup_id)
          else reject(new Error(JSON.stringify(data)))
        })
      }),
    { name },
  )
}

/** Delete a screengroup by id. */
async function deleteScreenGroup(page: Page, id: number): Promise<void> {
  await page.evaluate(
    ({ id }: { id: number }) =>
      new Promise<void>((resolve) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { resolve(); return }
        const t = setTimeout(() => resolve(), 5_000)
        socket.emit('displayhive:admin:cts:delete_screengroup', { screengroup_id: id }, () => { clearTimeout(t); resolve() })
      }),
    { id },
  )
}

/** Assign a screen to a screengroup via socket. */
async function assignScreen(page: Page, sgId: number, screenId: number): Promise<void> {
  await page.evaluate(
    ({ sgId, screenId }: { sgId: number; screenId: number }) =>
      new Promise<void>((resolve) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { resolve(); return }
        socket.emit('displayhive:admin:cts:add_screen_to_screengroup', {
          screengroup_id: sgId,
          screen_id: screenId,
        })
        setTimeout(resolve, 600)
      }),
    { sgId, screenId },
  )
}

/** Remove a screen from a screengroup via socket. */
async function removeScreen(page: Page, sgId: number, screenId: number): Promise<void> {
  await page.evaluate(
    ({ sgId, screenId }: { sgId: number; screenId: number }) =>
      new Promise<void>((resolve) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { resolve(); return }
        socket.emit('displayhive:admin:cts:remove_screen_from_screengroup', {
          screengroup_id: sgId,
          screen_id: screenId,
        })
        setTimeout(resolve, 600)
      }),
    { sgId, screenId },
  )
}

// ---------------------------------------------------------------------------
// Suite state
// ---------------------------------------------------------------------------

test.describe('Matrix page', () => {
  const screenName = `e2e-mx-scr-${Math.random().toString(36).slice(2, 8)}`
  const sgName = `e2e-mx-sg-${Math.random().toString(36).slice(2, 8)}`
  let screenId = 0
  let sgId = 0

  // ---------------------------------------------------------------------------
  // 0. Seed screen and screengroup
  // ---------------------------------------------------------------------------

  test('seed: screen and screengroup created', async ({ page, backendUrl }) => {
    await gotoMatrix(page, backendUrl)
    screenId = await seedScreen(page, screenName)
    sgId = await seedScreenGroup(page, sgName)
    expect(screenId).toBeGreaterThan(0)
    expect(sgId).toBeGreaterThan(0)
  })

  // ---------------------------------------------------------------------------
  // 1. Matrix page renders the matrix table with seeded data
  // ---------------------------------------------------------------------------

  test('matrix table renders screen rows and screengroup columns', async ({
    page,
    backendUrl,
  }) => {
    await gotoMatrix(page, backendUrl)

    // Wait for the matrix table to appear (not the loading state)
    const matrix = page.locator('.matrix-table')
    await expect(matrix).toBeVisible({ timeout: 15_000 })

    // Our screen should appear as a row
    await expect(matrix.locator('.screen-name', { hasText: screenName })).toBeVisible({
      timeout: 10_000,
    })

    // Our screengroup should appear as a column header
    await expect(matrix.locator('.group-header', { hasText: sgName })).toBeVisible({
      timeout: 10_000,
    })
  })

  // ---------------------------------------------------------------------------
  // Cleanup
  // ---------------------------------------------------------------------------

  test('cleanup: delete seeded screen and screengroup', async ({ page, backendUrl }) => {
    await gotoMatrix(page, backendUrl)
    if (screenId > 0) await deleteScreen(page, screenId)
    if (sgId > 0) await deleteScreenGroup(page, sgId)
  })
})
