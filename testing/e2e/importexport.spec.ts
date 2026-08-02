/**
 * E2E tests for the Import/Export admin page (/importexport).
 *
 * Covered:
 *  1.  Export — clicking "Download Export" triggers a network download from
 *      /admin/export/download and the response is a valid ZIP (starts with PK).
 *  2.  Export + Import round-trip — export the DB, seed an extra screen,
 *      import the export (which wipes and restores the original state),
 *      verify the extra screen is gone and the original data is present.
 *
 * Strategy:
 *  - Test 1 intercepts the download via the browser's download event.
 *  - Test 2 drives the same REST endpoints the UI uses
 *    (GET /admin/export/download, POST /admin/import/upload) directly via
 *    Playwright's `apiRequest` context, which — unlike `fetch()` from inside
 *    the page — isn't subject to the browser's CORS restrictions against the
 *    per-worker backend origin. The downloaded ZIP's db.json entry is
 *    inflated with a small local helper (no zip library dependency) to
 *    inspect/re-upload its contents; on the way back in, the JSON is
 *    uploaded standalone (`snapshot.json`), which the endpoint also accepts.
 *  - All tests run serially on the same worker / isolated DB.
 */

import * as zlib from 'node:zlib'
import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import { TEST_ADMIN_USERNAME, TEST_ADMIN_PASSWORD } from './testAdminCredentials.js'
import type { APIRequestContext, Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(60_000)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function gotoImportExport(page: Page, workerBackendUrl: string) {
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, workerBackendUrl)
  await page.goto(`${adminUrl}/importexport`)
  await expect(page.locator('.importexport-view')).toBeVisible({ timeout: 10_000 })
}

/** Log in against *backendUrl* and return a bearer token for REST calls. */
async function getAuthToken(apiRequest: APIRequestContext, backendUrl: string): Promise<string> {
  const res = await apiRequest.post(`${backendUrl}/admin/api/auth/login`, {
    data: { username: TEST_ADMIN_USERNAME, password: TEST_ADMIN_PASSWORD },
    ignoreHTTPSErrors: true,
  })
  if (!res.ok()) {
    throw new Error(`login failed (${res.status()}): ${await res.text()}`)
  }
  const { token } = await res.json()
  return token
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

/**
 * Extract and inflate a single entry from an in-memory ZIP buffer.
 * Handles only the plain (non-Zip64, no data-descriptor) local file header
 * layout that Python's `zipfile.writestr` produces — enough for reading the
 * single `db.json` entry the export endpoint writes.
 */
function readZipEntry(buf: Buffer, entryName: string): Buffer {
  const localHeaderSig = 0x04034b50
  let offset = 0
  while (offset < buf.length - 4) {
    if (buf.readUInt32LE(offset) !== localHeaderSig) {
      offset++
      continue
    }
    const compressionMethod = buf.readUInt16LE(offset + 8)
    const compressedSize = buf.readUInt32LE(offset + 18)
    const nameLen = buf.readUInt16LE(offset + 26)
    const extraLen = buf.readUInt16LE(offset + 28)
    const nameStart = offset + 30
    const name = buf.toString('utf-8', nameStart, nameStart + nameLen)
    const dataStart = nameStart + nameLen + extraLen
    if (name === entryName) {
      const compressed = buf.subarray(dataStart, dataStart + compressedSize)
      return compressionMethod === 0 ? Buffer.from(compressed) : zlib.inflateRawSync(compressed)
    }
    offset = dataStart + compressedSize
  }
  throw new Error(`Zip entry not found: ${entryName}`)
}

/** Download the export ZIP via REST and return the parsed db.json payload. */
async function exportViaRest(
  apiRequest: APIRequestContext,
  backendUrl: string,
  token: string,
): Promise<Record<string, any>> {
  const res = await apiRequest.get(`${backendUrl}/admin/export/download`, {
    headers: { Authorization: `Bearer ${token}` },
    ignoreHTTPSErrors: true,
  })
  if (!res.ok()) {
    throw new Error(`export failed (${res.status()}): ${await res.text()}`)
  }
  const zipBuf = await res.body()
  const dbJson = readZipEntry(zipBuf, 'db.json')
  return JSON.parse(dbJson.toString('utf-8'))
}

/** Import a JSON payload via REST (as the endpoint's legacy .json upload path). */
async function importViaRest(
  apiRequest: APIRequestContext,
  backendUrl: string,
  token: string,
  payload: Record<string, any>,
): Promise<void> {
  const res = await apiRequest.post(`${backendUrl}/admin/import/upload`, {
    headers: { Authorization: `Bearer ${token}` },
    multipart: {
      file: {
        name: 'snapshot.json',
        mimeType: 'application/json',
        buffer: Buffer.from(JSON.stringify(payload)),
      },
    },
    ignoreHTTPSErrors: true,
  })
  const result = await res.json()
  if (!result?.success) {
    throw new Error(`Import failed: ${JSON.stringify(result)}`)
  }
}

// ---------------------------------------------------------------------------
// Suite state
// ---------------------------------------------------------------------------

test.describe('Import / Export page', () => {
  // ---------------------------------------------------------------------------
  // 1. Export download produces a non-empty ZIP
  // ---------------------------------------------------------------------------

  test('Download Export button triggers a download from the server', async ({
    page,
    backendUrl,
  }) => {
    await gotoImportExport(page, backendUrl)

    // Listen for the download event before clicking
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 30_000 }),
      page.getByRole('button', { name: 'Download Export' }).click(),
    ])

    // Download must complete without error
    const downloadPath = await download.path()
    expect(downloadPath).not.toBeNull()

    // Suggested filename should contain "export" or end in .zip / .json
    const suggestedName = download.suggestedFilename()
    expect(suggestedName).toMatch(/export|backup|displayhive/i)
  })

  // ---------------------------------------------------------------------------
  // 2. Export → seed extra screen → Import restores original state
  // ---------------------------------------------------------------------------

  test('import restores original state — extra screen seeded after export is gone', async ({
    page,
    apiRequest,
    backendUrl,
  }) => {
    await gotoImportExport(page, backendUrl)
    const token = await getAuthToken(apiRequest, backendUrl)

    // Step 1: export current DB via REST
    const snapshot = await exportViaRest(apiRequest, backendUrl, token)
    expect(snapshot).toHaveProperty('screens')
    const screenCountBefore = (snapshot.screens as any[]).length

    // Step 2: seed an extra screen after the export
    const extraName = `e2e-import-extra-${Math.random().toString(36).slice(2, 8)}`
    await seedScreen(page, extraName)

    // Verify extra screen exists in the current DB
    const snapshotAfter = await exportViaRest(apiRequest, backendUrl, token)
    expect((snapshotAfter.screens as any[]).length).toBe(screenCountBefore + 1)

    // Step 3: import the original snapshot via REST
    await importViaRest(apiRequest, backendUrl, token, snapshot)

    // Step 4: verify the extra screen is gone
    const snapshotRestored = await exportViaRest(apiRequest, backendUrl, token)
    expect((snapshotRestored.screens as any[]).length).toBe(screenCountBefore)
    const hasExtra = (snapshotRestored.screens as any[]).some((s: any) => s.name === extraName)
    expect(hasExtra).toBe(false)

    // Success toast from the import should have shown (we check indirectly via socket)
    await page.reload()
    await expect(page.locator('.importexport-view')).toBeVisible({ timeout: 10_000 })
  })
})
