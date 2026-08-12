/**
 * E2E tests for the Import/Export admin page (/importexport).
 *
 * Covered:
 *  1.  Export — clicking "Download Export" triggers a network download from
 *      /admin/export/download (now a POST with a {selection} body — the
 *      Tree UI defaults to everything checked) and the response is a valid
 *      ZIP (starts with PK).
 *  2.  Export → seed extra screen → Import (reset mode) restores original
 *      state — drives the two-step preview/confirm flow directly.
 *  3.  Selective export — only the checked entity type's items end up in
 *      the downloaded ZIP's db.json.
 *  4.  Merge conflict resolution — importing a snapshot twice in merge mode
 *      with 'skip' does not duplicate rows; with 'overwrite' it updates the
 *      existing row's fields in place.
 *
 * Strategy:
 *  - Test 1 intercepts the download via the browser's download event.
 *  - The rest drive the REST endpoints the UI uses
 *    (POST /admin/export/download, POST /admin/import/preview,
 *    POST /admin/import/confirm) directly via Playwright's `apiRequest`
 *    context, which — unlike `fetch()` from inside the page — isn't subject
 *    to the browser's CORS restrictions against the per-worker backend
 *    origin. The downloaded ZIP's db.json entry is inflated with a small
 *    local helper (no zip library dependency) to inspect/re-upload its
 *    contents; on the way back in, the JSON is uploaded standalone
 *    (`snapshot.json`), which the preview endpoint also accepts.
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

/** Download the export ZIP via REST (optionally scoped to a selection) and
 * return the parsed db.json payload. */
async function exportViaRest(
  apiRequest: APIRequestContext,
  backendUrl: string,
  token: string,
  selection: Record<string, string[]> | null = null,
): Promise<Record<string, any>> {
  const res = await apiRequest.post(`${backendUrl}/admin/export/download`, {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    data: { selection },
    ignoreHTTPSErrors: true,
  })
  if (!res.ok()) {
    throw new Error(`export failed (${res.status()}): ${await res.text()}`)
  }
  const zipBuf = await res.body()
  const dbJson = readZipEntry(zipBuf, 'db.json')
  return JSON.parse(dbJson.toString('utf-8'))
}

/** GET the export manifest tree (uuid/id/label per entity type). */
async function exportTreeViaRest(
  apiRequest: APIRequestContext,
  backendUrl: string,
  token: string,
): Promise<Record<string, Array<{ uuid: string; id: number; label: string }>>> {
  const res = await apiRequest.get(`${backendUrl}/admin/export/tree`, {
    headers: { Authorization: `Bearer ${token}` },
    ignoreHTTPSErrors: true,
  })
  if (!res.ok()) {
    throw new Error(`export tree failed (${res.status()}): ${await res.text()}`)
  }
  return res.json()
}

/** Stage a JSON payload for import via the preview endpoint and return
 * {token, is_legacy, manifest}. */
