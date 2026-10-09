/**
 * E2E tests for the Screen Groups admin page.
 *
 * Covered:
 *  Main table
 *  1.  Create screengroup — dialog creates row with 0 screens / 0 content badges
 *  2.  Delete button only visible when group is empty (0/0), absent otherwise
 *  3.  Text filter narrows the table
 *  4.  Rename screengroup — edit dialog updates the row name
 *  5.  Delete screengroup — confirm dialog removes the row
 *
 *  Screens management dialog (Screens badge)
 *  6.  Badge opens the Screens dialog
 *  7.  Add screen to group — screen moves from "Not Assigned" to "Assigned", badge increments
 *  8.  Filter inside dialog narrows assigned list
 *  9.  Remove screen from group — screen moves back, badge decrements
 *  10. "Remove All" clears all assigned screens after confirm
 *
 *  Content management dialog (Content badge)
 *  11. Badge opens the Content dialog
 *  12. Add content to group — content moves from "Not Assigned" to "Assigned", badge increments
 *  13. Remove content from group — content moves back, badge decrements
 *  14. "Remove All" clears all assigned content after confirm
 *
 * Strategy:
 *  - One screengroup is seeded for tests 1-10; a second empty group is used
 *    for the delete test (5) so deletion never blocks the main suite group.
 *  - A dedicated screen and a dedicated content_element item are seeded via socket
 *    and torn down in cleanup so the tests are fully self-contained.
 *  - All tests run serially on the same worker / isolated DB.
 */

import test, { expect } from './fixtures.js'
import { adminUrl } from './urls.js'
import type { Page } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
test.setTimeout(60_000)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function gotoScreenGroups(page: Page, workerBackendUrl: string) {
  console.log('[screengroups.spec] gotoScreenGroups')
  await page.addInitScript((url: string) => {
    ;(window as any).__DISPLAYHIVE_TEST_BACKEND_URL__ = url
  }, workerBackendUrl)
  await page.goto(`${adminUrl}/screengroups`)
  await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })
}

/** Wait for and return a socket from window.__displayhive_socket__. */
function getSocket(page: Page) {
  return page.evaluate(() => (window as any).__displayhive_socket__)
}

/**
 * Create a screengroup via socket and return its id.
 * Waits for `displayhive:admin:stc:screengroup_created`.
 */
async function seedScreenGroup(page: Page, name: string): Promise<number> {
  return page.evaluate(
    ({ name }: { name: string }) =>
      new Promise<number>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) {
          reject(new Error('Socket not available'))
          return
        }
        const t = setTimeout(
          () => reject(new Error('Timed out waiting for screengroup_created')),
          10_000,
        )
        socket.once('displayhive:admin:stc:screengroup_created', (data: any) => {
          clearTimeout(t)
          if (data?.success) resolve(data.screengroup_id)
          else reject(new Error(`screengroup_created failed: ${JSON.stringify(data)}`))
        })
        socket.emit('displayhive:admin:cts:create_screengroup', { name })
      }),
    { name },
  )
}

/**
 * Delete a screengroup by id via socket.
 * Waits for `displayhive:admin:stc:screengroup_deleted`.
 */
async function deleteScreenGroupById(page: Page, id: number): Promise<void> {
  await page.evaluate(
    ({ id }: { id: number }) =>
      new Promise<void>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) {
          reject(new Error('Socket not available'))
          return
        }
        const t = setTimeout(
          () => reject(new Error('Timed out waiting for screengroup_deleted')),
          10_000,
        )
        socket.once('displayhive:admin:stc:screengroup_deleted', (data: any) => {
          clearTimeout(t)
          if (data?.success) resolve()
          else reject(new Error(`screengroup_deleted failed: ${JSON.stringify(data)}`))
        })
        socket.emit('displayhive:admin:cts:delete_screengroup', { screengroup_id: id })
      }),
    { id },
  )
}

