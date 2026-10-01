import type { TourDefinition } from '../types'

// Opens a <details class="scheduling-collapsible"> section (Scheduling /
// Duration / Screen Groups & Screens on the Content edit page) before
// highlighting it, so the tour shows its actual fields instead of just the
// collapsed summary line. Idempotent — safe even if already open.
const openDetails = (dataTour: string) => () => {
  const el = document.querySelector<HTMLDetailsElement>(`[data-tour="${dataTour}"]`)
  if (el) el.open = true
}

// If the person clicked the tour's own "Next" instead of an actual content
// type card, selectContentType() never ran and the Select Content Type
// dialog is still open — but the create form underneath (incl.
// .content-edit-preview, the very next step's target) is already mounted
// regardless of the dialog, so waitForElement would find it immediately
// and highlight it *behind* the still-open dialog instead of skipping.
// Clicking the first card here closes the dialog exactly like a real click
// would, so the next step's precondition holds either way. No-ops (nothing
// to click) if a content type was already picked for real.
const ensureContentTypeSelected = () => {
  document.querySelector<HTMLElement>('[data-tour^="contenttype-card-"]')?.click()
}

// Toggles the marker class main.css keys its "keep the preview visible
// above driver.js's overlay" rule off (see .tour-preview-elevated there) —
// only "Content type fields" wants that, not every step on this page, so
// it's added on the way into that step and removed on the way into its
// neighbors (whichever direction "Next"/"Previous" is used to leave it).
const setPreviewElevated = (elevated: boolean) => () => {
  document.querySelector('.content-edit-preview')?.classList.toggle('tour-preview-elevated', elevated)
}

export const createEditContentTour: TourDefinition = {
  id: 'create-edit-content',
  title: 'Creating & Editing Content',
  description: 'Start a new content element, picking any content type, and fill it in with the live preview, scheduling, and screen assignment.',
  icon: 'pi pi-box',
  category: 'user',
  steps: [
    {
      route: '/content',
      selector: '[data-tour="content-new"]',
      title: 'Create new content',
      description: 'Every piece of content on screen starts here. Click "New Content" to start one now.',
      side: 'bottom',
      advanceOnClick: true,
    },
    {
      route: '/content/new',
      // Matches whichever content type card appears first — any content
      // type works to demonstrate the flow, so this doesn't depend on a
      // specific one existing (see docs/developer/tour-design-ruleset.md).
      selector: '[data-tour^="contenttype-card-"]',
      title: 'Pick a content type',
      description: 'A content type defines which fields you fill in. Click one to see its fields.',
      side: 'bottom',
      advanceOnClick: true,
    },
    {
      selector: '.content-edit-preview',
      title: 'Live Preview',
      description:
        'This shows exactly what this content looks like on screen, updating as you type — no need to save first to check your work.',
      side: 'left',
      before: ensureContentTypeSelected,
    },
    {
      selector: '[data-tour="content-title-field"]',
      title: 'Title',
      description: 'Only shown here in the admin backend, never on screen — just to help you keep an overview of your content list.',
      side: 'bottom',
      before: setPreviewElevated(false),
    },
    {
      selector: '.tag-fields-section',
      title: 'Content type fields',
      description:
        'The actual per-field values this content type defines — these are what show up on screen. Watch the Live Preview on the right as you fill them in. An admin may have already locked or pre-filled some of these; anything not locked can still be overwritten.',
      side: 'top',
      before: setPreviewElevated(true),
    },
    {
      selector: '[data-tour="content-scheduling"]',
      title: 'Scheduling',
      description: 'Optionally restrict this content to a start and/or end date — outside that window it\'s simply skipped.',
      side: 'top',
      before: openDetails('content-scheduling'),
    },
    {
      selector: '[data-tour="content-duration"]',
      title: 'Duration',
      description: 'How long this content stays on screen before the next piece of content takes its turn.',
      side: 'top',
      before: openDetails('content-duration'),
    },
    {
      selector: '[data-tour="content-screens"]',
      title: 'Screen Groups & Screens',
      description: 'Which screens actually show this content — assign it to one or more screen groups, or individual screens.',
      side: 'top',
      before: openDetails('content-screens'),
    },
    {
      selector: '[data-tour="content-form-actions"]',
      title: 'Save your changes',
      description:
        'Save writes immediately and returns to the Content list; Update writes immediately too but keeps you here. Either way, every screen this content is currently assigned to updates right away — no manual refresh needed.',
      side: 'top',
    },
  ],
}
