/**
 * E2E tests for the Dashboard admin page (/).
 *
 * Covered:
 *  1.  Dashboard loads and shows the welcome card
 *  2.  Stat cards render the correct counts after seeding known quantities of
 *      screens, content items, and screen groups
 *  3.  Clicking a stat card navigates to the relevant section
 *
 * Strategy:
 *  - Items are seeded via socket before navigating to the dashboard.
 *  - Counts are read from the .stat-value elements and compared to known seeds.
 *  - All seeded items are cleaned up in the final test.
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

async function gotoDashboard(page: Page, workerBackendUrl: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, workerBackendUrl)
  await page.goto(`${adminUrl}/`)
  await expect(page.locator('.dashboard')).toBeVisible({ timeout: 10_000 })
}

/** Create a screen via socket and return its id. */
async function seedScreen(page: Page, name: string): Promise<number> {
  return page.evaluate(
    ({ name }: { name: string }) =>
      new Promise<number>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { reject(new Error('Socket not available')); return }
        const t = setTimeout(() => reject(new Error('Timed out waiting for create_screen ack')), 10_000)
        socket.emit('displayhive:screens:cts:create_screen', { name }, (ack: any) => {
          clearTimeout(t)
          if (ack?.success) resolve(Number(ack.screen_id))
          else reject(new Error(`create_screen failed: ${JSON.stringify(ack)}`))
        })
      }),
    { name },
  )
}

/** Delete a screen by id via socket. */
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

/** Create a content_element item via socket and return its id. */
async function seedContent(page: Page, title: string): Promise<number> {
  return page.evaluate(
    ({ title }: { title: string }) =>
      new Promise<number>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { reject(new Error('Socket not available')); return }
        const t = setTimeout(() => reject(new Error('Timed out waiting for create_content_element_result')), 10_000)
        socket.once('displayhive:admin:stc:create_content_element_result', (data: any) => {
          clearTimeout(t)
          if (data?.success) resolve(data.content_element_id)
          else reject(new Error(`create_content_element failed: ${JSON.stringify(data)}`))
        })
        socket.emit('displayhive:admin:cts:create_content_element', { title, duration: 10 })
      }),
    { title },
  )
}

/** Delete a content_element item via socket. */
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

/** Create a screengroup via socket and return its id. */
async function seedScreenGroup(page: Page, name: string): Promise<number> {
  return page.evaluate(
    ({ name }: { name: string }) =>
      new Promise<number>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { reject(new Error('Socket not available')); return }
        const t = setTimeout(() => reject(new Error('Timed out waiting for screengroup_created')), 10_000)
        socket.emit('displayhive:admin:cts:create_screengroup', { name }, (data: any) => {
          clearTimeout(t)
          if (data?.success) resolve(data.screengroup_id)
          else reject(new Error(`create_screengroup failed: ${JSON.stringify(data)}`))
        })
      }),
    { name },
  )
}

/** Delete a screengroup by id via socket. */
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

// ---------------------------------------------------------------------------
// Suite state
// ---------------------------------------------------------------------------

