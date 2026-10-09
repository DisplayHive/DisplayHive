import type { TourDefinition } from '../types'

// If the person clicked "Next" instead of Cancel/Create, the Add Screen
// dialog is still open — but the table underneath (the next step's target)
// is already mounted regardless of the dialog, so waitForElement would
// find it immediately and highlight it *behind* the still-open dialog
// instead of skipping. Clicking Cancel here closes it exactly like a real
// dismissal would. No-op if the dialog's already closed.
const closeScreenCreateDialogIfStillOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="screens-create-cancel"]')?.click()
}

// If the person clicked "Next" instead of the real "Rename & group"
// button, the Rename dialog never opened, so this step's target (a field
// inside it) wouldn't exist — and since this is the tour's *last* step,
// that would silently end the tour instead of reaching "Exit Tour".
// Clicking the button here opens it for real either way; re-opening an
// already-open rename dialog just resets its form, so this is safe to
// run unconditionally.
const ensureRenameDialogOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="screens-row-rename"]')?.click()
}

export const screensTour: TourDefinition = {
  id: 'screens',
  title: 'Screens',
  description: 'Register a screen, then preview, reload, debug, and monitor it day to day.',
  icon: 'pi pi-desktop',
  category: 'user',
  steps: [
    {
      route: '/screens',
      selector: '[data-tour="screens-page"]',
      title: 'Screens',
      description: 'A screen is a registered, named display — this is where you manage every one of them.',
      side: 'bottom',
    },
    {
      route: '/screens',
      selector: '[data-tour="screens-new"]',
      title: 'Register a screen',
      description: 'Click "Add Screen" to register a new display.',
      side: 'bottom',
      advanceOnClick: true,
    },
    {
      selector: '[data-tour="screen-name-field"]',
      title: 'Name it',
      description:
        'Give it a name you\'ll recognize later, then Create — pairing actual hardware to this screen happens on the Devices page.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="screens-table"]',
      title: 'Your screens',
      description: 'Every registered screen shows up here, with its live online/fullscreen status.',
      side: 'top',
      before: closeScreenCreateDialogIfStillOpen,
    },
    {
      selector: '[data-tour="screens-filter"]',
      title: 'Finding a screen',
      description: 'Once you have more than a handful, filter the list by name here.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="screens-status-filters"]',
      title: 'Quick status filters',
      description:
        'Click any of these to narrow the table: Windowed / Fullscreen is whether the screen\'s browser view currently fills its device\'s whole display or not; Online / Offline is whether its device is currently connected at all.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="screens-preview-button"]',
      title: 'Preview',
      description:
        'Opens a live, read-only view of whatever this screen is currently showing — only works once a device is attached to it.',
      side: 'top',
    },
    {
      selector: '[data-tour="screens-row-reload"]',
      title: 'Reload',
      description: 'Forces this screen\'s device to refresh its page — useful if it ever gets stuck showing stale content.',
      side: 'top',
    },
    {
      selector: '[data-tour="page-more-actions"]',
      title: 'More actions',
      description:
        'Reload All sends the same reload to every registered screen at once. Rarely needed actions live in this menu; the lists update by themselves.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="screens-row-debug"]',
      title: 'Toggle Debug',
      description:
        'Shows a diagnostic overlay directly on the screen\'s own display (resolution, connection state, current scene) — useful when troubleshooting on-site without needing a laptop.',
      side: 'top',
    },
    {
      selector: '[data-tour="screens-row-monitor"]',
      title: 'Online monitoring',
      description:
        'Disables alerting for this screen going offline — use it for a screen you expect to be powered off sometimes (e.g. only running during business hours), so it doesn\'t trigger false offline alerts.',
      side: 'top',
    },
    {
      selector: '[data-tour="screens-row-rename"]',
      title: 'Rename & group',
      description: 'Rename a screen, or change which screen groups it belongs to, from here.',
      side: 'left',
      advanceOnClick: true,
    },
    {
      selector: '[data-tour="rename-screengroups-field"]',
      title: 'Screen Groups',
      description:
        'Tick the groups this screen should belong to — it immediately starts sharing whatever content rotation those groups define. Save to apply. See the Screen Groups tour for how groups themselves work.',
      side: 'top',
      before: ensureRenameDialogOpen,
    },
  ],
}
