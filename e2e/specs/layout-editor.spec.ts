/**
 * E2E tests for the Layout canvas editor (/layouts/:id/edit).
 *
 * Covered: the canvas and its rectangles, drag / resize / draw, staged settings that are only
 * saved with the Layout, default-content handlers, snaplines, aspect-ratio variations,
 * adding / removing / locking containers, and the preview toggles.
 *
 * Strategy: one Layout with two containers (and a Design offering 4:3) is seeded via socket;
 * tests run serially against it and the last one cleans up.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Page, Locator } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(60_000)

const suffix = Math.random().toString(36).slice(2, 7)
const layoutName = `e2e-le-${suffix}`
const nameA = `le-A-${suffix}`
const nameB = `le-B-${suffix}`
const designName = `e2e-le-design-${suffix}`

let layoutId = 0
let containerA = 0
let containerB = 0
let designId = 0
const extraContainers: number[] = []

/** Emit a socket event on the admin page and resolve with its ack. */
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

async function gotoEditor(page: Page, backendUrl: string) {
  // tall enough that the whole canvas is on screen: the pointer tests use real mouse coordinates
  await page.setViewportSize({ width: 1400, height: 1500 })
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, backendUrl)
  await page.goto(`${adminUrl}/layouts/${layoutId}/edit`)
  await expect(page.locator('.editor-canvas')).toBeVisible({ timeout: 15_000 })
  await expect(page.locator('.editor-rect', { hasText: nameA })).toBeVisible({ timeout: 10_000 })
}

const rect = (page: Page, name: string): Locator => page.locator('.editor-rect', { hasText: name })

/** The rect's position as numbers (percent of the canvas). */
async function rectBox(page: Page, name: string) {
  return rect(page, name).evaluate((el) => {
    const s = (el as HTMLElement).style
    return { top: parseFloat(s.top), left: parseFloat(s.left), width: parseFloat(s.width), height: parseFloat(s.height) }
  })
}

const settingsInput = (page: Page, label: string): Locator =>
  page.locator('.editor-settings-card .field', { has: page.locator('label', { hasText: label }) }).locator('input').first()

async function selectContainer(page: Page, name: string) {
  await page.locator('.sidebar-item', { hasText: name }).first().click()
  await expect(page.locator('.editor-settings-card input').first()).toHaveValue(name, { timeout: 5_000 })
}

async function saveLayout(page: Page) {
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.locator('.p-toast')).toContainText(/Layout updated/i, { timeout: 8_000 })
}

