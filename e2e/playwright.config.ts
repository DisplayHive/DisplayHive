import process from 'node:process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, devices } from '@playwright/test'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Centralized, configurable URLs used by E2E tests.
// Override via environment variables:
//   PLAYWRIGHT_ADMIN_URL  — Vite dev/preview server (default: http://localhost:5173)
//   PLAYWRIGHT_SCREEN_URL — DisplayHive screen client URL (default: https://localhost:5000)
//   PLAYWRIGHT_BACKEND_URL — Flask SSL backend (default: https://localhost:5000)
const ADMIN_URL =
  process.env.PLAYWRIGHT_ADMIN_URL ||
  (process.env.CI ? 'http://localhost:4173' : 'http://localhost:5173')
const SCREEN_URL = process.env.PLAYWRIGHT_SCREEN_URL || 'https://localhost:5000'
const BACKEND_URL = process.env.PLAYWRIGHT_BACKEND_URL || 'https://localhost:5000'

// Expose to tests via process.env as a single source of truth
process.env.PLAYWRIGHT_ADMIN_URL = ADMIN_URL
process.env.PLAYWRIGHT_SCREEN_URL = SCREEN_URL
process.env.PLAYWRIGHT_BACKEND_URL = BACKEND_URL

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// require('dotenv').config();

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: './e2e',
  /* Run tests serially, one at a time — no parallel workers. */
  fullyParallel: false,
  workers: 1,
  /* Global setup/teardown: spawn per-worker Flask processes before tests, clean up after. */
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',
  /* Maximum time one test can run for. */
  timeout: 30 * 1000,
  expect: {
    /**
     * Maximum time expect() should wait for the condition to be met.
     * For example in `await expect(locator).toHaveText();`
     */
    timeout: 5000,
  },
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'html',
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Maximum time each action such as `click()` can take. Defaults to 0 (no limit). */
    actionTimeout: 0,
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL:
      process.env.PLAYWRIGHT_ADMIN_URL ||
      (process.env.CI ? 'http://localhost:4173' : 'http://localhost:5173'),

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',
    /* Capture screenshots only on test failure */
    screenshot: 'only-on-failure',
    /* Keep video recordings only on failure to aid debugging */
    video: 'retain-on-failure',

    /* Run headless unless PLAYWRIGHT_HEADED=1 is set */
    headless: process.env.PLAYWRIGHT_HEADED !== '1',
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // Prefer a specific Chromium revision (1194) executable if available.
        // You can override with the env var `PLAYWRIGHT_CHROMIUM_1194_PATH`.
        //aunchOptions: {
        // executablePath:
        //  process.env.PLAYWRIGHT_CHROMIUM_1194_PATH ||
        //  '/nix/store/flmcw3aq13z083rgd299f0zmnv5dr8pc-playwright-browsers/chromium-1194/chrome-linux/chrome',
        //},
      },
    },
    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
        // Prefer a specific Firefox executable (1495) if available.
        // Override with env var `PLAYWRIGHT_FIREFOX_1495_PATH` if needed.
        //    launchOptions: {
        //    executablePath:
        //    process.env.PLAYWRIGHT_FIREFOX_1495_PATH ||
        //  '/nix/store/flmcw3aq13z083rgd299f0zmnv5dr8pc-playwright-browsers/firefox-1495/firefox/firefox',
        // },
      },
    },
    //   {
    //    name: 'webkit',
    //    use: {
    //      ...devices['Desktop Safari'],
    // Use Nix-provided WebKit runner script by default. Override with
    // PLAYWRIGHT_WEBKIT_PW_RUN_PATH to point to a different wrapper.
    //     launchOptions: {
    //     executablePath:
    //     process.env.PLAYWRIGHT_WEBKIT_PW_RUN_PATH ||
    //   '/nix/store/flmcw3aq13z083rgd299f0zmnv5dr8pc-playwright-browsers/webkit-2215/pw_run.sh',
    // },
    //    },
    //  },

    /* Test against mobile viewports. */
    // {
    //   name: 'Mobile Chrome',
    //   use: {
    //     ...devices['Pixel 5'],
    //   },
    // },
    // {
    //   name: 'Mobile Safari',
    //   use: {
    //     ...devices['iPhone 12'],
    //   },
    // },

    /* Test against branded browsers. */
    // {
    //   name: 'Microsoft Edge',
    //   use: {
    //     channel: 'msedge',
    //   },
    // },
    // {
    //   name: 'Google Chrome',
    //   use: {
    //     channel: 'chrome',
    //   },
    // },
  ],

  /* Folder for test artifacts such as screenshots, videos, traces, etc. */
  outputDir: 'test-results/',

  /* Vite dev/preview server for the admin SPA.
   * Flask workers are started by global-setup.ts instead of webServer, so the
   * Socket.IO proxy in vite.config.ts is bypassed for sockets — each page
   * injects __DISPLAYHIVE_TEST_BACKEND_URL__ directly to reach its worker's
   * Flask port. Plain REST fetches (export/import) go through Vite's static
   * proxy though, which must be pointed at the same worker port via
   * VITE_BACKEND_URL — otherwise it falls back to its default (port 5000),
   * where nothing is listening during tests. With `workers: 1` there's only
   * ever one worker (index 0), whose port is PW_BASE_PORT (see global-setup.ts). */
  webServer: {
    /**
     * Vite dev server (admin SPA).
     * Use the dev server by default for faster feedback loop.
     * Use the preview server on CI for more realistic testing.
     */
    // CI serves the built app: build first, or the tests run against whatever dist/ held before
    // (stale code gives phantom failures).
    command: process.env.CI ? 'npm run build-only && npm run preview' : 'npm run dev',
    timeout: 180_000,
    cwd: path.resolve(__dirname, '../frontends/admin'),
    port: process.env.CI ? 4173 : 5173,
    reuseExistingServer: !process.env.CI,
    env: {
      ...process.env,
      VITE_BACKEND_URL: `http://localhost:${parseInt(process.env.PW_BASE_PORT || '5001', 10)}`,
    },
  },
})
