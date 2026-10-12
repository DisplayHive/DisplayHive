// Centralized URL helper for E2E tests.
// Tests should import from './urls.js' to get consistent admin/screen/backend endpoints.
// All URLs can be overridden via environment variables set before running Playwright.
export const adminUrl = process.env.PLAYWRIGHT_ADMIN_URL
  ? `${process.env.PLAYWRIGHT_ADMIN_URL}/admin`
  : 'http://localhost:5173/admin'
export const screenUrl = process.env.PLAYWRIGHT_SCREEN_URL || 'https://localhost:5000'
export const backendUrl = process.env.PLAYWRIGHT_BACKEND_URL || 'https://localhost:5000'

export default { adminUrl, screenUrl, backendUrl }
