/**
 * E2E tests for the Ctrl+K command palette (components/CommandPalette.vue).
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

async function gotoHome(page: Page, backendUrl: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, backendUrl)
  await page.goto(`${adminUrl}/`)
  await expect(page.locator('.dashboard')).toBeVisible({ timeout: 10_000 })
}

test('Ctrl+K opens the palette, finds pages and items, Enter jumps there', async ({ page, backendUrl }) => {
  await gotoHome(page, backendUrl)
  const suffix = Math.random().toString(36).slice(2, 6)
  const title = `e2e-palette-${suffix}`
  const created = await emitAck(page, 'displayhive:admin:cts:create_content_element', { title, duration: 10 })
  expect(created.success).toBe(true)
  const screenName = `e2e-pal-screen-${suffix}`
  const screen = await emitAck(page, 'displayhive:screens:cts:create_screen', { name: screenName })
  expect(screen.success).toBe(true)

  const palette = page.getByTestId('command-palette')
  const input = palette.getByRole('textbox', { name: 'Search' })

  // Page: "layouts" → Enter
  await page.keyboard.press('Control+k')
  await expect(palette).toBeVisible()
  await expect(input).toBeFocused()
  await input.fill('layouts')
  await expect(palette.getByTestId('palette-p-/layouts')).toBeVisible()
  await input.press('Enter')
  await expect(page).toHaveURL(/\/layouts$/)
  await expect(palette).toBeHidden()

  // Item: a content element by name
  await page.keyboard.press('Control+k')
  await input.fill(title)
  await expect(palette.getByTestId(`palette-c-${created.content_element_id}`)).toBeVisible({ timeout: 10_000 })
  await input.press('Enter')
  await expect(page).toHaveURL(new RegExp(`/content/${created.content_element_id}/edit`))

  // Item: a screen opens its edit dialog; Escape closes the palette
  await page.keyboard.press('Control+k')
  await input.fill(screenName)
  await expect(palette.getByTestId(`palette-s-${screen.screen_id}`)).toBeVisible({ timeout: 10_000 })
  await palette.getByTestId(`palette-s-${screen.screen_id}`).click()
  await expect(page).toHaveURL(/\/screens/)
  await page.keyboard.press('Control+k')
  await expect(palette).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(palette).toBeHidden()

  // Nothing found
  await page.keyboard.press('Control+k')
  await input.fill('zzzz-no-such-thing')
  await expect(palette).toContainText('Nothing found')
  await page.keyboard.press('Escape')

  // The header button opens it too
  await page.getByTestId('palette-button').click()
  await expect(palette).toBeVisible()
  await page.keyboard.press('Escape')

  await emitAck(page, 'displayhive:admin:cts:delete_content_element', { content_element_id: created.content_element_id })
  await emitAck(page, 'displayhive:screens:cts:delete_screen', { screen_id: screen.screen_id })
})
