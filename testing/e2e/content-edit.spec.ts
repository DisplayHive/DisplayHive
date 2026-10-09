/**
 * E2E tests for the content edit page (/content/new, /content/:id/edit, /content/:id/copy).
 *
 * Covered: choosing a content type, the field and title inputs (auto-title), validation, creating,
 * editing with "Update" and "Save", copying, the scheduling / duration summaries, screen-group
 * assignment, the live preview pane and the `contenttype_id` shortcut.
 *
 * Strategy: a layout with one container, a content type with one text field and a screen group are
 * seeded via socket; tests run serially and the last one cleans up.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(60_000)

const suffix = Math.random().toString(36).slice(2, 7)
const ctName = `e2e-ce-ct-${suffix}`
const groupName = `e2e-ce-group-${suffix}`
const headline = `Headline ${suffix}`

let containerId = 0
let layoutId = 0
let contenttypeId = 0
let groupId = 0
let contentId = 0

async function emitAck<T = any>(page: Page, event: string, data: unknown): Promise<T> {
  return page.evaluate(
    ({ event, data }) =>
      new Promise<any>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { reject(new Error('Socket not available')); return }
        const t = setTimeout(() => reject(new Error(`Timed out: ${event}`)), 10_000)
        socket.emit(event, data, (ack: any) => { clearTimeout(t); resolve(ack) })
      }),
    { event, data },
  )
}

async function open(page: Page, backendUrl: string, path: string) {
  await page.setViewportSize({ width: 1500, height: 1300 })
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, backendUrl)
  await page.goto(`${adminUrl}${path}`)
}

const toast = (page: Page) => page.locator('.p-toast')
const fieldInput = (page: Page) => page.locator('.tag-fields-section input[type="text"], .tag-fields-section input:not([type])').first()

test.describe('Content edit page', () => {
  test('seed: container, layout, content type, screen group', async ({ page, backendUrl }) => {
    await open(page, backendUrl, '/content')
    await expect(page.locator('.content-view')).toBeVisible({ timeout: 15_000 })
    await page.waitForTimeout(1000)
    const c = await emitAck(page, 'displayhive:admin:cts:create_container', { name: `ce-c-${suffix}`, order: 1, top: 5, left: 5, width: 90, height: 90 })
    containerId = c.id
    const l = await emitAck(page, 'displayhive:admin:cts:create_layout', { name: `e2e-ce-layout-${suffix}`, description: '', container_ids: [containerId] })
    layoutId = l.id
    const ct = await emitAck(page, 'displayhive:admin:cts:create_contenttype', {
      name: ctName, layout_id: layoutId,
      tagconfigs: [{ name: 'headline', title: 'Headline', field_handler: 'textklein', contentcontainer_id: containerId, order: 0 }],
    })
    expect(ct.success).toBe(true)
    contenttypeId = ct.id
    const g = await emitAck(page, 'displayhive:admin:cts:create_screengroup', { name: groupName })
    expect(g.success).toBe(true)
    groupId = g.screengroup_id
  })

  test('/content/new asks for a content type and shows its fields', async ({ page, backendUrl }) => {
    await open(page, backendUrl, '/content/new')
    const dialog = page.locator('.p-dialog', { hasText: 'Select Content Type' })
    await expect(dialog).toBeVisible({ timeout: 15_000 })
    await dialog.locator('.contenttype-card', { hasText: ctName }).click()
    await expect(dialog).toBeHidden({ timeout: 5_000 })
    await expect(page.locator('.content-type-banner')).toContainText(ctName)
    await expect(page.locator('.tag-fields-section')).toContainText('Headline')
    await expect(fieldInput(page)).toBeVisible()
  })

  test('the contenttype_id shortcut skips the dialog, and the preview pane appears', async ({ page, backendUrl }) => {
    await open(page, backendUrl, `/content/new?contenttype_id=${contenttypeId}`)
    await expect(page.locator('.content-type-banner')).toContainText(ctName, { timeout: 15_000 })
    await expect(page.locator('.p-dialog', { hasText: 'Select Content Type' })).toHaveCount(0)
    await expect(page.locator('.content-edit-preview')).toBeVisible()
    await fieldInput(page).fill('preview text')
    await expect(page.locator('.content-edit-preview-iframe')).toBeVisible({ timeout: 10_000 })
  })

  test('a title is required, and a typed text fills the title automatically', async ({ page, backendUrl }) => {
    await open(page, backendUrl, `/content/new?contenttype_id=${contenttypeId}`)
    await expect(page.locator('.content-type-banner')).toContainText(ctName, { timeout: 15_000 })
    await page.getByRole('button', { name: 'Create', exact: true }).click()
    await expect(toast(page)).toContainText(/Title is required/i, { timeout: 5_000 })
    await fieldInput(page).fill(headline)
    await expect(page.locator('#create-title')).toHaveValue(headline, { timeout: 5_000 })
    // a title typed by hand is not overwritten any more
    await page.locator('#create-title').fill('Typed by hand')
    await fieldInput(page).fill(`${headline} again`)
    await expect(page.locator('#create-title')).toHaveValue('Typed by hand')
  })

  test('the Delivery settings show summaries', async ({ page, backendUrl }) => {
    await open(page, backendUrl, `/content/new?contenttype_id=${contenttypeId}`)
    await expect(page.locator('.content-type-banner')).toContainText(ctName, { timeout: 15_000 })
    await expect(page.locator('[data-tour="content-scheduling"] summary')).toContainText('no restriction')
    await expect(page.locator('[data-tour="content-screens"] summary')).toContainText('none selected')
    await page.locator('[data-tour="content-duration"] summary').click()
    await page.getByRole('button', { name: '20s', exact: true }).click()
    await expect(page.locator('[data-tour="content-duration"] summary')).toContainText('20s')
    await page.locator('[data-tour="content-screens"] summary').click()
    await page.getByLabel(groupName).check()
    await expect(page.locator('[data-tour="content-screens"] summary')).toContainText('1 selected')
  })

  test('creating content goes back to the list with the new row', async ({ page, backendUrl }) => {
    await open(page, backendUrl, `/content/new?contenttype_id=${contenttypeId}`)
    await expect(page.locator('.content-type-banner')).toContainText(ctName, { timeout: 15_000 })
    await fieldInput(page).fill(headline)
    await page.locator('[data-tour="content-screens"] summary').click()
    await page.getByLabel(groupName).check()
    await page.getByRole('button', { name: 'Create', exact: true }).click()
    await expect(toast(page)).toContainText(/Content created successfully/i, { timeout: 8_000 })
    await expect(page).toHaveURL(/\/content$/, { timeout: 8_000 })
    const row = page.locator('tr', { hasText: headline })
    await expect(row).toBeVisible({ timeout: 10_000 })
    await row.locator('button:has(.pi-pencil)').click()
    await expect(page).toHaveURL(/\/content\/(\d+)\/edit/)
    contentId = Number(page.url().match(/\/content\/(\d+)\/edit/)![1])
  })

  test('editing shows the saved values; Update stays, Save returns to the list', async ({ page, backendUrl }) => {
    await open(page, backendUrl, `/content/${contentId}/edit`)
    await expect(page.locator('#create-title')).toHaveValue(headline, { timeout: 15_000 })
    await expect(fieldInput(page)).toHaveValue(headline)
    // the saved screen group is checked
    await page.locator('[data-tour="content-screens"] summary').click()
    await expect(page.getByLabel(groupName)).toBeChecked()
    await fieldInput(page).fill(`${headline} v2`)
    await page.getByRole('button', { name: 'Update', exact: true }).click()
    await expect(toast(page)).toContainText(/Content updated successfully/i, { timeout: 8_000 })
    await expect(page).toHaveURL(new RegExp(`/content/${contentId}/edit`))
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(page).toHaveURL(/\/content$/, { timeout: 8_000 })
    // the field changed, the title (typed once) did not
    await open(page, backendUrl, `/content/${contentId}/edit`)
    await expect(fieldInput(page)).toHaveValue(`${headline} v2`, { timeout: 15_000 })
    await expect(page.locator('#create-title')).toHaveValue(headline)
  })

  test('unchecking the screen group is saved', async ({ page, backendUrl }) => {
    await open(page, backendUrl, `/content/${contentId}/edit`)
    await expect(page.locator('#create-title')).toHaveValue(headline, { timeout: 15_000 })
    await page.locator('[data-tour="content-screens"] summary').click()
    await page.getByLabel(groupName).uncheck()
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(page).toHaveURL(/\/content$/, { timeout: 8_000 })
    await open(page, backendUrl, `/content/${contentId}/edit`)
    await expect(page.locator('#create-title')).toHaveValue(headline, { timeout: 15_000 })
    await page.locator('[data-tour="content-screens"] summary').click()
    await expect(page.getByLabel(groupName)).not.toBeChecked()
  })

  test('copying prefills a copy that is saved as a new element', async ({ page, backendUrl }) => {
    await open(page, backendUrl, `/content/${contentId}/copy`)
    await expect(page.locator('#create-title')).toHaveValue(`Copy of ${headline}`, { timeout: 15_000 })
    await expect(page.getByRole('button', { name: 'Create', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Create', exact: true }).click()
    await expect(toast(page)).toContainText(/Content created successfully/i, { timeout: 8_000 })
    await expect(page).toHaveURL(/\/content$/)
    await expect(page.locator('tr', { hasText: `Copy of ${headline}` })).toBeVisible({ timeout: 10_000 })
  })

  test('cleanup', async ({ page, backendUrl }) => {
    await open(page, backendUrl, '/content')
    await expect(page.locator('.content-view')).toBeVisible({ timeout: 15_000 })
    await page.waitForTimeout(1000)
    const ids: number[] = await page.evaluate(
      () =>
        new Promise<number[]>((resolve) => {
          const socket = (window as any).__displayhive_socket__
          socket.once('displayhive:admin:stc:upd_all_content', (d: any) => resolve((d?.data || d?.content || []).map((c: any) => c.id)))
          socket.emit('displayhive:admin:cts:get_all_content_detailed')
          setTimeout(() => resolve([]), 4000)
        }),
    )
    for (const id of ids) await emitAck(page, 'displayhive:admin:cts:delete_content_element', { content_element_id: id })
    await emitAck(page, 'displayhive:admin:cts:delete_contenttype', { id: contenttypeId })
    await emitAck(page, 'displayhive:admin:cts:delete_layout', { id: layoutId })
    await emitAck(page, 'displayhive:admin:cts:delete_container', { id: containerId })
    await emitAck(page, 'displayhive:admin:cts:delete_screengroup', { screengroup_id: groupId })
  })
})