/** Create a screen via socket and return its id. */
async function seedScreen(page: Page, name: string): Promise<number> {
  return page.evaluate(
    ({ name }: { name: string }) =>
      new Promise<number>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) {
          reject(new Error('Socket not available'))
          return
        }
        const t = setTimeout(
          () => reject(new Error('Timed out waiting for screen creation')),
          10_000,
        )
        socket.emit('displayhive:screens:cts:create_screen', { name }, (ack: any) => {
          clearTimeout(t)
          if (ack?.success && ack?.screen_id) resolve(Number(ack.screen_id))
          else reject(new Error(`create_screen ack failed: ${JSON.stringify(ack)}`))
        })
      }),
    { name },
  )
}

/** Delete a screen by id via socket. */
async function deleteScreen(page: Page, screenId: number): Promise<void> {
  await page.evaluate(
    ({ screenId }: { screenId: number }) =>
      new Promise<void>((resolve) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) {
          resolve()
          return
        }
        socket.emit('displayhive:screens:cts:delete_screen', { screen_id: screenId })
        // delete_screen has no ack — wait briefly for the push
        setTimeout(resolve, 500)
      }),
    { screenId },
  )
}

/**
 * Create a content_element item via socket and return its id.
 * Uses `displayhive:admin:cts:create_content_element` — no contenttype needed for
 * a minimal item (container defaults to 'maincontent').
 */
async function seedContent(page: Page, title: string): Promise<number> {
  return page.evaluate(
    ({ title }: { title: string }) =>
      new Promise<number>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) {
          reject(new Error('Socket not available'))
          return
        }
        const t = setTimeout(
          () => reject(new Error('Timed out waiting for create_content_element_result')),
          10_000,
        )
        socket.once('displayhive:admin:stc:create_content_element_result', (data: any) => {
          clearTimeout(t)
          if (data?.success) resolve(data.content_element_id)
          else reject(new Error(`create_content_element failed: ${JSON.stringify(data)}`))
        })
        socket.emit('displayhive:admin:cts:create_content_element', { title, duration: 10 })
      }),
    { title },
  )
}

/** Delete a content_element item by id via socket. */
async function deleteContent(page: Page, contentId: number): Promise<void> {
  await page.evaluate(
    ({ contentId }: { contentId: number }) => {
      const socket = (window as any).__displayhive_socket__
      if (socket) socket.emit('displayhive:admin:cts:delete_content_element', { content_element_id: contentId })
    },
    { contentId },
  )
  // small settle time — no ack on delete
  await page.waitForTimeout(400)
}

// ---------------------------------------------------------------------------
// Suite state
// ---------------------------------------------------------------------------

