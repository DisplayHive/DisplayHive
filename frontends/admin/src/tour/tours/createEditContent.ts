import type { TourDefinition } from '../types'

// Assumes the tour-content package's fixed IDs: contenttype 5 = "DHcon
// Title", content_element 13 = "DHCON Intropage" — see tourcontent/tour.zip.
const DHCON_TITLE_CONTENTTYPE_ID = 5
const DHCON_INTROPAGE_CONTENT_ID = 13

// Opens a <details class="scheduling-collapsible"> section (Scheduling /
// Duration / Screen Groups & Screens on the Content edit page) before
// highlighting it, so the tour shows its actual fields instead of just the
// collapsed summary line. Idempotent — safe even if already open.
const openDetails = (dataTour: string) => () => {
  const el = document.querySelector<HTMLDetailsElement>(`[data-tour="${dataTour}"]`)
  if (el) el.open = true
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
  description: 'Start a new content element, then edit an existing one with the live preview, scheduling, and screen assignment.',
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
      selector: `[data-tour="contenttype-card-${DHCON_TITLE_CONTENTTYPE_ID}"]`,
      title: 'Pick a content type',
      description: 'A content type defines which fields you fill in. Click "DHcon Title" to see its fields.',
      side: 'bottom',
      advanceOnClick: true,
    },
    {
      route: `/content/${DHCON_INTROPAGE_CONTENT_ID}/edit`,
      selector: '.content-edit-preview',
      title: 'Live Preview',
      description:
        'This shows exactly what this content looks like on screen, updating as you type — no need to save first to check your work.',
      side: 'left',
    },
    {
      route: `/content/${DHCON_INTROPAGE_CONTENT_ID}/edit`,
      selector: '#create-title',
      title: 'Title',
      description: 'Only shown here in the admin backend, never on screen — just to help you keep an overview of your content list.',
      side: 'bottom',
      before: setPreviewElevated(false),
    },
    {
      route: `/content/${DHCON_INTROPAGE_CONTENT_ID}/edit`,
      selector: '.tag-fields-section',
      title: 'Content type fields',
      description:
        'The actual per-field values this content type defines — these are what show up on screen. Watch the Live Preview on the right as you fill them in.',
      side: 'top',
      before: setPreviewElevated(true),
    },
    {
      route: `/content/${DHCON_INTROPAGE_CONTENT_ID}/edit`,
      selector: '.content-edit-preview',
      title: 'Preset by an admin',
      description:
        'An admin has already decided which of these fields you can edit here, and may have pre-filled some with default values — anything not locked can still be overwritten.',
      side: 'left',
      before: setPreviewElevated(false),
    },
    {
      route: `/content/${DHCON_INTROPAGE_CONTENT_ID}/edit`,
      selector: '[data-tour="content-scheduling"]',
      title: 'Scheduling',
      description: 'Optionally restrict this content to a start and/or end date — outside that window it\'s simply skipped.',
      side: 'top',
      before: openDetails('content-scheduling'),
    },
    {
      route: `/content/${DHCON_INTROPAGE_CONTENT_ID}/edit`,
      selector: '[data-tour="content-duration"]',
      title: 'Duration',
      description: 'How long this content stays on screen before the next piece of content takes its turn.',
      side: 'top',
      before: openDetails('content-duration'),
    },
    {
      route: `/content/${DHCON_INTROPAGE_CONTENT_ID}/edit`,
      selector: '[data-tour="content-screens"]',
      title: 'Screen Groups & Screens',
      description: 'Which screens actually show this content — assign it to one or more screen groups, or individual screens.',
      side: 'top',
      before: openDetails('content-screens'),
    },
    {
      route: `/content/${DHCON_INTROPAGE_CONTENT_ID}/edit`,
      selector: '.content-edit-form-actions',
      title: 'Save your changes',
      description:
        'Save writes immediately and returns to the Content list; Update writes immediately too but keeps you here. Either way, every screen this content is currently assigned to updates right away — no manual refresh needed.',
      side: 'top',
    },
  ],
}
