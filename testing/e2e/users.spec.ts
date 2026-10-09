/**
 * E2E tests for the Users & Rights page (/users).
 *
 * Covered: the account list, creating / editing / (de)activating / deleting an account, the
 * recent-logins popover, creating / renaming / deleting a group, the group rights matrix, and
 * a user's group membership and right overrides.
 *
 * Strategy: one account and one group are created through the UI and used across the tests,
 * which run serially; the last tests delete them again.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(60_000)

const suffix = Math.random().toString(36).slice(2, 7)
const userName = `e2e-user-${suffix}`
const userRenamed = `${userName}-ren`
const groupName = `e2e-group-${suffix}`
const groupRenamed = `${groupName}-ren`

async function gotoUsers(page: Page, backendUrl: string) {
  await page.setViewportSize({ width: 1400, height: 1200 })
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, backendUrl)
  await page.goto(`${adminUrl}/users`)
  await expect(page.locator('[data-tour="users-page"]')).toBeVisible({ timeout: 15_000 })
  await expect(page.locator('tr', { hasText: 'admin' }).first()).toBeVisible({ timeout: 10_000 })
}

const row = (page: Page, text: string) => page.locator('tr', { hasText: text })
const groupRow = (page: Page, text: string) => page.locator('[data-tour="users-groups-table"] tr', { hasText: text })
const toast = (page: Page) => page.locator('.p-toast')

async function openGroupsTab(page: Page) {
  await page.getByRole('tab', { name: 'Groups' }).click()
  await expect(page.locator('[data-tour="users-groups-table"]')).toBeVisible()
}

test.describe('Users & Rights page', () => {
  test('lists the signed-in account with its group', async ({ page, backendUrl }) => {
    await gotoUsers(page, backendUrl)
    await expect(row(page, 'admin').first()).toContainText('Superadmin')
    await expect(page.getByRole('button', { name: 'Add User' })).toBeVisible()
  })

  test('creating an account validates and then adds a row', async ({ page, backendUrl }) => {
    await gotoUsers(page, backendUrl)
    await page.getByRole('button', { name: 'Add User' }).click()
    const dialog = page.locator('.p-dialog', { hasText: 'Add User' })
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(toast(page)).toContainText(/required|Username/i, { timeout: 8_000 })
    await dialog.locator('#user-username').fill(userName)
    await dialog.locator('input[type="password"]').fill('Correct-Horse-9!')
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(toast(page)).toContainText(/User created/i, { timeout: 8_000 })
    await expect(dialog).toBeHidden({ timeout: 5_000 })
    await expect(row(page, userName)).toBeVisible({ timeout: 10_000 })
  })

  test('a taken username is refused', async ({ page, backendUrl }) => {
    await gotoUsers(page, backendUrl)
    await page.getByRole('button', { name: 'Add User' }).click()
    const dialog = page.locator('.p-dialog', { hasText: 'Add User' })
    await dialog.locator('#user-username').fill(userName)
    await dialog.locator('input[type="password"]').fill('Correct-Horse-9!')
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(toast(page)).toContainText(/already exists/i, { timeout: 8_000 })
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toBeHidden()
  })

  test('editing renames the account', async ({ page, backendUrl }) => {
    await gotoUsers(page, backendUrl)
    await row(page, userName).locator('button[title="Edit account"]').click()
    const dialog = page.locator('.p-dialog', { hasText: 'Edit User' })
    await expect(dialog).toBeVisible()
    await dialog.locator('#user-username').fill(userRenamed)
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(toast(page)).toContainText(/User updated/i, { timeout: 8_000 })
    await expect(row(page, userRenamed)).toBeVisible({ timeout: 10_000 })
  })

  test('the Active switch deactivates and reactivates', async ({ page, backendUrl }) => {
    await gotoUsers(page, backendUrl)
    const toggle = row(page, userRenamed).locator('.p-toggleswitch').first()
    await toggle.click()
    await expect(toast(page)).toContainText(/deactivated/i, { timeout: 8_000 })
    await expect(row(page, userRenamed).locator('.p-toggleswitch-checked')).toHaveCount(0)
    await toggle.click()
    await expect(toast(page)).toContainText(/activated/i, { timeout: 8_000 })
    await expect(row(page, userRenamed).locator('.p-toggleswitch-checked')).toHaveCount(1)
  })

  test('the recent-logins popover opens', async ({ page, backendUrl }) => {
    await gotoUsers(page, backendUrl)
    await row(page, 'admin').first().locator('button[title="Recent logins"]').click()
    await expect(page.locator('.logins-popover')).toContainText('Recent logins')
    await expect(page.locator('.logins-popover')).not.toContainText('No recorded logins yet', { timeout: 8_000 })
    await page.keyboard.press('Escape')
  })

  test('creating a group adds a row, and a duplicate name is refused', async ({ page, backendUrl }) => {
    await gotoUsers(page, backendUrl)
    await openGroupsTab(page)
    await page.getByRole('button', { name: 'Add Group' }).click()
    const dialog = page.locator('.p-dialog', { hasText: 'Add Group' })
    await dialog.locator('#group-name').fill(groupName)
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(toast(page)).toContainText(/Group created/i, { timeout: 8_000 })
    await expect(row(page, groupName)).toBeVisible({ timeout: 10_000 })

    await page.getByRole('button', { name: 'Add Group' }).click()
    const again = page.locator('.p-dialog', { hasText: 'Add Group' })
    await again.locator('#group-name').fill(groupName)
    await again.getByRole('button', { name: 'Save' }).click()
    await expect(toast(page)).toContainText(/already exists/i, { timeout: 8_000 })
    await again.getByRole('button', { name: 'Cancel' }).click()
  })

  test('renaming a group updates its row', async ({ page, backendUrl }) => {
    await gotoUsers(page, backendUrl)
    await openGroupsTab(page)
    await row(page, groupName).locator('button[title="Rename / move"]').click()
    const dialog = page.locator('.p-dialog', { hasText: 'Edit Group' })
    await dialog.locator('#group-name').fill(groupRenamed)
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(toast(page)).toContainText(/Group updated/i, { timeout: 8_000 })
    await expect(row(page, groupRenamed)).toBeVisible({ timeout: 10_000 })
  })

  test('the group rights matrix grants and revokes rights', async ({ page, backendUrl }) => {
    await gotoUsers(page, backendUrl)
    await openGroupsTab(page)
    await expect(row(page, groupRenamed)).toContainText('0 granted')
    await row(page, groupRenamed).locator('button[title="Edit rights"]').click()
    const dialog = page.locator('.p-dialog', { hasText: `Rights — ${groupRenamed}` })
    await expect(dialog).toBeVisible()
    // grant the first section's first right
    await dialog.locator('.rights-row .p-checkbox').first().click()
    await expect(dialog.locator('.rights-row .p-checkbox-checked').first()).toBeVisible({ timeout: 8_000 })
    await dialog.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()
    await expect(row(page, groupRenamed)).not.toContainText('0 granted', { timeout: 8_000 })
    // "All" then "None" for everything
    await row(page, groupRenamed).locator('button[title="Edit rights"]').click()
    await dialog.locator('.rights-global-actions').getByRole('button', { name: 'All' }).click()
    await dialog.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()
    await expect(row(page, groupRenamed)).not.toContainText('0 granted', { timeout: 8_000 })
    await row(page, groupRenamed).locator('button[title="Edit rights"]').click()
    await dialog.locator('.rights-global-actions').getByRole('button', { name: 'None' }).click()
    await dialog.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()
    await expect(row(page, groupRenamed)).toContainText('0 granted', { timeout: 8_000 })
  })

  test('a user can be put into a group, and gets right overrides', async ({ page, backendUrl }) => {
    await gotoUsers(page, backendUrl)
    await row(page, userRenamed).locator('button[title="Manage rights"]').click()
    const dialog = page.locator('.p-dialog', { hasText: `Rights — ${userRenamed}` })
    await expect(dialog).toBeVisible()
    await dialog.locator('.p-multiselect').click()
    await page.getByRole('option', { name: groupRenamed }).click()
    await page.keyboard.press('Escape')
    await dialog.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(toast(page)).toContainText(/Group membership updated/i, { timeout: 8_000 })
    await expect(dialog.locator('.p-multiselect')).toContainText(groupRenamed)
    // an override: allow the first right
    const select = dialog.locator('.rights-row--user .p-select').first()
    await select.click()
    await page.getByRole('option', { name: 'Allow', exact: true }).click()
    await expect(dialog.locator('.rights-row--user').first()).toContainText('allowed', { timeout: 8_000 })
    await dialog.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()
    await expect(row(page, userRenamed)).toContainText(groupRenamed, { timeout: 8_000 })
  })

  test('deleting a group asks first and removes it', async ({ page, backendUrl }) => {
    await gotoUsers(page, backendUrl)
    await openGroupsTab(page)
    await groupRow(page, groupRenamed).locator('button[title="Delete"]').click()
    await expect(page.locator('.p-confirmdialog')).toContainText(groupRenamed)
    await page.locator('.p-confirmdialog').getByRole('button', { name: 'Yes' }).click()
    await expect(toast(page)).toContainText(/Group deleted/i, { timeout: 8_000 })
    await expect(groupRow(page, groupRenamed)).toHaveCount(0, { timeout: 10_000 })
  })

  test('deleting an account asks first and removes it', async ({ page, backendUrl }) => {
    await gotoUsers(page, backendUrl)
    await row(page, userRenamed).locator('button[title="Delete"]').click()
    await expect(page.locator('.p-confirmdialog')).toContainText(userRenamed)
    await page.locator('.p-confirmdialog').getByRole('button', { name: 'Yes' }).click()
    await expect(toast(page)).toContainText(/User deleted/i, { timeout: 8_000 })
    await expect(row(page, userRenamed)).toHaveCount(0, { timeout: 10_000 })
  })
})