test.describe('Screen Groups page', () => {
  const sgName = `e2e-sg-${Math.random().toString(36).slice(2, 8)}`
  const sgNameHolder = { current: sgName }
  let sgId = 0

  // Dedicated screen / content items seeded in their respective tests
  let screenId = 0
  let contentId = 0

  // ---------------------------------------------------------------------------
  // 1. Create screengroup
  // ---------------------------------------------------------------------------

  test('create screengroup dialog adds a row with 0 screens and 0 content', async ({
    page,
    backendUrl,
  }) => {
    console.log('[screengroups.spec] init socket handlers')
    await gotoScreenGroups(page, backendUrl)

    await page.getByRole('button', { name: 'New Screen Group' }).click()

    const dialog = page.locator('.p-dialog', { hasText: 'New Screen Group' })
    await expect(dialog).toBeVisible({ timeout: 5_000 })

    await dialog.locator('#sg-name').fill(sgName)
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden({ timeout: 5_000 })
    await expect(page.locator('.p-toast')).toContainText(/created/i, { timeout: 8_000 })

    // Row appears in the table
    const row = page.locator('tr', { hasText: sgName })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // Both badges show 0
    const badges = row.locator('.p-badge')
    await expect(badges.nth(0)).toHaveText('0') // screens
    await expect(badges.nth(1)).toHaveText('0') // content

    // Capture the id by fetching the fresh list
    sgId = await page.evaluate(
      ({ name }: { name: string }) => {
        const socket = (window as any).__displayhive_socket__
        return new Promise<number>((resolve) => {
          if (!socket) {
            resolve(0)
            return
          }
          const t = setTimeout(() => resolve(0), 8_000)
          socket.once('displayhive:admin:stc:upd_screengroups', (data: any) => {
            clearTimeout(t)
            const list: any[] = data?.data || []
            const sg = list.find((g: any) => (g.attributes?.name ?? g.name) === name)
            resolve(sg ? Number(sg.id) : 0)
          })
          socket.emit('displayhive:admin:cts:get_screengroups')
        })
      },
      { name: sgName },
    )
  })

  // ---------------------------------------------------------------------------
  // 2. Delete button only visible when group is empty
  // ---------------------------------------------------------------------------

  test('delete button is visible on empty group and absent after a screen is assigned', async ({
    page,
    backendUrl,
  }) => {
    console.log('[screengroups.spec] init socket handlers')
    await gotoScreenGroups(page, backendUrl)

    const row = page.locator('tr', { hasText: sgNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // Empty group → Delete button present
    await expect(row.locator('button[title="Delete"]')).toBeVisible()

    // Seed a screen and assign it so the group is no longer empty
    const tmpScreenName = `e2e-sgchk-${Math.random().toString(36).slice(2, 8)}`
    screenId = await seedScreen(page, tmpScreenName)

    if (sgId > 0) {
      await page.evaluate(
        ({ sgId, screenId }: { sgId: number; screenId: number }) =>
          new Promise<void>((resolve) => {
            const socket = (window as any).__displayhive_socket__
            if (!socket) {
              resolve()
              return
            }
            socket.emit('displayhive:admin:cts:add_screen_to_screengroup', {
              screengroup_id: sgId,
              screen_id: screenId,
            })
            setTimeout(resolve, 600)
          }),
        { sgId, screenId },
      )
      await page.reload()
      await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })
      const freshRow = page.locator('tr', { hasText: sgNameHolder.current })
      await expect(freshRow).toBeVisible({ timeout: 10_000 })
      // Group now has 1 screen → Delete button must be absent
      await expect(freshRow.locator('button[title="Delete"]')).toHaveCount(0)
    }
  })

  // ---------------------------------------------------------------------------
  // 3. Text filter
  // ---------------------------------------------------------------------------

  test('text filter hides non-matching rows and reveals matching ones', async ({
    page,
    backendUrl,
  }) => {
    console.log('[screengroups.spec] init socket handlers')
    await gotoScreenGroups(page, backendUrl)

    const row = page.locator('tr', { hasText: sgNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    const filterInput = page.locator('.filter-input input, .filter-input')
    await filterInput.fill('__no_match_xyz__')
    await expect(row).toBeHidden({ timeout: 3_000 })

    await filterInput.fill(sgNameHolder.current.slice(0, 8))
    await expect(row).toBeVisible({ timeout: 3_000 })

    await filterInput.fill('')
  })

  // ---------------------------------------------------------------------------
  // 4. Rename screengroup
  // ---------------------------------------------------------------------------

  test('edit dialog renames the group and updates the row', async ({ page, backendUrl }) => {
    console.log('[screengroups.spec] init socket handlers')
    await gotoScreenGroups(page, backendUrl)

    const row = page.locator('tr', { hasText: sgNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    await row.locator('button[title="Edit"]').click()

    const dialog = page.locator('.p-dialog', { hasText: 'Edit Screen Group' })
    await expect(dialog).toBeVisible({ timeout: 5_000 })

    const newName = `${sgNameHolder.current}-ren`
    await dialog.locator('#sg-name').clear()
    await dialog.locator('#sg-name').fill(newName)
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden({ timeout: 5_000 })
    await expect(page.locator('.p-toast')).toContainText(/updated/i, { timeout: 5_000 })

    await expect(page.locator('tr', { hasText: newName })).toBeVisible({ timeout: 10_000 })
    sgNameHolder.current = newName
  })

  // ---------------------------------------------------------------------------
  // 5. Delete an empty screengroup
  // ---------------------------------------------------------------------------

  test('delete dialog removes an empty screengroup', async ({ page, backendUrl }) => {
    console.log('[screengroups.spec] init socket handlers')
    await gotoScreenGroups(page, backendUrl)

    // Create a fresh empty group solely for deletion
    const delName = `e2e-sgdel-${Math.random().toString(36).slice(2, 8)}`
    await seedScreenGroup(page, delName)
    await page.reload()
    await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })

    const row = page.locator('tr', { hasText: delName })
    await expect(row).toBeVisible({ timeout: 10_000 })
    await expect(row.locator('button[title="Delete"]')).toBeVisible()

    await row.locator('button[title="Delete"]').click()

    await expect(page.getByText(/Are you sure you want to delete/)).toBeVisible({ timeout: 5_000 })
    await page.getByRole('button', { name: 'Yes' }).click()

    await expect(page.locator('tr', { hasText: delName })).toHaveCount(0, { timeout: 10_000 })
  })

  // ---------------------------------------------------------------------------
  // 6. Screens badge opens the Screens dialog
  // ---------------------------------------------------------------------------

  test('screens badge opens the screens management dialog', async ({ page, backendUrl }) => {
    console.log('[screengroups.spec] init socket handlers')
    await gotoScreenGroups(page, backendUrl)

    const row = page.locator('tr', { hasText: sgNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // Click the first (screens) badge
    await row.locator('.p-badge').nth(0).click()

    const dialog = page.locator('.p-dialog', { hasText: `Screens in ${sgNameHolder.current}` })
    await expect(dialog).toBeVisible({ timeout: 5_000 })
    await expect(dialog.getByText('Assigned Screens', { exact: true })).toBeVisible()
    await expect(dialog.getByText('Not Assigned Screens', { exact: true })).toBeVisible()

    await dialog.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()
    await expect(dialog).toBeHidden({ timeout: 3_000 })
  })

  // ---------------------------------------------------------------------------
  // 7. Add screen to group via the Screens dialog
  // ---------------------------------------------------------------------------

  test('add screen — moves from Not Assigned to Assigned, badge increments', async ({
    page,
    backendUrl,
  }) => {
    console.log('[screengroups.spec] init socket handlers')
    await gotoScreenGroups(page, backendUrl)

    const row = page.locator('tr', { hasText: sgNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // Open the dialog and ensure the screen is in Not Assigned before we test Add.
    // (Test 2 may have left it in Assigned — remove it via the UI first.)
    await row.locator('.p-badge').nth(0).click()
    const dialog = page.locator('.p-dialog', { hasText: `Screens in ${sgNameHolder.current}` })
    await expect(dialog).toBeVisible({ timeout: 5_000 })
    await expect(dialog.locator('.pi-spin')).toHaveCount(0, { timeout: 8_000 })
    // Wait for the assigned section to finish rendering before checking state.
    // Either a row or an empty-state/paragraph must appear — this prevents the
    // racy isVisible() check that fails in Firefox due to slower paint timing.
    const assignedSection = dialog.locator('.screens-section').first()
    await expect(assignedSection.locator('tr, p')).not.toHaveCount(0, { timeout: 5_000 }).catch(() => {})

    const screensBadge = row.locator('.p-badge').nth(0)
    let countBefore = parseInt((await screensBadge.textContent()) || '0', 10)

    const assignedRow = assignedSection.locator('tr', { hasText: /e2e-sgchk/ }).first()
    if (await assignedRow.isVisible()) {
      await assignedRow.locator('button[title="Remove from group"]').click()
      // Wait for it to leave the assigned section
      await expect(assignedRow).toBeHidden({ timeout: 5_000 })
      // The server pushes the new count; wait for it so the number read below is the settled one.
      countBefore -= 1
      await expect(screensBadge).toHaveText(String(countBefore), { timeout: 8_000 })
    }
    await dialog.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()
    await expect(dialog).toBeHidden({ timeout: 3_000 })

    await screensBadge.click()
    const dialog2 = page.locator('.p-dialog', { hasText: `Screens in ${sgNameHolder.current}` })
    await expect(dialog2).toBeVisible({ timeout: 5_000 })
    await expect(dialog2.locator('.pi-spin')).toHaveCount(0, { timeout: 8_000 })

    // Find the screen in the "Not Assigned" section (second .screens-section) and click +
    const availableSection = dialog2.locator('.screens-section').nth(1)
    const screenRow = availableSection.locator('tr', { hasText: /e2e-sgchk/ }).first()
    await expect(screenRow).toBeVisible({ timeout: 8_000 })
    await screenRow.locator('button[title="Add to group"]').click()

    // Row should appear in the Assigned section
    await expect(
      dialog2
        .locator('.screens-section')
        .first()
        .locator('tr', { hasText: /e2e-sgchk/ }),
    ).toBeVisible({ timeout: 5_000 })

    await dialog2.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()
    await expect(dialog2).toBeHidden({ timeout: 3_000 })

    // Badge should have incremented
    await expect(screensBadge).toHaveText(String(countBefore + 1), { timeout: 8_000 })
  })

  // ---------------------------------------------------------------------------
  // 8. Filter inside the Screens dialog
  // ---------------------------------------------------------------------------

  test('filter in screens dialog hides non-matching assigned screens', async ({
    page,
    backendUrl,
  }) => {
    console.log('[screengroups.spec] init socket handlers')
    await gotoScreenGroups(page, backendUrl)

    const row = page.locator('tr', { hasText: sgNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    await row.locator('.p-badge').nth(0).click()

    const dialog = page.locator('.p-dialog', { hasText: `Screens in ${sgNameHolder.current}` })
    await expect(dialog).toBeVisible({ timeout: 5_000 })
    await expect(dialog.locator('.pi-spin')).toHaveCount(0, { timeout: 8_000 })

    // The assigned screen is named e2e-sgchk-... — filter it out
    const assignedFilter = dialog.locator('input[placeholder="Filter assigned screens..."]')
    await assignedFilter.fill('__no_match__')

    await expect(
      dialog.locator('.screens-section').first().getByText('No assigned screens matching filter'),
    ).toBeVisible({ timeout: 3_000 })

    // Clear → screen reappears
    await assignedFilter.fill('')
    await expect(
      dialog
        .locator('.screens-section')
        .first()
        .locator('tr', { hasText: /e2e-sgchk/ }),
    ).toBeVisible({ timeout: 3_000 })

    await dialog.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()
  })

  // ---------------------------------------------------------------------------
  // 9. Remove screen from group
  // ---------------------------------------------------------------------------

  test('remove screen — moves back to Not Assigned, badge decrements', async ({
    page,
    backendUrl,
  }) => {
    console.log('[screengroups.spec] init socket handlers')
    await gotoScreenGroups(page, backendUrl)

    const row = page.locator('tr', { hasText: sgNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    const screensBadge = row.locator('.p-badge').nth(0)
    const countBefore = parseInt((await screensBadge.textContent()) || '1', 10)

    await screensBadge.click()

    const dialog = page.locator('.p-dialog', { hasText: `Screens in ${sgNameHolder.current}` })
    await expect(dialog).toBeVisible({ timeout: 5_000 })
    await expect(dialog.locator('.pi-spin')).toHaveCount(0, { timeout: 8_000 })

    const screenRow = dialog
      .locator('.screens-section')
      .first()
      .locator('tr', { hasText: /e2e-sgchk/ })
    await expect(screenRow).toBeVisible({ timeout: 5_000 })
    await screenRow.locator('button[title="Remove from group"]').click()

    // Screen should now be in the Not Assigned section
    await expect(
      dialog
        .locator('.screens-section')
        .nth(1)
        .locator('tr', { hasText: /e2e-sgchk/ }),
    ).toBeVisible({ timeout: 5_000 })

    await dialog.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()
    await expect(dialog).toBeHidden({ timeout: 3_000 })

    await expect(screensBadge).toHaveText(String(countBefore - 1), { timeout: 8_000 })
  })

  // ---------------------------------------------------------------------------
  // 10. Remove All screens
  // ---------------------------------------------------------------------------

  test('"Remove All" clears all assigned screens after confirm', async ({ page, backendUrl }) => {
    console.log('[screengroups.spec] init socket handlers')
    await gotoScreenGroups(page, backendUrl)

    const row = page.locator('tr', { hasText: sgNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // Ensure the screen is assigned — add it via UI if it's currently in Not Assigned
    const screensBadge = row.locator('.p-badge').nth(0)
    const initialCount = parseInt((await screensBadge.textContent()) || '0', 10)
    await screensBadge.click()
    const setupDialog = page.locator('.p-dialog', { hasText: `Screens in ${sgNameHolder.current}` })
    await expect(setupDialog).toBeVisible({ timeout: 5_000 })
    await expect(setupDialog.locator('.pi-spin')).toHaveCount(0, { timeout: 8_000 })

    const inAvailable = setupDialog
      .locator('.screens-section')
      .nth(1)
      .locator('tr', { hasText: /e2e-sgchk/ })
      .first()
    if (await inAvailable.isVisible()) {
      await inAvailable.locator('button[title="Add to group"]').click()
      await expect(
        setupDialog
          .locator('.screens-section')
          .first()
          .locator('tr', { hasText: /e2e-sgchk/ }),
      ).toBeVisible({ timeout: 5_000 })
      // Wait until the server has stored it (its pushed count), so "Remove All" below can't run first.
      await expect(screensBadge).toHaveText(String(initialCount + 1), { timeout: 8_000 })
    }
    await setupDialog.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()
    await expect(setupDialog).toBeHidden({ timeout: 3_000 })

    // Now open the dialog and use Remove All
    await screensBadge.click()

    const dialog = page.locator('.p-dialog', { hasText: `Screens in ${sgNameHolder.current}` })
    await expect(dialog).toBeVisible({ timeout: 5_000 })
    await expect(dialog.locator('.pi-spin')).toHaveCount(0, { timeout: 8_000 })

    // "Remove All" footer button — only visible when assignedScreens.length > 0
    await expect(dialog.getByRole('button', { name: 'Remove All' })).toBeVisible({ timeout: 5_000 })
    await dialog.getByRole('button', { name: 'Remove All' }).click()

    await expect(page.getByText(/Remove ALL screens from/)).toBeVisible({ timeout: 5_000 })
    await page.getByRole('button', { name: 'Yes' }).click()

    // Assigned section should now show the empty state
    await expect(dialog.locator('.screens-section').first().locator('.empty-state')).toBeVisible({
      timeout: 8_000,
    })

    await dialog.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()

    // Badge must be 0
    await expect(row.locator('.p-badge').nth(0)).toHaveText('0', { timeout: 8_000 })
  })

  // ---------------------------------------------------------------------------
  // 11. Content badge opens the Content dialog
  // ---------------------------------------------------------------------------

  test('content badge opens the content management dialog', async ({ page, backendUrl }) => {
    console.log('[screengroups.spec] init socket handlers')
    // Seed the content item that will be used in tests 12-14
    await gotoScreenGroups(page, backendUrl)
    const contentTitle = `e2e-sgcnt-${Math.random().toString(36).slice(2, 8)}`
    contentId = await seedContent(page, contentTitle)

    await page.reload()
    await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })

    const row = page.locator('tr', { hasText: sgNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    await row.locator('.p-badge').nth(1).click()

    const dialog = page.locator('.p-dialog', { hasText: `Content in ${sgNameHolder.current}` })
    await expect(dialog).toBeVisible({ timeout: 5_000 })
    await expect(dialog.getByText('Assigned Content', { exact: true })).toBeVisible()
    await expect(dialog.getByText('Not Assigned Content', { exact: true })).toBeVisible()

    await dialog.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()
    await expect(dialog).toBeHidden({ timeout: 3_000 })
  })

  // ---------------------------------------------------------------------------
  // 12. Add content to group
  // ---------------------------------------------------------------------------

  test('add content — moves from Not Assigned to Assigned, badge increments', async ({
    page,
    backendUrl,
  }) => {
    console.log('[screengroups.spec] init socket handlers')
    await gotoScreenGroups(page, backendUrl)

    const row = page.locator('tr', { hasText: sgNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    const contentBadge = row.locator('.p-badge').nth(1)
    const countBefore = parseInt((await contentBadge.textContent()) || '0', 10)

    await contentBadge.click()

    const dialog = page.locator('.p-dialog', { hasText: `Content in ${sgNameHolder.current}` })
    await expect(dialog).toBeVisible({ timeout: 5_000 })
    await expect(dialog.locator('.pi-spin')).toHaveCount(0, { timeout: 8_000 })

    // Find the seeded content in "Not Assigned Content" and click +
    const availableRow = dialog
      .locator('.content-section')
      .nth(1)
      .locator('tr', { hasText: /e2e-sgcnt/ })
      .first()
    await expect(availableRow).toBeVisible({ timeout: 8_000 })
    await availableRow.locator('button[title="Add to group"]').click()

    // Should appear in Assigned section
    await expect(
      dialog
        .locator('.content-section')
        .first()
        .locator('tr', { hasText: /e2e-sgcnt/ }),
    ).toBeVisible({ timeout: 5_000 })

    await dialog.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()
    await expect(dialog).toBeHidden({ timeout: 3_000 })

    await expect(contentBadge).toHaveText(String(countBefore + 1), { timeout: 8_000 })
  })

  // ---------------------------------------------------------------------------
  // 13. Remove content from group
  // ---------------------------------------------------------------------------

  test('remove content — moves back to Not Assigned, badge decrements', async ({
    page,
    backendUrl,
  }) => {
    console.log('[screengroups.spec] init socket handlers')
    await gotoScreenGroups(page, backendUrl)

    const row = page.locator('tr', { hasText: sgNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    const contentBadge = row.locator('.p-badge').nth(1)
    const countBefore = parseInt((await contentBadge.textContent()) || '1', 10)

    await contentBadge.click()

    const dialog = page.locator('.p-dialog', { hasText: `Content in ${sgNameHolder.current}` })
    await expect(dialog).toBeVisible({ timeout: 5_000 })
    await expect(dialog.locator('.pi-spin')).toHaveCount(0, { timeout: 8_000 })

    const assignedRow = dialog
      .locator('.content-section')
      .first()
      .locator('tr', { hasText: /e2e-sgcnt/ })
    await expect(assignedRow).toBeVisible({ timeout: 5_000 })
    await assignedRow.locator('button[title="Remove from group"]').click()

    // Should reappear in Not Assigned
    await expect(
      dialog
        .locator('.content-section')
        .nth(1)
        .locator('tr', { hasText: /e2e-sgcnt/ }),
    ).toBeVisible({ timeout: 5_000 })

    await dialog.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()
    await expect(dialog).toBeHidden({ timeout: 3_000 })

    await expect(contentBadge).toHaveText(String(countBefore - 1), { timeout: 8_000 })
  })

  // ---------------------------------------------------------------------------
  // 14. Remove All content
  // ---------------------------------------------------------------------------

  test('"Remove All" clears all assigned content after confirm', async ({ page, backendUrl }) => {
    console.log('[screengroups.spec] init socket handlers')
    await gotoScreenGroups(page, backendUrl)

    const row = page.locator('tr', { hasText: sgNameHolder.current })
    await expect(row).toBeVisible({ timeout: 10_000 })

    // Ensure content is assigned — add it via UI if currently in Not Assigned
    const contentBadge = row.locator('.p-badge').nth(1)
    const initialCount = parseInt((await contentBadge.textContent()) || '0', 10)
    await contentBadge.click()
    const setupDialog = page.locator('.p-dialog', { hasText: `Content in ${sgNameHolder.current}` })
    await expect(setupDialog).toBeVisible({ timeout: 5_000 })
    await expect(setupDialog.locator('.pi-spin')).toHaveCount(0, { timeout: 8_000 })

    const inAvailableContent = setupDialog
      .locator('.content-section')
      .nth(1)
      .locator('tr', { hasText: /e2e-sgcnt/ })
      .first()
    if (await inAvailableContent.isVisible()) {
      await inAvailableContent.locator('button[title="Add to group"]').click()
      await expect(
        setupDialog
          .locator('.content-section')
          .first()
          .locator('tr', { hasText: /e2e-sgcnt/ }),
      ).toBeVisible({ timeout: 5_000 })
      // Wait until the server has stored it (its pushed count), so "Remove All" below can't run first.
      await expect(contentBadge).toHaveText(String(initialCount + 1), { timeout: 8_000 })
    }
    await setupDialog.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()
    await expect(setupDialog).toBeHidden({ timeout: 3_000 })

    // Now open the dialog and use Remove All
    await contentBadge.click()

    const dialog = page.locator('.p-dialog', { hasText: `Content in ${sgNameHolder.current}` })
    await expect(dialog).toBeVisible({ timeout: 5_000 })
    await expect(dialog.locator('.pi-spin')).toHaveCount(0, { timeout: 8_000 })

    await expect(
      dialog.locator('.p-dialog-footer').getByRole('button', { name: 'Remove All' }),
    ).toBeVisible({ timeout: 5_000 })
    await dialog.locator('.p-dialog-footer').getByRole('button', { name: 'Remove All' }).click()

    await expect(page.getByText(/Remove ALL content from/)).toBeVisible({ timeout: 5_000 })
    await page.getByRole('button', { name: 'Yes' }).click()

    await expect(dialog.locator('.content-section').first().locator('.empty-state')).toBeVisible({
      timeout: 8_000,
    })

    await dialog.locator('.p-dialog-footer').getByRole('button', { name: 'Close' }).click()

    await expect(row.locator('.p-badge').nth(1)).toHaveText('0', { timeout: 8_000 })
  })

  // ---------------------------------------------------------------------------
  // 15. Cleanup
  // ---------------------------------------------------------------------------

  test('cleanup: delete seeded screen, content and screengroup', async ({ page, backendUrl }) => {
    console.log('[screengroups.spec] init socket handlers')
    await gotoScreenGroups(page, backendUrl)

    if (contentId > 0) await deleteContent(page, contentId)
    if (screenId > 0) await deleteScreen(page, screenId)

    // Remove the main test screengroup — first ensure it is empty
    if (sgId > 0) {
      await page.evaluate(
        ({ sgId }: { sgId: number }) =>
          new Promise<void>((resolve) => {
            const socket = (window as any).__displayhive_socket__
            if (!socket) {
              resolve()
              return
            }
            socket.emit('displayhive:admin:cts:remove_all_screens_from_screengroup', {
              screengroup_id: sgId,
            })
            socket.emit('displayhive:admin:cts:remove_all_content_from_screengroup', {
              screengroup_id: sgId,
            })
            setTimeout(resolve, 600)
          }),
        { sgId },
      )
      await deleteScreenGroupById(page, sgId)
    }

    await page.reload()
    await expect(page.locator('.p-datatable')).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('tr', { hasText: sgNameHolder.current })).toHaveCount(0, {
      timeout: 5_000,
    })
  })
})
