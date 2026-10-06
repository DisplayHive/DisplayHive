import type { TourDefinition } from '../types'

// If the person clicked "Next" instead of Save/Cancel, the New Content
// Type dialog is still open — but the table underneath (this step's
// target) is already mounted regardless of the dialog, so waitForElement
// would find it immediately and highlight it *behind* the still-open
// dialog instead of skipping. Clicking the dialog's first button (Cancel)
// here closes it exactly like a real dismissal would. No-op if the
// dialog's already closed.
const closeDialogIfStillOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="contenttype-dialog-footer"] .p-button')?.click()
}

export const contentTypesTour: TourDefinition = {
  id: 'content-types',
  title: 'Content Types',
  description: 'What a content type is, and how it shapes the content you create.',
  icon: 'pi pi-file',
  category: 'admin',
  steps: [
    {
      route: '/contenttypes',
      selector: '[data-tour="contenttypes-page"]',
      title: 'Content Types',
      description:
        'A content type is a template — it defines which fields a piece of content has (text, image, table, ...) before you fill any of them in.',
      side: 'bottom',
    },
    {
      route: '/contenttypes',
      selector: '[data-tour="contenttypes-new"]',
      title: 'Create a content type',
      description: 'Click "New Content Type" to open the editor and see how one is put together.',
      side: 'bottom',
      advanceOnClick: true,
    },
    {
      selector: '[data-tour="contenttype-layout-field"]',
      title: 'Pick a Layout',
      description:
        'The Layout scopes which containers this content type\'s fields can target — pick one from the dropdown and watch the Fields list below fill in.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="contenttype-fields-section"]',
      title: 'Fields',
      description:
        'One field per container of the selected Layout, kept automatically in sync with it — these are what show up on screen when content of this type is created.',
      side: 'top',
    },
    {
      selector: '[data-tour="contenttype-dialog-footer"]',
      title: 'Save or discard',
      description: 'Save keeps this content type; Cancel closes the dialog without creating anything.',
      side: 'top',
      advanceOnClick: true,
    },
    {
      selector: '[data-tour="contenttypes-table"]',
      title: 'Your content types',
      description:
        'Every content type you define shows up here, along with the layout it is used with and how many fields it has.',
      side: 'top',
      before: closeDialogIfStillOpen,
    },
    {
      selector: '[data-tour="contenttypes-filter"]',
      title: 'Finding a content type',
      description: 'Once you have more than a handful, filter the list by name here.',
      side: 'bottom',
    },
  ],
}