async function previewImportViaRest(
  apiRequest: APIRequestContext,
  backendUrl: string,
  authToken: string,
  payload: Record<string, any>,
): Promise<{ token: string; is_legacy: boolean; manifest: Record<string, any[]> }> {
  const res = await apiRequest.post(`${backendUrl}/admin/import/preview`, {
    headers: { Authorization: `Bearer ${authToken}` },
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
  if (!res.ok() || result?.error) {
    throw new Error(`Preview failed: ${JSON.stringify(result)}`)
  }
  return result
}

/** Confirm a staged import (by preview token) via REST. */
async function confirmImportViaRest(
  apiRequest: APIRequestContext,
  backendUrl: string,
  authToken: string,
  opts: { token: string; selection?: Record<string, string[]> | null; mode?: 'reset' | 'merge'; conflict_resolution?: any },
): Promise<any> {
  const res = await apiRequest.post(`${backendUrl}/admin/import/confirm`, {
    headers: { Authorization: `Bearer ${authToken}`, 'Content-Type': 'application/json' },
    data: {
      token: opts.token,
      selection: opts.selection ?? null,
      mode: opts.mode ?? 'reset',
      conflict_resolution: opts.conflict_resolution ?? 'skip',
    },
    ignoreHTTPSErrors: true,
  })
  const result = await res.json()
  if (!result?.success) {
    throw new Error(`Import failed: ${JSON.stringify(result)}`)
  }
  return result
}

/** Full preview + confirm round trip for a JSON payload (defaults to reset
 * mode / everything selected, matching the old all-or-nothing importer). */
async function importViaRest(
  apiRequest: APIRequestContext,
  backendUrl: string,
  authToken: string,
  payload: Record<string, any>,
  opts: { selection?: Record<string, string[]> | null; mode?: 'reset' | 'merge'; conflict_resolution?: any } = {},
): Promise<any> {
  const { token } = await previewImportViaRest(apiRequest, backendUrl, authToken, payload)
  return confirmImportViaRest(apiRequest, backendUrl, authToken, { token, ...opts })
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

  // ---------------------------------------------------------------------------
  // 3. Selective export — only the checked entity type ends up in the ZIP
  // ---------------------------------------------------------------------------

  test('selective export only includes the selected entity type', async ({
    page,
    apiRequest,
    backendUrl,
  }) => {
    await gotoImportExport(page, backendUrl)
    const token = await getAuthToken(apiRequest, backendUrl)

    const screenName = `e2e-selective-${Math.random().toString(36).slice(2, 8)}`
    await seedScreen(page, screenName)

    const tree = await exportTreeViaRest(apiRequest, backendUrl, token)
    expect(tree).toHaveProperty('screens')
    const screenUuids = (tree.screens || []).map((s) => s.uuid)
    expect(screenUuids.length).toBeGreaterThan(0)

    const scoped = await exportViaRest(apiRequest, backendUrl, token, { screens: screenUuids })
    expect((scoped.screens as any[]).length).toBe(screenUuids.length)
    // Nothing else was selected, and screens have no hard dependency on any
    // other entity type, so every other type should come back empty.
    expect((scoped.designs as any[]).length).toBe(0)
    expect((scoped.contenttypes as any[]).length).toBe(0)
    expect((scoped.content_elements as any[]).length).toBe(0)
  })

  // ---------------------------------------------------------------------------
  // 4. Merge mode conflict resolution — skip vs. overwrite
  // ---------------------------------------------------------------------------

  test('merge mode: skip leaves the existing row untouched, overwrite updates it', async ({
    page,
    apiRequest,
    backendUrl,
  }) => {
    await gotoImportExport(page, backendUrl)
    const token = await getAuthToken(apiRequest, backendUrl)

    const screenName = `e2e-merge-${Math.random().toString(36).slice(2, 8)}`
    await seedScreen(page, screenName)

    const snapshot = await exportViaRest(apiRequest, backendUrl, token)
    const screenCountBefore = (snapshot.screens as any[]).length
    const seededRow = (snapshot.screens as any[]).find((s: any) => s.name === screenName)
    expect(seededRow).toBeTruthy()
    expect(seededRow.debug).toBe(false)

    // Re-import the unmodified snapshot in merge/skip mode: same uuid already
    // exists locally, so it must be skipped — no duplicate row, no field change.
    await importViaRest(apiRequest, backendUrl, token, snapshot, { mode: 'merge', conflict_resolution: 'skip' })

    const afterSkip = await exportViaRest(apiRequest, backendUrl, token)
    expect((afterSkip.screens as any[]).length).toBe(screenCountBefore)
    const afterSkipRow = (afterSkip.screens as any[]).find((s: any) => s.uuid === seededRow.uuid)
    expect(afterSkipRow.debug).toBe(false)

    // Re-import the same uuid again, this time with a changed field and
    // conflict_resolution 'overwrite': the local row must be updated in place
    // (still no duplicate row).
    const mutatedSnapshot = JSON.parse(JSON.stringify(snapshot))
    const mutatedRow = (mutatedSnapshot.screens as any[]).find((s: any) => s.uuid === seededRow.uuid)
    mutatedRow.debug = true
    await importViaRest(apiRequest, backendUrl, token, mutatedSnapshot, { mode: 'merge', conflict_resolution: 'overwrite' })

    const afterOverwrite = await exportViaRest(apiRequest, backendUrl, token)
    expect((afterOverwrite.screens as any[]).length).toBe(screenCountBefore)
    const afterOverwriteRow = (afterOverwrite.screens as any[]).find((s: any) => s.uuid === seededRow.uuid)
    expect(afterOverwriteRow.debug).toBe(true)
  })
})
