/**
 * E2E tests for the installable icon libraries (Settings → Icon libraries, application/admin/icons/libraries.py).
 * DisplayHive ships no icons; the catalog download needs the internet and is covered by unit tests, so
 * here a library of one's own is uploaded as a ZIP file, served and removed again.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Page } from '@playwright/test'
import { makeZip } from './makeZip.js'

test.describe.configure({ mode: 'serial' })
test.setTimeout(60_000)

const SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M2 12h20" stroke="currentColor"/><script>alert(1)</script></svg>'

async function gotoSettings(page: Page, backendUrl: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, backendUrl)
  await page.goto(`${adminUrl}/settings`)
  await expect(page.getByTestId('icon-lib-table')).toBeVisible({ timeout: 15_000 })
}

const libId = `e2e-${Math.random().toString(36).slice(2, 7)}`

test('the card lists the known libraries as not installed', async ({ page, backendUrl }) => {
  await gotoSettings(page, backendUrl)
  for (const id of ['lucide', 'material-symbols', 'tabler', 'remixicon']) {
    const row = page.getByTestId(`icon-lib-${id}`)
    await expect(row).toBeVisible()
    await expect(row).toContainText('not installed')
    await expect(page.getByTestId(`icon-lib-install-${id}`)).toBeEnabled()
  }
  await expect(page.getByTestId('icon-lib-install-all')).toBeEnabled()
})

test('a library of one\'s own is uploaded, sanitised, served and removed', async ({ page, backendUrl }) => {
  await gotoSettings(page, backendUrl)
  const own = page.getByTestId('icon-lib-own')
  await own.locator('#icon-lib-id').fill(libId)
  await own.locator('#icon-lib-label').fill('E2E icons')
  await own.locator('#icon-lib-license').fill('CC0')
  await page.getByTestId('icon-lib-file').setInputFiles({
    name: 'icons.zip', mimeType: 'application/zip',
    buffer: makeZip({ 'set/Home.svg': SVG, 'set/readme.txt': 'not an icon' }),
  })
  await page.getByTestId('icon-lib-upload').click()
  const row = page.getByTestId(`icon-lib-${libId}`)
  await expect(row).toBeVisible({ timeout: 15_000 })
  await expect(row).toContainText('1 installed')
  await expect(row).toContainText('CC0')

  // served, and the script in the file is gone
  const manifest = await (await page.request.get(`${backendUrl}/static/icons/manifest.json`)).json()
  expect(manifest[libId]).toEqual(['home'])
  const svg = await (await page.request.get(`${backendUrl}/static/icons/${libId}/home.svg`)).text()
  expect(svg).toContain('<path')
  expect(svg).not.toContain('script')

  // remove it
  await row.getByRole('button', { name: /remove/i }).or(row.locator('button[title="Remove"]')).click()
  await page.getByRole('button', { name: /^(yes|delete|remove|ok)$/i }).click()
  await expect(row).toHaveCount(0, { timeout: 10_000 })
  expect(((await (await page.request.get(`${backendUrl}/static/icons/manifest.json`)).json()) as Record<string, unknown>)[libId]).toBeUndefined()
})

test('bad input is refused with a message', async ({ page, backendUrl }) => {
  await gotoSettings(page, backendUrl)
  const own = page.getByTestId('icon-lib-own')
  // an id with capital letters is not accepted
  await own.locator('#icon-lib-id').fill('Bad Id')
  await expect(own).toContainText('Lowercase letters')
  await expect(page.getByTestId('icon-lib-upload')).toBeDisabled()

  // a file without icons
  await own.locator('#icon-lib-id').fill(`${libId}-x`)
  await own.locator('#icon-lib-label').fill('Nothing')
  await page.getByTestId('icon-lib-file').setInputFiles({ name: 'x.zip', mimeType: 'application/zip', buffer: makeZip({ 'a.txt': 'x' }) })
  await page.getByTestId('icon-lib-upload').click()
  await expect(own).toContainText('No usable SVG icons', { timeout: 10_000 })

  // a download link into a private network is blocked (the default)
  await own.locator('#icon-lib-url').fill('http://127.0.0.1:9/icons.zip')
  await page.getByTestId('icon-lib-download').click()
  await expect(page.getByTestId('icon-lib-table')).toContainText(/private|blocked|not allowed|refus/i, { timeout: 15_000 })
})
