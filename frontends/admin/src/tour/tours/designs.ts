import type { TourDefinition } from '../types'

// If the person clicked "Next" instead of Cancel/Save, the Design dialog
// is still open — but the table underneath (the next step's target) is
// already mounted regardless of the dialog, so waitForElement would find
// it immediately and highlight it *behind* the still-open dialog instead
// of skipping. Clicking Cancel here closes it exactly like a real
// dismissal would. No-op if the dialog's already closed.
const closeDesignDialogIfStillOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="designs-dialog-cancel"]')?.click()
}

// If the person clicked "Next" instead of the real "Create a design"
// button, the dialog never opened, so this step's target (inside it)
// wouldn't exist. Clicking the button here opens it for real either way;
// re-opening an already-open "new" dialog just resets its form, so this
// is safe to run unconditionally.
const ensureNewDesignDialogOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="designs-new"]')?.click()
}

// Same reasoning as ensureNewDesignDialogOpen, for the "Edit" button and
// its dialog — this also gates every later step down to the tour's last
// one, so without this, clicking only "Next" the whole way through would
// silently end the tour instead of reaching "Exit Tour".
const ensureEditDesignDialogOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="designs-row-edit"]')?.click()
}

export const designsTour: TourDefinition = {
  id: 'designs',
  title: 'Designs',
  description: 'The global visual skin every screen renders through — colors, backdrop, effects, and raw CSS.',
  icon: 'pi pi-palette',
  category: 'admin',
  steps: [
    {
      route: '/designs',
      selector: '[data-tour="designs-page"]',
      title: 'Designs',
      description:
        'A Design is the instance-wide skin — exactly one is active at a time, and every screen renders through it.',
      side: 'bottom',
    },
    {
      route: '/designs',
      selector: '[data-tour="designs-new"]',
      title: 'Create a design',
      description: 'Start a new one here — its styling panels unlock the first time you save it.',
      side: 'bottom',
      advanceOnClick: true,
    },
    {
      selector: '[data-tour="designs-name-fields"]',
      title: 'Name it',
      description: 'A name and optional description to tell designs apart in the list.',
      side: 'bottom',
      before: ensureNewDesignDialogOpen,
    },
    {
      selector: '[data-tour="designs-dialog-cancel"]',
      title: 'Save or Cancel',
      description: 'Save creates it (not yet active); Cancel discards without creating anything.',
      side: 'top',
    },
    {
      route: '/designs',
      selector: '[data-tour="designs-table"]',
      title: 'Your designs',
      description: 'Every design you\'ve created shows up here — the "Active" tag marks the one currently live.',
      side: 'top',
      before: closeDesignDialogIfStillOpen,
    },
    {
      selector: '[data-tour="designs-filter"]',
      title: 'Finding a design',
      description: 'Once you have more than a handful, filter the list by name here.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="designs-row-make-active"]',
      title: 'Make Active',
      description: 'Switches the live skin for the whole instance immediately — every screen picks it up right away.',
      side: 'top',
    },
    {
      selector: '[data-tour="designs-row-edit"]',
      title: 'Edit',
      description: 'Open an existing design to see its full styling panels.',
      side: 'top',
      advanceOnClick: true,
    },
    {
      selector: '[data-tour="designs-default-colors-header"]',
      title: 'Default Colors',
      description: 'A named palette for this design — any color field elsewhere can reuse one of these by name instead of a raw hex value.',
      side: 'top',
      before: ensureEditDesignDialogOpen,
    },
    {
      selector: '[data-tour="designs-backdrop-header"]',
      title: 'Backdrop',
      description: 'The page background every screen sits on: one or more gradients layered on top of a background image or color.',
      side: 'top',
    },
    {
      selector: '[data-tour="designs-effect-header"]',
      title: 'Background Effect',
      description: 'An optional animated effect (particles, waves, etc.) rendered behind the content containers.',
      side: 'top',
    },
    {
      selector: '[data-tour="designs-global-styles-header"]',
      title: 'Global Styles',
      description: 'Base typography and color defaults that apply across every container, unless a container overrides them.',
      side: 'top',
    },
    {
      selector: '[data-tour="designs-custom-html-header"]',
      title: 'Custom HTML and CSS',
      description: 'An escape hatch for anything the panels above don\'t cover — raw HTML/CSS merged into the rendered screen.',
      side: 'top',
    },
    {
      selector: '[data-tour="designs-dialog-cancel"]',
      title: 'Save your changes',
      description: 'Save/Update applies your styling changes immediately to every screen currently using this design (if it\'s the active one).',
      side: 'top',
    },
  ],
}
