/**
 * E2E tests for the field editors of the content edit page (one per field handler) and for
 * their preset mode in the Content Types dialog.
 *
 * Covered: every handler renders its editor; values typed into the text-like, number, checkbox,
 * date/time format, marquee, countdown, arrows, table, link, iframe and raw HTML fields survive a
 * save and a reload; the image picker opens; "hide" in a preset hides the field from the content
 * editor; "lock" disables it.
 *
 * Strategy: one content type with a field per handler is seeded via socket; tests run serially.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Locator, Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(90_000)

const suffix = Math.random().toString(36).slice(2, 7)
const ctName = `e2e-fe-ct-${suffix}`

const HANDLERS: Array<[name: string, handler: string, title: string]> = [
  ['f_text', 'textklein', 'Short text'],
  ['f_big', 'textbig', 'Long text'],
  ['f_link', 'link', 'Link'],
  ['f_iframe', 'iframe', 'Frame'],
  ['f_raw', 'rawhtml', 'Raw html'],
  ['f_num', 'numbers', 'Number'],
  ['f_check', 'checkbox', 'Check'],
  ['f_date', 'datetime_format', 'Date format'],
  ['f_marq', 'marquee', 'Marquee'],
  ['f_count', 'countdown', 'Countdown'],
  ['f_arrow', 'arrows', 'Arrow'],
  ['f_table', 'table', 'Table'],
  ['f_image', 'image', 'Image'],
  ['f_wys', 'wysiwyg', 'Rich text'],
  ['f_icon', 'icon', 'Icon'],
  ['f_pretalx', 'pretalx_table', 'Pretalx'],
]

let containerId = 0
let layoutId = 0
let contenttypeId = 0
let contentId = 0
const presetName = `e2e-fe-preset-${suffix}`
// A content type's field is named after its container (the Content Types dialog derives it).
const p1Name = `fe_p1_${suffix}`
const p2Name = `fe_p2_${suffix}`
const presetContainers: number[] = []
let presetLayoutId = 0
let presetTypeId = 0

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
  await page.setViewportSize({ width: 1500, height: 2600 })
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, backendUrl)
  await page.goto(`${adminUrl}${path}`)
}

const block = (page: Page, title: string): Locator =>
  page.locator('.tag-fields-section > .field', { has: page.locator('label', { hasText: new RegExp(`^${title}$`) }) })

async function openNew(page: Page, backendUrl: string) {
  await open(page, backendUrl, `/content/new?contenttype_id=${contenttypeId}`)
  await expect(page.locator('.content-type-banner')).toContainText(ctName, { timeout: 15_000 })
  await expect(block(page, 'Short text')).toBeVisible({ timeout: 10_000 })
}

test.describe('Field editors', () => {
  test('seed: a content type with a field per handler', async ({ page, backendUrl }) => {
    await open(page, backendUrl, '/content')
    await expect(page.locator('.content-view')).toBeVisible({ timeout: 15_000 })
    await page.waitForTimeout(1000)
    containerId = (await emitAck(page, 'displayhive:admin:cts:create_container', { name: `fe-c-${suffix}`, order: 1, top: 5, left: 5, width: 90, height: 90 })).id
    layoutId = (await emitAck(page, 'displayhive:admin:cts:create_layout', { name: `e2e-fe-layout-${suffix}`, description: '', container_ids: [containerId] })).id
    const ct = await emitAck(page, 'displayhive:admin:cts:create_contenttype', {
      name: ctName, layout_id: layoutId,
      tagconfigs: HANDLERS.map(([name, handler, title], i) => ({ name, title, field_handler: handler, order: i })),
    })
    expect(ct.success).toBe(true)
    contenttypeId = ct.id
  })

  test('every handler renders its editor', async ({ page, backendUrl }) => {
    await openNew(page, backendUrl)
    await expect(block(page, 'Short text').locator('input[type="text"]')).toBeVisible()
    await expect(block(page, 'Long text').locator('textarea')).toBeVisible()
    await expect(block(page, 'Link').locator('input[type="url"]')).toBeVisible()
    await expect(block(page, 'Frame').locator('input[type="url"]')).toBeVisible()
    await expect(block(page, 'Raw html').locator('textarea')).toBeVisible()
    await expect(block(page, 'Number').locator('.p-inputnumber input')).toBeVisible()
    await expect(block(page, 'Check').locator('.p-checkbox')).toBeVisible()
    await expect(block(page, 'Date format').locator('.datetime-preview-value')).toBeVisible()
    await expect(block(page, 'Date format').locator('.token-table')).toBeVisible()
    await expect(block(page, 'Marquee').getByPlaceholder('Dein Lauftext…')).toBeVisible()
    await expect(block(page, 'Countdown').locator('.datetime-preview-value')).toBeVisible()
    await expect(block(page, 'Arrow').locator('.arrow-btn').first()).toBeVisible()
    await expect(block(page, 'Table').locator('.table-editor-tbl')).toBeVisible()
    await expect(block(page, 'Image').getByText('Click to select an image')).toBeVisible()
    await expect(block(page, 'Rich text').locator('.ql-editor')).toBeVisible({ timeout: 10_000 })
    await expect(block(page, 'Icon').locator('.icon-picker')).toBeVisible()
    await expect(block(page, 'Pretalx').locator('.pretalx-table-editor')).toBeVisible()
  })

  test('the date format and countdown previews update as you type', async ({ page, backendUrl }) => {
    await openNew(page, backendUrl)
    const date = block(page, 'Date format')
    await date.locator('input[type="text"]').first().fill('YYYY')
    await expect(date.locator('.datetime-preview-value')).toHaveText(/^\d{4}$/)
    const count = block(page, 'Countdown')
    await expect(count.locator('.datetime-preview-value')).toHaveText('—')
  })

  test('the image field opens the picker, and random mode shows the tag chooser', async ({ page, backendUrl }) => {
    await openNew(page, backendUrl)
    const image = block(page, 'Image')
    await image.getByText('Click to select an image').click()
    const dialog = page.locator('.p-dialog', { hasText: 'Select Image' })
    await expect(dialog).toBeVisible({ timeout: 5_000 })
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toBeHidden()
    await image.locator('.image-mode-select .p-select').click()
    await page.getByRole('option', { name: 'Random Image from Tags' }).click()
    await expect(image.locator('.image-tags-cloud')).toBeVisible()
  })

  test('typed values are saved and come back when the content is edited', async ({ page, backendUrl }) => {
    await openNew(page, backendUrl)
    await block(page, 'Short text').locator('input[type="text"]').fill('Hello')
    await block(page, 'Long text').locator('textarea').fill('Line one\nLine two')
    await block(page, 'Link').locator('input[type="url"]').fill('https://example.org/a')
    await block(page, 'Frame').locator('input[type="url"]').fill('https://example.org/frame')
    await block(page, 'Raw html').locator('textarea').fill('<b>raw</b>')
    const num = block(page, 'Number').locator('.p-inputnumber input')
    await num.fill('7')
    await num.blur()
    await block(page, 'Check').locator('.p-checkbox').click()
    await block(page, 'Date format').locator('input[type="text"]').first().fill('DD.MM.YYYY')
    await block(page, 'Marquee').getByPlaceholder('Dein Lauftext…').fill('Scrolling news')
    const speed = block(page, 'Marquee').locator('.marquee-speed-row input')
    await speed.fill('33')
    await speed.blur()
    await block(page, 'Countdown').locator('input[placeholder="DD:HH:mm:ss"]').fill('DD:HH')
    await block(page, 'Arrow').locator('.arrow-btn[title="Right"]').click()
    await expect(block(page, 'Arrow').locator('.arrow-selected-preview')).toContainText('→')
    await block(page, 'Table').getByRole('button', { name: 'Add Row' }).click()
    await block(page, 'Table').locator('.table-editor-cell input').first().fill('cell A')
    await page.locator('#create-title').fill(`FE content ${suffix}`)
    await page.getByRole('button', { name: 'Create', exact: true }).click()
    await expect(page.locator('.p-toast')).toContainText(/Content created successfully/i, { timeout: 8_000 })
    await expect(page).toHaveURL(/\/content$/)
    const row = page.locator('tr', { hasText: `FE content ${suffix}` })
    await expect(row).toBeVisible({ timeout: 10_000 })
    await row.locator('button:has(.pi-pencil)').click()
    await expect(page).toHaveURL(/\/content\/\d+\/edit/, { timeout: 8_000 })
    contentId = Number(page.url().match(/\/content\/(\d+)\/edit/)![1])
  })

  test('the saved values are shown again', async ({ page, backendUrl }) => {
    await open(page, backendUrl, `/content/${contentId}/edit`)
    await expect(page.locator('#create-title')).toHaveValue(`FE content ${suffix}`, { timeout: 15_000 })
    await expect(block(page, 'Short text').locator('input[type="text"]')).toHaveValue('Hello')
    await expect(block(page, 'Long text').locator('textarea')).toHaveValue('Line one\nLine two')
    await expect(block(page, 'Link').locator('input[type="url"]')).toHaveValue('https://example.org/a')
    await expect(block(page, 'Frame').locator('input[type="url"]')).toHaveValue('https://example.org/frame')
    await expect(block(page, 'Raw html').locator('textarea')).toHaveValue('<b>raw</b>')
    await expect(block(page, 'Number').locator('.p-inputnumber input')).toHaveValue('7')
    await expect(block(page, 'Check').locator('.p-checkbox-checked')).toHaveCount(1)
    await expect(block(page, 'Date format').locator('input[type="text"]').first()).toHaveValue('DD.MM.YYYY')
    await expect(block(page, 'Marquee').getByPlaceholder('Dein Lauftext…')).toHaveValue('Scrolling news')
    await expect(block(page, 'Marquee').locator('.marquee-speed-row input')).toHaveValue('33 s')
    await expect(block(page, 'Countdown').locator('input[placeholder="DD:HH:mm:ss"]')).toHaveValue('DD:HH')
    await expect(block(page, 'Arrow').locator('.arrow-selected-preview')).toContainText('→')
    await expect(block(page, 'Table').locator('.table-editor-cell input').first()).toHaveValue('cell A')
  })

  test('a preset can lock a field and hide a field from the content editor', async ({ page, backendUrl }) => {
    // The Content Types dialog lists one field per container of the layout, so this uses a second
    // content type whose two fields sit on two containers.
    await open(page, backendUrl, '/contenttypes')
    await expect(page.locator('tr', { hasText: ctName })).toBeVisible({ timeout: 15_000 })
    await page.waitForTimeout(500)
    const c1 = (await emitAck(page, 'displayhive:admin:cts:create_container', { name: p1Name, order: 1, top: 5, left: 5, width: 40, height: 40 })).id
    const c2 = (await emitAck(page, 'displayhive:admin:cts:create_container', { name: p2Name, order: 2, top: 50, left: 50, width: 40, height: 40 })).id
    presetContainers.push(c1, c2)
    presetLayoutId = (await emitAck(page, 'displayhive:admin:cts:create_layout', { name: `e2e-fe-preset-layout-${suffix}`, description: '', container_ids: [c1, c2] })).id
    const presetCt = await emitAck(page, 'displayhive:admin:cts:create_contenttype', {
      name: presetName, layout_id: presetLayoutId,
      tagconfigs: [
        { name: p1Name, title: p1Name, field_handler: 'textklein', contentcontainer_id: c1, order: 0 },
        { name: p2Name, title: p2Name, field_handler: 'textbig', contentcontainer_id: c2, order: 1 },
      ],
    })
    expect(presetCt.success).toBe(true)
    presetTypeId = presetCt.id

    const row = page.locator('tr', { hasText: presetName })
    await expect(row).toBeVisible({ timeout: 15_000 })
    await row.locator('button[title="Edit"]').click()
    const dialog = page.locator('.p-dialog', { hasText: 'Edit Content Type' })
    await expect(dialog).toBeVisible({ timeout: 10_000 })
    await expect(dialog.locator('.tagconfig-row')).toHaveCount(2)
    // first field: lock it
    await dialog.locator('.tagconfig-row').nth(0).locator('button[title="Preset value"]').click()
    const firstPanel = dialog.locator('.tagconfig-preset-panel').first()
    await expect(firstPanel.locator('.option-flag-btn')).toHaveCount(2)
    await firstPanel.locator('.option-flag-btn').nth(0).click()
    await expect(firstPanel.locator('.option-flag-btn--active')).toHaveCount(1)
    // second field: hide it
    await dialog.locator('.tagconfig-row').nth(1).locator('button[title="Preset value"]').click()
    const secondPanel = dialog.locator('.tagconfig-preset-panel').nth(1)
    await expect(secondPanel.locator('.option-flag-btn')).toHaveCount(2)
    await secondPanel.locator('.option-flag-btn').nth(1).click()
    await expect(secondPanel.locator('.option-flag-btn--active')).toHaveCount(1)
    await dialog.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(page.locator('.p-toast')).toContainText(/Content type updated/i, { timeout: 8_000 })

    await open(page, backendUrl, `/content/new?contenttype_id=${presetTypeId}`)
    await expect(page.locator('.content-type-banner')).toContainText(presetName, { timeout: 15_000 })
    await expect(block(page, p1Name).locator('input[type="text"]')).toBeDisabled()
    await expect(block(page, p2Name)).toBeHidden()
  })

  test('cleanup', async ({ page, backendUrl }) => {
    await open(page, backendUrl, '/content')
    await expect(page.locator('.content-view')).toBeVisible({ timeout: 15_000 })
    await page.waitForTimeout(1000)
    if (contentId) await emitAck(page, 'displayhive:admin:cts:delete_content_element', { content_element_id: contentId })
    await emitAck(page, 'displayhive:admin:cts:delete_contenttype', { id: contenttypeId })
    await emitAck(page, 'displayhive:admin:cts:delete_layout', { id: layoutId })
    await emitAck(page, 'displayhive:admin:cts:delete_container', { id: containerId })
    if (presetTypeId) await emitAck(page, 'displayhive:admin:cts:delete_contenttype', { id: presetTypeId })
    if (presetLayoutId) await emitAck(page, 'displayhive:admin:cts:delete_layout', { id: presetLayoutId })
    for (const id of presetContainers) await emitAck(page, 'displayhive:admin:cts:delete_container', { id })
  })
})