test.describe('Dashboard', () => {
  const seededScreenIds: number[] = []
  const seededContentIds: number[] = []
  const seededSgIds: number[] = []

  // ---------------------------------------------------------------------------
  // 1. Dashboard loads
  // ---------------------------------------------------------------------------

  test('dashboard loads and shows the welcome card', async ({ page, backendUrl }) => {
    await gotoDashboard(page, backendUrl)
    await expect(page.getByText('Welcome to DisplayHive Admin')).toBeVisible({ timeout: 5_000 })
    // All stat cards should be present
    await expect(page.locator('.stat-card')).not.toHaveCount(0)
  })

  // ---------------------------------------------------------------------------
  // 2. Stat cards reflect seeded counts
  // ---------------------------------------------------------------------------

  test('stat cards show correct counts after seeding screens, content, and groups', async ({
    page,
    backendUrl,
  }) => {
    // Navigate to an admin page that has the socket, then seed
    await page.addInitScript((url: string) => {
      ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
    }, backendUrl)
    await page.goto(`${adminUrl}/screens`)
    await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })

    // Seed 2 screens, 2 content items, 1 explicit screen group
    // (creating 2 screens also creates 2 is_one_screen groups automatically,
    //  so screengroupsCount will be at least 3)
    for (let i = 0; i < 2; i++) {
      const id = await seedScreen(page, `e2e-dash-scr-${i}-${Math.random().toString(36).slice(2, 6)}`)
      seededScreenIds.push(id)
    }
    for (let i = 0; i < 2; i++) {
      const id = await seedContent(page, `e2e-dash-cnt-${i}-${Math.random().toString(36).slice(2, 6)}`)
      seededContentIds.push(id)
    }
    const sgId = await seedScreenGroup(page, `e2e-dash-sg-${Math.random().toString(36).slice(2, 6)}`)
    seededSgIds.push(sgId)

    // Navigate to dashboard and check stats
    await gotoDashboard(page, backendUrl)

    // Read stat values — each .stat-card contains a .stat-value
    const statCards = page.locator('.stat-card')
    await expect(statCards).not.toHaveCount(0, { timeout: 5_000 })

    // Screens card: should show at least 2
    const screensCard = page.locator('.stat-card').filter({ has: page.locator('.stat-label', { hasText: /^Screens$/ }) })
    await expect(screensCard.locator('.stat-value')).not.toHaveText('0', { timeout: 10_000 })
    const screensValue = await screensCard.locator('.stat-value').textContent()
    expect(Number(screensValue?.trim())).toBeGreaterThanOrEqual(2)

    // Content card: should show at least 2
    const contentCard = page.locator('.stat-card').filter({ has: page.locator('.stat-label', { hasText: /^Content$/ }) })
    await expect(contentCard.locator('.stat-value')).not.toHaveText('0', { timeout: 10_000 })
    const contentValue = await contentCard.locator('.stat-value').textContent()
    expect(Number(contentValue?.trim())).toBeGreaterThanOrEqual(2)

    // Screen Groups card: should show at least 1 explicit group
    const sgCard = page.locator('.stat-card', { hasText: /Screen Groups/ })
    await expect(sgCard.locator('.stat-value')).not.toHaveText('0', { timeout: 10_000 })
    const sgValue = await sgCard.locator('.stat-value').textContent()
    expect(Number(sgValue?.trim())).toBeGreaterThanOrEqual(1)
  })

  // ---------------------------------------------------------------------------
  // 3. Clicking Screens stat card navigates to /screens
  // ---------------------------------------------------------------------------

  test('clicking Screens stat card navigates to the screens section', async ({
    page,
    backendUrl,
  }) => {
    await gotoDashboard(page, backendUrl)

    const screensCard = page.locator('.stat-card').filter({ has: page.locator('.stat-label', { hasText: /^Screens$/ }) })
    await expect(screensCard).toBeVisible({ timeout: 5_000 })
    await screensCard.click()

    // Should navigate to the screens page
    await expect(page).toHaveURL(/\/screens/, { timeout: 5_000 })
    await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })
  })

  // ---------------------------------------------------------------------------
  // Cleanup
  // ---------------------------------------------------------------------------

  test('cleanup: delete seeded screens, content, and screen group', async ({
    page,
    backendUrl,
  }) => {
    await page.addInitScript((url: string) => {
      ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
    }, backendUrl)
    await page.goto(`${adminUrl}/screens`)
    await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })

    for (const id of seededScreenIds) await deleteScreen(page, id)
    for (const id of seededContentIds) await deleteContent(page, id)
    for (const id of seededSgIds) {
      // Screengroups seeded via create_screengroup are explicit (not is_one_screen)
      // They can be deleted only when empty
      await deleteScreenGroup(page, id)
    }
  })
})
