/**
 * E2E tests for the Plugins page (application/plugins/, application/admin/plugins/): the bundled plugins are
 * listed, one is switched off and on again while the server runs, and a plugin of one's own is uploaded as a ZIP
 * file, answers on its route and is removed again.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import { makeZip } from './makeZip.js'
import type { Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(60_000)

const id = `e2e.plugin${Math.random().toString(36).slice(2, 7)}`

async function gotoPlugins(page: Page, backendUrl: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, backendUrl)
  await page.goto(`${adminUrl}/plugins`)
  await expect(page.getByTestId('plugin-displayhive.countdown')).toBeVisible({ timeout: 15_000 })
}

const active = async (page: Page, backendUrl: string): Promise<string[]> =>
  ((await (await page.request.get(`${backendUrl}/api/plugins/_active`)).json()) as { plugins: Array<{ id: string }> }).plugins.map((p) => p.id)

test('the bundled plugins are listed', async ({ page, backendUrl }) => {
  await gotoPlugins(page, backendUrl)
  for (const name of ['textklein', 'image', 'icon', 'countdown', 'marquee', 'wysiwyg']) {
    await expect(page.getByTestId(`plugin-displayhive.${name}`)).toBeVisible()
  }
  await expect(page.getByTestId('plugin-displayhive.countdown').getByRole('switch')).toBeChecked()
  await expect(page.getByTestId('plugin-displayhive.pretalx')).toBeVisible()
  // bundled plugins cannot be removed
  await expect(page.getByTestId('plugin-remove-displayhive.countdown')).toHaveCount(0)
})

test('a plugin is switched off and on again without a restart', async ({ page, backendUrl }) => {
  await gotoPlugins(page, backendUrl)
  const toggle = page.getByTestId('plugin-displayhive.marquee').getByRole('switch')
  try {
    await toggle.click()
    await expect(toggle).not.toBeChecked({ timeout: 10_000 })
    expect(await active(page, backendUrl)).not.toContain('displayhive.marquee')
    // a plugin that was loaded is now held in memory until a restart: the page says so
    await expect(page.getByTestId('plugins-restart')).toBeVisible({ timeout: 10_000 })
  } finally {
    if (!(await toggle.isChecked())) await toggle.click()
  }
  await expect(toggle).toBeChecked({ timeout: 10_000 })
  expect(await active(page, backendUrl)).toContain('displayhive.marquee')
})

test('a plugin of one\'s own is uploaded, answers on its route and is removed', async ({ page, backendUrl }) => {
  await gotoPlugins(page, backendUrl)
  const zip = makeZip({
    'plugin.json': JSON.stringify({ id, name: 'E2E plugin', kind: 'integration', version: '1.0.0', plugin_api: 1, backend: 'backend', description: 'for the tests' }),
    'backend/__init__.py': 'def register(api):\n    api.routes.add("hello", lambda: {"hello": "e2e"})\n',
  })
  await page.getByTestId('plugin-file').setInputFiles({ name: 'plugin.zip', mimeType: 'application/zip', buffer: zip })
  await page.getByTestId('plugin-install-file').click()
  const row = page.getByTestId(`plugin-${id}`)
  await expect(row).toBeVisible({ timeout: 15_000 })
  await expect(row).toContainText('Installed')
  await expect(row.getByRole('switch')).toBeChecked()
  expect(await (await page.request.get(`${backendUrl}/api/plugins/${id}/hello`)).json()).toEqual({ hello: 'e2e' })

  await page.getByTestId(`plugin-remove-${id}`).click()
  await page.getByRole('button', { name: /^(yes|delete|remove|ok)$/i }).click()
  await expect(row).toHaveCount(0, { timeout: 10_000 })
  expect((await page.request.get(`${backendUrl}/api/plugins/${id}/hello`)).status()).toBe(404)
})

test('a file that is not a plugin is refused with a message', async ({ page, backendUrl }) => {
  await gotoPlugins(page, backendUrl)
  await page.getByTestId('plugin-file').setInputFiles({ name: 'x.zip', mimeType: 'application/zip', buffer: makeZip({ 'readme.txt': 'x' }) })
  await page.getByTestId('plugin-install-file').click()
  await expect(page.getByTestId('plugin-error')).toContainText('plugin.json', { timeout: 10_000 })
})
