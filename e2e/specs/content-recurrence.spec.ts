/**
 * E2E tests for the weekly time windows of a content element (recurrence): saving and
 * validation through the socket API, and what the Dashboard's "On air" tile makes of it.
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

async function openAdmin(page: Page, backendUrl: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, backendUrl)
  await page.goto(`${adminUrl}/`)
  await expect(page.locator('.dashboard')).toBeVisible({ timeout: 10_000 })
}

/** The "On air" count on the Dashboard tile. */
const onAirCount = async (page: Page) => parseInt((await page.getByTestId('dash-onair').locator('.stat-value').textContent()) || '0', 10)

test('weekly windows are validated, saved and shown in the content list', async ({ page, backendUrl }) => {
  await openAdmin(page, backendUrl)
  const title = `e2e-weekly-${Math.random().toString(36).slice(2, 6)}`

  const bad = await emitAck(page, 'displayhive:admin:cts:create_content_element', {
    title, duration: 10, recurrence: [{ days: [], from: '08:00', to: '18:00' }],
  })
  expect(bad.success).toBe(false)
  expect(bad.error).toMatch(/weekday/i)

  const good = await emitAck(page, 'displayhive:admin:cts:create_content_element', {
    title, duration: 10, recurrence: [{ days: [3, 1], from: '08:00', to: '18:00' }],
  })
  expect(good.success).toBe(true)
  const id = good.content_element_id as number

  // The editor reads the windows from the detail answer
  const detail = await page.evaluate(
    (contentId: number) =>
      new Promise<any>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        const t = setTimeout(() => reject(new Error('Timed out: content detail')), 10_000)
        socket.once('displayhive:admin:stc:content_element_detail', (data: any) => { clearTimeout(t); resolve(data) })
        socket.emit('displayhive:admin:cts:get_content_element_detail', { content_element_id: contentId })
      }),
    id,
  )
  expect(detail.content.recurrence).toEqual([{ days: [1, 3], from: '08:00', to: '18:00' }])

  await emitAck(page, 'displayhive:admin:cts:delete_content_element', { content_element_id: id })
})

test('the On air tile counts only content inside its weekly window', async ({ page, backendUrl }) => {
  await openAdmin(page, backendUrl)
  const suffix = Math.random().toString(36).slice(2, 6)
  const group = await emitAck(page, 'displayhive:admin:cts:create_screengroup', { name: `e2e-rec-group-${suffix}` })
  expect(group.success).toBe(true)

  const make = async (title: string, recurrence: unknown) => {
    const ack = await emitAck(page, 'displayhive:admin:cts:create_content_element', { title, duration: 10, recurrence })
    expect(ack.success).toBe(true)
    const add = await emitAck(page, 'displayhive:admin:cts:add_content_to_screengroup', { screengroup_id: group.screengroup_id, content_id: ack.content_element_id })
    expect(add.success).toBe(true)
    return ack.content_element_id as number
  }

  await page.reload()
  await expect(page.getByTestId('dash-onair')).toBeVisible({ timeout: 10_000 })
  const before = await onAirCount(page)

  // Every weekday, all day except one minute: "inside" now. Never on any day: "outside" now.
  const everyDay = [1, 2, 3, 4, 5, 6, 7]
  const inside = await make(`e2e-in-${suffix}`, [{ days: everyDay, from: '00:00', to: '23:59' }])
  const outside = await make(`e2e-out-${suffix}`, [{ days: everyDay, from: '03:00', to: '03:01' }])

  await page.reload()
  await expect(page.getByTestId('dash-onair')).toBeVisible({ timeout: 10_000 })
  await expect.poll(() => onAirCount(page), { timeout: 10_000 }).toBe(before + 1)

  for (const id of [inside, outside]) await emitAck(page, 'displayhive:admin:cts:delete_content_element', { content_element_id: id })
  await emitAck(page, 'displayhive:admin:cts:delete_screengroup', { screengroup_id: group.screengroup_id })
})
