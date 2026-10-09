import * as fs from 'node:fs'
import { test as base, APIRequestContext, Page } from '@playwright/test'
import { adminUrl } from './urls.js'
import { PORT_MAP_PATH } from './global-setup.js'
import { TEST_ADMIN_USERNAME, TEST_ADMIN_PASSWORD } from './testAdminCredentials.js'

/**
 * Custom fixtures for admin E2E tests.
 * - `apiRequest` is the built-in Playwright request context (re-exported for convenience)
 * - `backendUrl` resolves the correct per-worker Flask backend URL from the port map
 *    written by global-setup.ts (Option B isolated DB per worker).
 * - The default `page` fixture is overridden below so that EVERY test starts
 *   pre-authenticated: a real login is performed against this worker's backend
 *   (POST /admin/api/auth/login with the bootstrap admin credentials — see
 *   testAdminCredentials.ts / global-setup.ts); the session cookie goes into the
 *   page's browser context and the SPA's "signed in" hint into localStorage
 *   before any navigation. This matches the old behavior
 *   where a hardcoded devicekey made every admin page load "authenticated"
 *   automatically, without requiring every spec to opt in explicitly.
 * - `loginAsAdmin(page)` remains for specs that want to be explicit about it
 *   (the seeding already happened via the `page` fixture; it just navigates).
 * - `seedAdminAuth(page, request, workerBackendUrl)` is exported for the rare
 *   case (see adoption.spec.ts) where a spec creates its own BrowserContext/Page
 *   directly instead of using the `page` fixture, and must seed it manually.
 */

/**
 * Resolve the backend URL for the current Playwright worker.
 * Falls back to the env-var default if the port map is not present
 * (e.g. when running a single test outside the full suite).
 */
function resolveWorkerBackendUrl(workerIndex: number): string {
  try {
    const raw = fs.readFileSync(PORT_MAP_PATH, 'utf-8')
    const { portMap } = JSON.parse(raw) as { portMap: Record<string, number> }
    const workerCount = Object.keys(portMap).length
    const port = portMap[String(workerIndex % workerCount)]
    if (port) return `http://localhost:${port}`
  } catch {
    // port map not present — fall back to the env-var / default
  }
  return process.env.PLAYWRIGHT_BACKEND_URL || 'https://localhost:5000'
}

/**
 * Log in against *workerBackendUrl* and give *page* the session: the server's
 * HttpOnly cookie lands in the page's browser context (logging in through the
 * context's own request client), and the small "signed in" hint the SPA keeps in
 * localStorage (stores/auth.ts) plus the worker's backend URL are seeded with
 * addInitScript, so the SPA is authenticated and pointed at the right backend from
 * its very first load. Does not navigate — callers decide where to go.
 *
 * The cookie belongs to host `localhost`, whatever the port: the page (Vite) and this
 * worker's Flask instance share it, as a real deployment's page and socket would.
 */
export async function seedAdminAuth(
  page: Page,
  request: APIRequestContext,
  workerBackendUrl: string,
): Promise<void> {
  // (`request` is unused now: it is not tied to the page, so its cookies would not reach it.)
  void request
  const loginResponse = await page.context().request.post(`${workerBackendUrl}/admin/api/auth/login`, {
    data: { username: TEST_ADMIN_USERNAME, password: TEST_ADMIN_PASSWORD, session: 'cookie' },
    headers: { 'X-DisplayHive-Request': '1' },
    ignoreHTTPSErrors: true,
  })
  if (!loginResponse.ok()) {
    throw new Error(
      `seedAdminAuth: login failed (${loginResponse.status()}): ${await loginResponse.text()}`,
    )
  }
  const { username, expires_at } = await loginResponse.json()

  // Seed the "signed in" hint before the app boots so App.vue's authStore.restore()
  // asks the server (which accepts the cookie) and useSocket.ts's connect() goes ahead.
  await page.addInitScript(
    ({ username, expiresAt }: { username: string; expiresAt: number }) => {
      try {
        // Runs in the browser page; localStorage exists there at runtime but
        // isn't in the Node-oriented tsconfig lib, so reach it via globalThis.
        const ls = (globalThis as any).localStorage
        ls.setItem('displayhive_admin_session', JSON.stringify({ username, expiresAt, impersonator: null }))
      } catch (e) {}
    },
    { username, expiresAt: Date.parse(expires_at) },
  )

  // Inject the worker-specific backend URL so useSocket.ts connects to this
  // worker's Flask instance (and its isolated DB) rather than falling back
  // to window.location.origin or the global PLAYWRIGHT_BACKEND_URL.
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, workerBackendUrl)
}

type Fixtures = {
  apiRequest: APIRequestContext
  backendUrl: string
  loginAsAdmin: (page: Page) => Promise<void>
}

export const test = base.extend<Fixtures>({
  // re-export the built-in Playwright request context (re-exported for convenience)
  apiRequest: async ({ request }, use) => {
    await use(request)
  },

  // Resolves to the Flask backend URL for this specific worker.
  // Tests and fixtures can use this instead of the global PLAYWRIGHT_BACKEND_URL
  // so they naturally talk to their own isolated database.
  backendUrl: async ({}, use, workerInfo) => {
    const url = resolveWorkerBackendUrl(workerInfo.workerIndex)
    await use(url)
  },

  // Override the built-in `page` fixture: seed a valid admin JWT + this
  // worker's backend URL before handing the page to the test, so every spec
  // starts authenticated regardless of whether it calls loginAsAdmin.
  page: async ({ page, request }, use, workerInfo) => {
    const workerBackendUrl = resolveWorkerBackendUrl(workerInfo.workerIndex)
    await seedAdminAuth(page, request, workerBackendUrl)
    await use(page)
  },

  // Convenience helper for specs that want to be explicit: the `page` is
  // already authenticated (see override above), so this just navigates to
  // the admin SPA root and lets it boot in that session.
  loginAsAdmin: async ({}, use) => {
    const helper = async (page: Page) => {
      await page.goto(adminUrl)
    }
    await use(helper)
  },
})

export const expect = test.expect
export default test
