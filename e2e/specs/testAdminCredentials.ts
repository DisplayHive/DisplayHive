/**
 * Shared test-only admin credentials.
 *
 * global-setup.ts passes these to each spawned Flask worker as
 * ADMIN_BOOTSTRAP_USERNAME/ADMIN_BOOTSTRAP_PASSWORD so every isolated
 * per-worker database bootstraps the same known admin account, and
 * fixtures.ts uses the same values to log in via the real /admin/api/auth/login
 * endpoint. Override via env vars if a specific CI setup needs different values.
 */

export const TEST_ADMIN_USERNAME = process.env.ADMIN_BOOTSTRAP_USERNAME || 'admin'
export const TEST_ADMIN_PASSWORD = process.env.ADMIN_BOOTSTRAP_PASSWORD || 'test-admin-password-e2e'
