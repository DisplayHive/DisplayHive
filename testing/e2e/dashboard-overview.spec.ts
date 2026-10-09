/**
 * E2E tests for the Dashboard's working part (components/dashboard/DashboardOverview.vue):
 * quick actions, "On air", "Ending soon", "Starting soon", "Recently changed".
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(60_000)

async function emitAck<T = any>(page: Page, event: string, data: unknown): Promise<T> {
  return page.evaluate(
    ({ event, data }: { event: string; data: unknown }) =>
      new Promise<any>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { reject(new Error('Socket not available')); return }
        const t = setTimeout(() => reject(new Error(`Timed out: ${event}`)), 10_000)
        socket.emit(event, data, (ack: any) => { clearTimeout(t); resolve(ack) })
      }),
    { event, data },
  )
}

/** "YYYY-MM-DDTHH:MM" in the browser's local time, `days` from now. */
const localIn = (days: number) => {
  const d = new Date(Date.now() + days * 86_400_000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

test('dashboard shows quick actions, schedule panels and recent changes', async ({ page, backendUrl }) => {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, backendUrl)
  await page.goto(`${adminUrl}/`)
  await expect(page.locator('.dashboard')).toBeVisible({ timeout: 10_000 })

  const suffix = Math.random().toString(36).slice(2, 6)
  const ending = `e2e-ending-${suffix}`
  const starting = `e2e-starting-${suffix}`
  const group = await emitAck(page, 'displayhive:admin:cts:create_screengroup', { name: `e2e-dash-group-${suffix}` })
  expect(group.success).toBe(true)

  const make = async (title: string, extra: Record<string, string>) => {
    const ack = await emitAck(page, 'displayhive:admin:cts:create_content_element', { title, duration: 10, ...extra })
    expect(ack.success).toBe(true)
    const id = ack.content_element_id as number
    const add = await emitAck(page, 'displayhive:admin:cts:add_content_to_screengroup', { screengroup_id: group.screengroup_id, content_id: id })
    expect(add.success).toBe(true)
    return id
  }
  const endingId = await make(ending, { end_time: localIn(2) })
  const startingId = await make(starting, { start_time: localIn(3) })

  await page.reload()
  await expect(page.locator('.dashboard')).toBeVisible({ timeout: 10_000 })

  // Quick actions
  const actions = page.locator('[data-tour="dashboard-quick-actions"]')
  await expect(actions.getByRole('button', { name: 'New content' })).toBeVisible()
  await expect(actions.getByRole('button', { name: 'Upload media' })).toBeVisible()

  // Panels
  await expect(page.getByTestId('dash-expiring').getByRole('link', { name: ending })).toBeVisible({ timeout: 10_000 })
  await expect(page.getByTestId('dash-expiring')).toContainText('in 2 days')
  await expect(page.getByTestId('dash-expiring').getByText(starting)).toHaveCount(0)
  await expect(page.getByTestId('dash-starting').getByRole('link', { name: starting })).toBeVisible()
  await expect(page.getByTestId('dash-recent').getByRole('link', { name: ending })).toBeVisible()
  await expect(page.getByTestId('dash-onair')).toContainText('shown right now')

  // The panel links open the content element
  await page.getByTestId('dash-expiring').getByRole('link', { name: ending }).click()
  await expect(page).toHaveURL(new RegExp(`/content/${endingId}/edit`))

  // Clean up
  for (const id of [endingId, startingId]) await emitAck(page, 'displayhive:admin:cts:delete_content_element', { content_element_id: id })
  await emitAck(page, 'displayhive:admin:cts:delete_screengroup', { screengroup_id: group.screengroup_id })
})
