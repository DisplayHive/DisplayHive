/**
 * E2E tests for the persistent screen log: a real screen (device socket) reports a line, the
 * Logger page shows it live under the screen's real name, keeps it across a reload, filters and
 * searches it. Also: the Settings page's retention card.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(90_000)

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

async function adminPage(page: Page, backendUrl: string, path: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, backendUrl)
  await page.goto(`${adminUrl}${path}`)
}

test('a screen reports a line: shown live, stored, filterable', async ({ page, browser, backendUrl }) => {
  await adminPage(page, backendUrl, '/logger')
  await expect(page.locator('.logger-view')).toBeVisible({ timeout: 10_000 })

  // A screen with an adopted device
  const suffix = Math.random().toString(36).slice(2, 7)
  const screenName = `e2e-slog-${suffix}`
  const screen = await emitAck(page, 'displayhive:screens:cts:create_screen', { name: screenName })
  expect(screen.success).toBe(true)
  const devicekey = await page.evaluate(
    ({ token }: { token: string }) =>
      new Promise<string>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        const t = setTimeout(() => reject(new Error('no registration_approved')), 10_000)
        socket.once('displayhive:devices:stc:registration_approved', (d: any) => { clearTimeout(t); resolve(d.devicekey) })
        socket.emit('displayhive:devices:cts:approve_registration', { token, device_name: `e2e-slog-dev-${token}` })
      }),
    { token: `slog-${suffix}` },
  )
  const deviceId = await page.evaluate(
    ({ devicekey }: { devicekey: string }) =>
      new Promise<number>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        const t = setTimeout(() => reject(new Error('no device list')), 10_000)
        socket.once('displayhive:devices:stc:devices_upd_devicelist', (d: any) => {
          clearTimeout(t)
          const dev = (d?.devices || []).find((x: any) => x.devicekey === devicekey)
          dev ? resolve(dev.id) : reject(new Error('device missing'))
        })
        socket.emit('displayhive:devices:cts:get_devices')
      }),
    { devicekey },
  )
  const assigned = await emitAck(page, 'displayhive:devices:cts:assign_device_screen', {
    device_id: deviceId, screen_id: Number(screen.screen_id), screen_name: screenName,
  })
  expect(assigned.success).toBe(true)
  await page.waitForTimeout(800)

  // The screen's own page (a real device connection)
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true })
  const screenPage = await ctx.newPage()
  await screenPage.addInitScript((key: string) => {
    try { localStorage.setItem('deviceKey', key); localStorage.removeItem('adoptionToken') } catch { /* no storage */ }
  }, devicekey)
  await screenPage.goto(backendUrl)
  await screenPage.waitForFunction(() => (window as any).socket?.connected, undefined, { timeout: 20_000 })

  // The screen connected while the Logger page was open: it was told, and says so by itself
  await expect(page.locator('.log-entry', { hasText: 'Logger is now active' }).filter({ hasText: screenName }).first())
    .toBeVisible({ timeout: 15_000 })

  const message = `e2e-slog-msg-${suffix}`
  await screenPage.evaluate(
    ({ message }: { message: string }) => {
      ;(window as any).socket.emit('displayhive:logger:cts:log_entry', {
        severity: 'warn', message, function: 'e2e', screen: 'forged-name',
      })
    },
    { message },
  )

  // Live, under the real screen name (not the forged one)
  const line = page.locator('.log-entry', { hasText: message })
  await expect(line).toBeVisible({ timeout: 10_000 })
  await expect(line).toContainText(screenName)
  await expect(line).not.toContainText('forged-name')

  // Stored: still there after a reload
  await page.reload()
  await expect(page.locator('.log-entry', { hasText: message })).toBeVisible({ timeout: 10_000 })

  // Filters work on the stored lines
  await page.getByTestId('logger-search').fill(message)
  await expect(page.locator('.log-entry', { hasText: message })).toBeVisible()
  await page.getByTestId('logger-search').fill(`${message}-nope`)
  await expect(page.locator('.log-entry', { hasText: message })).toHaveCount(0)
  await page.getByTestId('logger-search').fill(message)
  await page.locator('.filter-item').filter({ hasText: 'Severity' }).locator('.p-select').click()
  await page.getByRole('option', { name: 'Error' }).click()
  await expect(page.locator('.log-entry', { hasText: message })).toHaveCount(0)

  // Clean up
  await ctx.close()
  await emitAck(page, 'displayhive:devices:cts:delete_device', { device_id: deviceId })
  await emitAck(page, 'displayhive:screens:cts:delete_screen', { screen_id: screen.screen_id })
})

test('retention settings are saved and validated', async ({ page, backendUrl }) => {
  await adminPage(page, backendUrl, '/settings')
  await expect(page.locator('[data-tour="settings-screenlog-fields"]')).toBeVisible({ timeout: 10_000 })

  const bad = await emitAck(page, 'displayhive:admin:cts:set_system_settings', { settings: { screen_log_max_rows: '5' } })
  expect(bad.success).toBe(false)

  const hours = page.locator('#screen-log-max-age input')
  await hours.fill('48 hours')
  await page.locator('[data-tour="settings-screenlog-save"]').getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('Screen log settings updated')).toBeVisible({ timeout: 5_000 })

  await page.reload()
  await expect(page.locator('#screen-log-max-age input')).toHaveValue('48 hours', { timeout: 10_000 })
  // back to the default
  await emitAck(page, 'displayhive:admin:cts:set_system_settings', { settings: { screen_log_max_age_hours: '72' } })
})
