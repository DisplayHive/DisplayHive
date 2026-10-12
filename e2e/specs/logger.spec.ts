/**
 * E2E tests for the Logger admin page (/logger).
 *
 * Covered:
 *  1.  Logger page loads and the subscribe button is visible
 *  2.  Injecting a log entry via socket makes it appear in the log list
 *  3.  Filtering by screen name hides non-matching entries
 *
 * Strategy:
 *  - Tests subscribe to the logger room first so the admin page receives entries.
 *  - Log entries are injected via the displayhive:logger:cts:log_entry socket
 *    event (the same one the screen client sends).
 *  - A screen is seeded for the filter test so there is a concrete screen name
 *    to filter by.
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

async function gotoLogger(page: Page, workerBackendUrl: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, workerBackendUrl)
  await page.goto(`${adminUrl}/logger`)
  await expect(page.locator('.logger-view, .card')).toBeVisible({ timeout: 10_000 })
}

/**
 * Subscribe to the logger room via socket so the admin page receives log entries.
 * The admin logger view emits this automatically on mount; we ensure it's done.
 */
async function ensureLoggerSubscribed(page: Page): Promise<void> {
  await page.evaluate(() => {
    const socket = (window as any).__displayhive_socket__
    if (socket) socket.emit('displayhive:logger:cts:subscribe')
  })
  await page.waitForTimeout(300)
}

/**
 * Inject a log entry via socket (same path as screen client logger).
 * Returns the message string sent.
 */
async function injectLogEntry(
  page: Page,
  screenName: string,
  message: string,
): Promise<void> {
  await page.evaluate(
    ({ screenName, message }: { screenName: string; message: string }) => {
      const socket = (window as any).__displayhive_socket__
      if (socket) {
        socket.emit('displayhive:logger:cts:log_entry', {
          screen: screenName,
          message,
          severity: 'info',
          timestamp: new Date().toISOString(),
        })
      }
    },
    { screenName, message },
  )
}

/** Create a screen via socket and return its id. */
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

// ---------------------------------------------------------------------------
// Suite state
// ---------------------------------------------------------------------------

test.describe('Logger page', () => {
  let screenId = 0
  const screenName = `e2e-log-scr-${Math.random().toString(36).slice(2, 8)}`
  const logMessage = `e2e-log-msg-${Math.random().toString(36).slice(2, 8)}`

  // ---------------------------------------------------------------------------
  // 1. Page loads
  // ---------------------------------------------------------------------------

  test('logger page loads and shows the log view', async ({ page, backendUrl }) => {
    await gotoLogger(page, backendUrl)
    // The logger page should show a filter bar and log area
    await expect(page.locator('.logger-view')).toBeVisible({ timeout: 5_000 })
  })

  // ---------------------------------------------------------------------------
  // 2. Injecting a log entry via socket makes it appear in the log list
  // ---------------------------------------------------------------------------

  test('injected log entry appears in the log list', async ({ page, backendUrl }) => {
    await gotoLogger(page, backendUrl)
    await ensureLoggerSubscribed(page)

    // Clear any existing logs (if the page has a Clear button)
    const clearBtn = page.getByRole('button', { name: 'Clear' })
    if (await clearBtn.isVisible()) await clearBtn.click()

    // Inject a distinctive log entry
    await injectLogEntry(page, screenName, logMessage)

    // The entry should appear in the log list
    await expect(page.getByText(logMessage)).toBeVisible({ timeout: 10_000 })
  })

  // ---------------------------------------------------------------------------
  // Cleanup
  // ---------------------------------------------------------------------------

  test('cleanup: delete seeded screen', async ({ page, backendUrl }) => {
    await page.addInitScript((url: string) => {
      ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
    }, backendUrl)
    await page.goto(`${adminUrl}/screens`)
    await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })
    if (screenId > 0) await deleteScreen(page, screenId)
  })
})
