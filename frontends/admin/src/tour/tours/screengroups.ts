import type { TourDefinition } from '../types'

// If the person clicked "Next" instead of Cancel/Save, the New Screen
// Group dialog is still open — but the table underneath (the next step's
// target) is already mounted regardless of the dialog, so waitForElement
// would find it immediately and highlight it *behind* the still-open
// dialog instead of skipping. Clicking Cancel here closes it exactly like
// a real dismissal would. No-op if the dialog's already closed.
const closeScreengroupCreateDialogIfStillOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="screengroups-create-cancel"]')?.click()
}

// Same reasoning, for the Screens-in-group management dialog: it has its
// own Close button distinct from "Save/Cancel" (it isn't a create form),
// so it gets its own closer rather than reusing the one above.
const closeScreensManagementDialogIfStillOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="screengroups-screens-dialog-close"]')?.click()
}

// If the person clicked "Next" instead of the real "screens count" badge,
// the Screens-in-group dialog never opened, so this step's target (inside
// it) wouldn't exist. Clicking the badge here opens it for real either
// way; re-opening an already-open dialog just re-fetches/resets its data,
// so this is safe to run unconditionally.
const ensureScreensDialogOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="screengroups-screens-badge"]')?.click()
}

// Same reasoning as ensureScreensDialogOpen, for the content-count badge
// and its dialog — this is also the tour's *last* step's dependency, so
// without this, clicking only "Next" the whole way through would silently
// end the tour instead of reaching "Exit Tour".
const ensureContentDialogOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="screengroups-content-badge"]')?.click()
}

export const screengroupsTour: TourDefinition = {
  id: 'screengroups',
  title: 'Screen Groups',
  description: 'Group screens together so they share one content rotation, and assign that content once.',
  icon: 'pi pi-th-large',
  category: 'user',
  steps: [
    {
      route: '/screengroups',
      selector: '[data-tour="screengroups-page"]',
      title: 'Screen Groups',
      description:
        'A screen group is a set of screens that all play the same content rotation together — assign content to the group once instead of to each screen individually.',
      side: 'bottom',
    },
    {
      route: '/screengroups',
      selector: '[data-tour="screengroups-new"]',
      title: 'Create a screen group',
      description: 'Click "New Screen Group" to start one.',
      side: 'bottom',
      advanceOnClick: true,
    },
    {
      selector: '[data-tour="screengroup-name-field"]',
      title: 'Name it',
      description: 'Give the group a name, then Save.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="screengroups-table"]',
      title: 'Your screen groups',
      description: 'Each row is a screen group, with how many screens and how much content it currently has.',
      side: 'top',
      before: closeScreengroupCreateDialogIfStillOpen,
    },
    {
      selector: '[data-tour="screengroups-filter"]',
      title: 'Finding a screen group',
      description: 'Once you have more than a handful, filter the list by name here.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="screengroups-screens-badge"]',
      title: 'Manage its screens',
      description: 'Click the screens count to open the group\'s screen membership.',
      side: 'bottom',
      advanceOnClick: true,
    },
    {
      selector: '[data-tour="screengroups-available-screens"]',
      title: 'Assign screens',
      description:
        'Add any of your registered screens to this group from here — the same membership you can also set from a screen\'s own Rename dialog.',
      side: 'top',
      before: ensureScreensDialogOpen,
    },
    {
      selector: '[data-tour="screengroups-content-badge"]',
      title: 'Manage its content',
      description: 'Click the content count to open the group\'s content assignment — this is separate from screen membership.',
      side: 'bottom',
      advanceOnClick: true,
      before: closeScreensManagementDialogIfStillOpen,
    },
    {
      selector: '[data-tour="screengroups-available-content"]',
      title: 'Assign content',
      description:
        'Add any existing content element to this group — once added, it joins the shared rotation every screen in this group plays.',
      side: 'top',
      before: ensureContentDialogOpen,
    },
  ],
}
