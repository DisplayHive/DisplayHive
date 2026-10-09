/**
 * E2E tests for the screen page's long-running behaviour (frontends/screen/ts/screen):
 *  - the service worker (ts/sw): a screen page that was loaded once still loads, and shows the
 *    connection problem, when the server cannot be reached;
 *  - the mouse pointer hides itself when idle;
 *  - the daily scheduled reload (Settings → Screens).
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Browser, BrowserContext, Page } from '@playwright/test'

test.setTimeout(90_000)
// Service workers and a "network down" switch that also covers them are Chromium's.
test.skip(({ browserName }) => browserName !== 'chromium', 'offline service worker test runs in Chromium')

async function emitAck<T = any>(page: Page, event: string, data: unknown): Promise<T> {
  return page.evaluate(
    ({ event, data }: { event: string; data: unknown }) =>
      new Promise<any>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        const t = setTimeout(() => reject(new Error(`Timed out: ${event}`)), 10_000)
        socket.emit(event, data, (ack: any) => { clearTimeout(t); resolve(ack) })
      }),
    { event, data },
  )
}

/** An adopted device, and its own page connected to the server. */
async function connectDevice(page: Page, browser: Browser, backendUrl: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, backendUrl)
  await page.goto(`${adminUrl}/screens`)
  await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })

  const token = `off-${Math.random().toString(36).slice(2, 7)}`
  const devicekey = await page.evaluate(
    ({ token }: { token: string }) =>
      new Promise<string>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        const t = setTimeout(() => reject(new Error('no registration_approved')), 10_000)
        socket.once('displayhive:devices:stc:registration_approved', (d: any) => { clearTimeout(t); resolve(d.devicekey) })
        socket.emit('displayhive:devices:cts:approve_registration', { token, device_name: `e2e-offline-${token}` })
      }),
    { token },
  )
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true })
  const screenPage = await ctx.newPage()
  await screenPage.addInitScript((key: string) => {
    try { localStorage.setItem('deviceKey', key); localStorage.removeItem('adoptionToken') } catch { /* no storage */ }
  }, devicekey)
  await screenPage.goto(backendUrl)
  await screenPage.waitForFunction(() => (window as any).socket?.connected, undefined, { timeout: 20_000 })
  return { ctx, screenPage, devicekey }
}

async function removeDevice(page: Page, ctx: BrowserContext, devicekey: string) {
  await ctx.setOffline(false)
  await ctx.close()
  const id = await page.evaluate(
    ({ devicekey }: { devicekey: string }) =>
      new Promise<number | null>((resolve) => {
        const socket = (window as any).__displayhive_socket__
        socket.once('displayhive:devices:stc:devices_upd_devicelist', (d: any) => {
          resolve((d?.devices || []).find((x: any) => x.devicekey === devicekey)?.id ?? null)
        })
        socket.emit('displayhive:devices:cts:get_devices')
      }),
    { devicekey },
  )
  if (id) await emitAck(page, 'displayhive:devices:cts:delete_device', { device_id: id })
}

test('a screen that was loaded once starts again while the server is unreachable', async ({ page, browser, backendUrl }) => {
  const { ctx, screenPage, devicekey } = await connectDevice(page, browser, backendUrl)

  // The worker is installed, controls the page and holds the page and its bundle
  await screenPage.waitForFunction(async () => {
    const reg = await navigator.serviceWorker.getRegistration()
    if (!reg?.active) return false
    const names = (await caches.keys()).filter((n) => n.startsWith('dh-screen-static-'))
    if (!names.length) return false
    const cache = await caches.open(names[0]!)
    const urls = (await cache.keys()).map((r) => new URL(r.url).pathname)
    return urls.includes('/') && urls.some((u) => u === '/dist/screen/screen.js')
  }, undefined, { timeout: 20_000 })

  // The server becomes unreachable; the screen is reloaded (a restart)
  await ctx.setOffline(true)
  await screenPage.reload({ waitUntil: 'domcontentloaded' })

  // The page came from the worker's cache, ran, and tells what is wrong
  await expect(screenPage.locator('#main-container')).toBeAttached()
  await expect(screenPage.locator('#status-indicator')).toHaveAttribute('data-level', 'red', { timeout: 30_000 })
  await expect(screenPage.locator('#status-indicator')).toContainText('con')

  await removeDevice(page, ctx, devicekey)
})

test('the mouse pointer hides when idle and comes back on movement', async ({ page, browser, backendUrl }) => {
  const { ctx, screenPage, devicekey } = await connectDevice(page, browser, backendUrl)
  const html = screenPage.locator('html')
  await expect(html).toHaveClass(/cursor-hidden/, { timeout: 10_000 })
  await screenPage.mouse.move(50, 50)
  await screenPage.mouse.move(80, 90)
  await expect(html).not.toHaveClass(/cursor-hidden/)
  await expect(html).toHaveClass(/cursor-hidden/, { timeout: 10_000 })
  await removeDevice(page, ctx, devicekey)
})

test('screens reload themselves at the daily reload time', async ({ page, browser, backendUrl }) => {
  test.setTimeout(180_000)
  const { ctx, screenPage, devicekey } = await connectDevice(page, browser, backendUrl)
  await screenPage.evaluate(() => { (window as any).__notReloaded = true })

  // Two minutes from now, in the instance's time zone (UTC unless set)
  const tz = await page.evaluate(
    () => new Promise<string>((resolve) => {
      const socket = (window as any).__displayhive_socket__
      socket.once('displayhive:admin:stc:admin_settings', (d: any) => resolve(d?.system_settings?.timezone || 'UTC'))
      socket.emit('displayhive:admin:cts:get_admin_settings')
    }),
  )
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: tz, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
    .formatToParts(new Date(Date.now() + 2 * 60_000))
  const at = `${parts.find((p) => p.type === 'hour')!.value}:${parts.find((p) => p.type === 'minute')!.value}`
  const ack = await emitAck(page, 'displayhive:admin:cts:set_system_settings', { settings: { screen_reload_at: at } })
  expect(ack.success).toBe(true)

  // A bad time is refused
  expect((await emitAck(page, 'displayhive:admin:cts:set_system_settings', { settings: { screen_reload_at: '25:99' } })).success).toBe(false)

  // The screen reloads itself: the marker set on the page is gone
  await expect.poll(
    async () => screenPage.evaluate(() => (window as any).__notReloaded === true).catch(() => false),
    { timeout: 170_000, intervals: [2_000] },
  ).toBe(false)
  await screenPage.waitForFunction(() => (window as any).socket?.connected, undefined, { timeout: 20_000 })

  await emitAck(page, 'displayhive:admin:cts:set_system_settings', { settings: { screen_reload_at: '' } })
  await removeDevice(page, ctx, devicekey)
})
