/**
 * E2E tests for the installable icon libraries (Settings → Icon libraries, application/icon_libraries.py).
 * DisplayHive ships no icons; the catalog download needs the internet and is covered by unit tests, so
 * here a library of one's own is uploaded as a ZIP file, served and removed again.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(60_000)

const SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M2 12h20" stroke="currentColor"/><script>alert(1)</script></svg>'

/** A ZIP file with stored (uncompressed) entries — enough for a test. */
function makeZip(files: Record<string, string>): Buffer {
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    return c >>> 0
  })
  const crc32 = (buf: Buffer) => {
    let c = 0xffffffff
    for (const b of buf) c = crcTable[(c ^ b) & 0xff]! ^ (c >>> 8)
    return (c ^ 0xffffffff) >>> 0
  }
  const parts: Buffer[] = []
  const central: Buffer[] = []
  let offset = 0
  for (const [name, text] of Object.entries(files)) {
    const nameBuf = Buffer.from(name)
    const data = Buffer.from(text)
    const header = Buffer.alloc(30)
    header.writeUInt32LE(0x04034b50, 0)
    header.writeUInt16LE(20, 4)
    header.writeUInt32LE(crc32(data), 14)
    header.writeUInt32LE(data.length, 18)
    header.writeUInt32LE(data.length, 22)
    header.writeUInt16LE(nameBuf.length, 26)
    parts.push(header, nameBuf, data)
    const entry = Buffer.alloc(46)
    entry.writeUInt32LE(0x02014b50, 0)
    entry.writeUInt16LE(20, 4)
    entry.writeUInt16LE(20, 6)
    entry.writeUInt32LE(crc32(data), 16)
    entry.writeUInt32LE(data.length, 20)
    entry.writeUInt32LE(data.length, 24)
    entry.writeUInt16LE(nameBuf.length, 28)
    entry.writeUInt32LE(offset, 42)
    central.push(entry, nameBuf)
    offset += header.length + nameBuf.length + data.length
  }
  const centralBuf = Buffer.concat(central)
  const end = Buffer.alloc(22)
  end.writeUInt32LE(0x06054b50, 0)
  end.writeUInt16LE(Object.keys(files).length, 8)
  end.writeUInt16LE(Object.keys(files).length, 10)
  end.writeUInt32LE(centralBuf.length, 12)
  end.writeUInt32LE(offset, 16)
  return Buffer.concat([...parts, centralBuf, end])
}

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