test.describe('Layout editor', () => {
  test('seed: design with a 4:3 ratio, two containers, a layout', async ({ page, backendUrl }) => {
    await page.addInitScript((url: string) => {
      ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
    }, backendUrl)
    await page.goto(`${adminUrl}/layouts`)
    await expect(page.locator('.layouts-view, .p-datatable').first()).toBeVisible({ timeout: 15_000 })
    await page.waitForTimeout(1000)

    const design = await emitAck(page, 'displayhive:admin:cts:create_design', { name: designName, aspect_ratios: JSON.stringify(['4:3']) })
    expect(design.success).toBe(true)
    designId = design.id
    expect((await emitAck(page, 'displayhive:admin:cts:set_default_design', { id: designId })).success).toBe(true)

    const a = await emitAck(page, 'displayhive:admin:cts:create_container', { name: nameA, order: 1, top: 10, left: 10, width: 30, height: 30 })
    const b = await emitAck(page, 'displayhive:admin:cts:create_container', { name: nameB, order: 2, top: 55, left: 55, width: 30, height: 30 })
    expect(a.success && b.success).toBe(true)
    containerA = a.id
    containerB = b.id
    const layout = await emitAck(page, 'displayhive:admin:cts:create_layout', { name: layoutName, description: '', container_ids: [containerA, containerB] })
    expect(layout.success).toBe(true)
    layoutId = layout.id
  })

  test('shows the canvas, both containers and the sidebar lists', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    await expect(rect(page, nameA)).toBeVisible()
    await expect(rect(page, nameB)).toBeVisible()
    await expect(page.locator('.editor-used-card .sidebar-item')).toHaveCount(2)
    await expect(page.locator('.editor-used-card')).toContainText(nameA)
    const box = await rectBox(page, nameA)
    expect(box.left).toBeCloseTo(10, 0)
    expect(box.width).toBeCloseTo(30, 0)
  })

  test('the sidebar filter narrows the lists', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    await page.getByPlaceholder('Search containers…').fill(nameB)
    await expect(page.locator('.editor-used-card .sidebar-item')).toHaveCount(1)
    await expect(page.locator('.editor-used-card')).toContainText(nameB)
    // the canvas is not filtered
    await expect(rect(page, nameA)).toBeVisible()
    await page.getByPlaceholder('Search containers…').fill('')
    await expect(page.locator('.editor-used-card .sidebar-item')).toHaveCount(2)
  })

  test('dragging moves a container, and the move is only saved with the Layout', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    const canvas = await page.locator('.editor-canvas').boundingBox()
    const before = await rectBox(page, nameA)
    const r = await rect(page, nameA).boundingBox()
    const startX = r!.x + r!.width / 2
    const startY = r!.y + r!.height / 2
    await page.mouse.move(startX, startY)
    await page.mouse.down()
    await page.mouse.move(startX + canvas!.width * 0.2, startY + canvas!.height * 0.1, { steps: 8 })
    await page.mouse.up()
    const after = await rectBox(page, nameA)
    expect(after.left).toBeGreaterThan(before.left + 10)
    expect(after.top).toBeGreaterThan(before.top + 5)
    // nothing is saved until Save: a reload shows the old position
    await saveLayout(page)
    await page.reload()
    await expect(rect(page, nameA)).toBeVisible({ timeout: 10_000 })
    const saved = await rectBox(page, nameA)
    expect(saved.left).toBeCloseTo(after.left, 0)
  })

  test('discarded drags are not saved', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    const before = await rectBox(page, nameB)
    const canvas = await page.locator('.editor-canvas').boundingBox()
    const r = await rect(page, nameB).boundingBox()
    await page.mouse.move(r!.x + r!.width / 2, r!.y + r!.height / 2)
    await page.mouse.down()
    await page.mouse.move(r!.x + r!.width / 2 - canvas!.width * 0.15, r!.y + r!.height / 2 - canvas!.height * 0.1, { steps: 5 })
    await page.mouse.up()
    expect((await rectBox(page, nameB)).left).toBeLessThan(before.left - 5)
    await page.reload()
    await expect(rect(page, nameB)).toBeVisible({ timeout: 10_000 })
    expect((await rectBox(page, nameB)).left).toBeCloseTo(before.left, 0)
  })

  test('the bottom-right handle resizes', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    const before = await rectBox(page, nameB)
    const handle = rect(page, nameB).locator('.resize-handle--br')
    const h = await handle.boundingBox()
    await page.mouse.move(h!.x + h!.width / 2, h!.y + h!.height / 2)
    await page.mouse.down()
    const canvasBox = await page.locator('.editor-canvas').boundingBox()
    await page.mouse.move(h!.x - canvasBox!.width * 0.1, h!.y - canvasBox!.height * 0.1, { steps: 6 })
    await page.mouse.up()
    const after = await rectBox(page, nameB)
    expect(after.width).toBeLessThan(before.width - 3)
    expect(after.left).toBeCloseTo(before.left, 0)
  })

  test('the settings card follows a drag and a resize, and typing keeps the dragged size', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    const canvasBox = await page.locator('.editor-canvas').boundingBox()
    const start = await rectBox(page, nameB)
    // resize it first (this also selects it), then move it
    const h = await rect(page, nameB).locator('.resize-handle--br').boundingBox()
    await page.mouse.move(h!.x + h!.width / 2, h!.y + h!.height / 2)
    await page.mouse.down()
    await page.mouse.move(h!.x - canvasBox!.width * 0.1, h!.y - canvasBox!.height * 0.1, { steps: 6 })
    await page.mouse.up()
    const r = await rect(page, nameB).boundingBox()
    await page.mouse.move(r!.x + r!.width / 2, r!.y + r!.height / 2)
    await page.mouse.down()
    await page.mouse.move(r!.x + r!.width / 2 - canvasBox!.width * 0.1, r!.y + r!.height / 2, { steps: 6 })
    await page.mouse.up()
    const moved = await rectBox(page, nameB)
    expect(moved.width).toBeLessThan(start.width - 3)

    // The card shows what is on the canvas now
    const value = async (label: string) => Number(await settingsInput(page, label).inputValue())
    await expect.poll(() => value('Left (vw)')).toBeCloseTo(moved.left, 0)
    await expect.poll(() => value('Width (vw)')).toBeCloseTo(moved.width, 0)

    // Typing one number does not put the old size back
    const left = settingsInput(page, 'Left (vw)')
    await left.fill('30')
    await left.blur()
    await expect.poll(async () => (await rectBox(page, nameB)).left, { timeout: 5_000 }).toBeCloseTo(30, 0)
    expect((await rectBox(page, nameB)).width).toBeCloseTo(moved.width, 0)

    // "Reset to Default Position" shows the saved numbers again
    await page.getByRole('button', { name: 'Reset to Default Position' }).click()
    await expect.poll(() => value('Width (vw)')).toBeCloseTo(start.width, 0)
    await expect.poll(() => value('Left (vw)')).toBeCloseTo(start.left, 0)
  })

  test('typing a position in the settings card moves the rectangle live', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    await selectContainer(page, nameB)
    const input = settingsInput(page, 'Left (vw)')
    await input.fill('20')
    await input.blur()
    await expect.poll(async () => (await rectBox(page, nameB)).left, { timeout: 5_000 }).toBeCloseTo(20, 0)
  })

  test('settings edits (name, show when empty) are staged live and saved with the Layout', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    await selectContainer(page, nameB)
    const nameInput = page.locator('.editor-settings-card input').first()
    await nameInput.fill(`${nameB}-x`)
    await expect(rect(page, `${nameB}-x`)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Revert' })).toBeVisible()
    await saveLayout(page)
    await page.reload()
    await expect(rect(page, `${nameB}-x`)).toBeVisible({ timeout: 10_000 })
    // rename back so later tests keep their names
    await selectContainer(page, `${nameB}-x`)
    await page.locator('.editor-settings-card input').first().fill(nameB)
    await saveLayout(page)
  })

  test('Revert drops unsaved settings edits', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    await selectContainer(page, nameA)
    await page.locator('.editor-settings-card input').first().fill('temporary name')
    await expect(rect(page, 'temporary name')).toBeVisible()
    await page.getByRole('button', { name: 'Revert' }).click()
    await expect(rect(page, nameA)).toBeVisible()
    await expect(page.locator('.editor-settings-card input').first()).toHaveValue(nameA)
  })

  test('a default handler shows its editor and its content is saved', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    await selectContainer(page, nameA)
    await page.locator('.editor-settings-card .p-select, .editor-settings-card .p-dropdown').first().click()
    await page.getByRole('option', { name: 'Short Text' }).click()
    const content = page.locator('.editor-settings-card .field', { has: page.locator('label', { hasText: 'Default Content' }) }).locator('input')
    await expect(content).toBeVisible()
    await content.fill('hello default')
    await saveLayout(page)
    await page.reload()
    await expect(rect(page, nameA)).toBeVisible({ timeout: 10_000 })
    await selectContainer(page, nameA)
    await expect(page.locator('.editor-settings-card .field', { has: page.locator('label', { hasText: 'Default Content' }) }).locator('input')).toHaveValue('hello default')
  })

  test('each handler offers its own editor', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    await selectContainer(page, nameA)
    const dropdown = page.locator('.editor-settings-card .p-select, .editor-settings-card .p-dropdown').first()
    const pick = async (label: string) => {
      await dropdown.click()
      await page.getByRole('option', { name: label, exact: true }).click()
    }
    await pick('Long Text')
    await expect(page.locator('.editor-settings-card textarea')).toBeVisible()
    await pick('Arrow')
    await expect(page.locator('.editor-settings-card .arrow-btn').first()).toBeVisible()
    await pick('Table')
    await expect(page.locator('.editor-settings-card .default-table-editor')).toBeVisible()
    await pick('Countdown')
    await expect(page.getByText('Target Date & Time')).toBeVisible()
    await pick('Lauftext (Marquee)')
    await expect(page.getByPlaceholder('Dein Lauftext…')).toBeVisible()
    await pick('Image')
    await expect(page.getByText('Click to select an image')).toBeVisible()
    await pick('iFrame')
    await expect(page.getByPlaceholder('https://example.com')).toBeVisible()
    await pick('None')
    await expect(page.locator('.editor-settings-card .field', { has: page.locator('label', { hasText: 'Default Content' }) })).toHaveCount(0)
    await page.getByRole('button', { name: 'Revert' }).click()
  })

  test('snaplines can be added and removed', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    const chips = page.locator('.snapline-chip')
    const before = await chips.count()
    await page.locator('.snapline-position-input input').fill('25')
    await page.getByRole('button', { name: 'Add Snapline' }).click()
    await expect(chips).toHaveCount(before + 1, { timeout: 8_000 })
    await expect(page.locator('.canvas-snapline')).toHaveCount(before + 1)
    await chips.last().locator('.snapline-chip-remove').click()
    await expect(chips).toHaveCount(before, { timeout: 8_000 })
  })

  test('the preview toggles hide the handler elements', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    await page.locator('#hide-handler-elements').click()
    await expect(page.locator('.editor-canvas')).toHaveClass(/handles-hidden/)
    await page.locator('#hide-handler-elements').click()
    await expect(page.locator('.editor-canvas')).not.toHaveClass(/handles-hidden/)
  })

  test('a container can be removed from the layout and added back', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    await page.locator('.editor-used-card .sidebar-item', { hasText: nameB }).locator('.sidebar-icon-btn').click()
    await expect(rect(page, nameB)).toHaveCount(0, { timeout: 8_000 })
    await expect(page.locator('.editor-containers-card')).toContainText(nameB)
    await selectContainer(page, nameB)
    await page.getByRole('button', { name: 'Add to Layout' }).click()
    await expect(rect(page, nameB)).toBeVisible({ timeout: 8_000 })
  })

  test('a container can be locked, and a locked one has no resize handles', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    await rect(page, nameA).locator('.lock-handle').click()
    await expect(rect(page, nameA)).toHaveClass(/locked/, { timeout: 8_000 })
    await expect(rect(page, nameA).locator('.resize-handle')).toHaveCount(0)
    await rect(page, nameA).locator('.lock-handle').click()
    await expect(rect(page, nameA)).not.toHaveClass(/locked/, { timeout: 8_000 })
  })

  test('New Container adds a box to the layout', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    const before = await page.locator('.editor-rect').count()
    await page.getByRole('button', { name: 'New Container' }).click()
    await expect(page.locator('.editor-rect')).toHaveCount(before + 1, { timeout: 8_000 })
  })

  test('drawing on empty canvas space creates a container', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    const before = await page.locator('.editor-rect').count()
    const canvas = await page.locator('.editor-canvas').boundingBox()
    // the bottom-left corner is empty
    const x = canvas!.x + canvas!.width * 0.02
    const y = canvas!.y + canvas!.height * 0.62
    await page.mouse.move(x, y)
    await page.mouse.down()
    await page.mouse.move(x + canvas!.width * 0.15, y + canvas!.height * 0.25, { steps: 6 })
    await page.mouse.up()
    await expect(page.locator('.editor-rect:not(.drawing-rect)')).toHaveCount(before + 1, { timeout: 8_000 })
  })

  test('an aspect-ratio variation can be added, selected and removed', async ({ page, backendUrl }) => {
    await gotoEditor(page, backendUrl)
    const card = page.locator('.editor-ratio-card')
    await expect(card.locator('.ratio-row')).toHaveCount(1)
    await card.locator('.ratio-add-select').click()
    await page.getByRole('option', { name: '4:3' }).click()
    await card.getByRole('button', { name: 'Add' }).click()
    await expect(card.locator('.ratio-row')).toHaveCount(2, { timeout: 8_000 })
    // the new variation is shown right away and starts as a copy of the base
    await expect(card.locator('.ratio-row.active')).toContainText('4:3')
    await expect(rect(page, nameA)).toBeVisible()
    // back to the base, then remove the variation
    await card.locator('.ratio-row', { hasText: '16:9' }).click()
    await expect(card.locator('.ratio-row.active')).toContainText('16:9')
    await card.locator('.ratio-row', { hasText: '4:3' }).getByRole('button').click()
    await page.locator('.p-confirmdialog').getByRole('button', { name: 'Yes' }).click()
    await expect(card.locator('.ratio-row')).toHaveCount(1, { timeout: 8_000 })
  })

  test('cleanup', async ({ page, backendUrl }) => {
    await page.addInitScript((url: string) => {
      ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
    }, backendUrl)
    await page.goto(`${adminUrl}/layouts`)
    await page.waitForTimeout(1500)
    expect((await emitAck(page, 'displayhive:admin:cts:delete_layout', { id: layoutId })).success).toBe(true)
    const all = await page.evaluate(
      () =>
        new Promise<number[]>((resolve) => {
          const socket = (window as any).__displayhive_socket__
          socket.once('displayhive:admin:stc:upd_containers', (d: any) => resolve((d?.data || []).map((c: any) => c.id)))
          socket.emit('displayhive:admin:cts:get_containers')
        }),
    )
    for (const id of all) await emitAck(page, 'displayhive:admin:cts:delete_container', { id })
    void extraContainers
  })
})
