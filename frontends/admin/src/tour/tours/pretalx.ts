import type { TourDefinition } from '../types'

// If the person clicked "Next" instead of Cancel/Add, the Add dialog is
// still open — but the table underneath (the next step's target) is
// already mounted regardless of the dialog, so waitForElement would find
// it immediately and highlight it *behind* the still-open dialog instead
// of skipping. Clicking Cancel here closes it exactly like a real
// dismissal would. No-op if the dialog's already closed.
const closePretalxAddDialogIfStillOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="pretalx-add-cancel"]')?.click()
}

export const pretalxTour: TourDefinition = {
  id: 'pretalx',
  title: 'Pretalx',
  description: 'Pull a conference schedule into content via its Pretalx API, and set the display defaults.',
  icon: 'pi pi-calendar',
  category: 'admin',
  steps: [
    {
      route: '/pretalx',
      selector: '[data-tour="pretalx-page"]',
      title: 'Pretalx',
      description:
        'An optional integration for conferences using Pretalx — polls its API for the current/upcoming sessions so they can be rendered as content.',
      side: 'bottom',
    },
    {
      route: '/pretalx',
      selector: '[data-tour="pretalx-add-url"]',
      title: 'Add an endpoint',
      description: 'Register a Pretalx API URL here.',
      side: 'bottom',
      advanceOnClick: true,
    },
    {
      selector: '[data-tour="pretalx-add-fields"]',
      title: 'Name & API URL',
      description: 'The URL is fetched immediately on Add — it must return JSON to be marked valid.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="pretalx-add-cancel"]',
      title: 'Add & Validate',
      description: 'Cancel discards without adding anything.',
      side: 'top',
    },
    {
      route: '/pretalx',
      selector: '[data-tour="pretalx-table"]',
      title: 'Your endpoints',
      description: 'Each row shows whether polling is on, when it next fetches, and whether the last response was valid JSON.',
      side: 'top',
      before: closePretalxAddDialogIfStillOpen,
    },
    {
      selector: '[data-tour="pretalx-row-actions"]',
      title: 'Edit, view cache, delete',
      description: 'Edit changes the name/polling interval (not the URL itself); the eye icon shows the last cached response, useful for debugging a feed that looks wrong.',
      side: 'top',
    },
    {
      selector: '[data-tour="pretalx-texts-fields"]',
      title: 'Default texts',
      description: 'Fallback wording shown when no session is running, or when the API data looks invalid — content can still override these per-field.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="pretalx-datetime-fields"]',
      title: 'Date / time defaults',
      description:
        'The display time format (with a live preview and token reference), end-of-day cutoff, and an optional simulated date/time for previewing how content will look at a specific moment.',
      side: 'top',
    },
  ],
}
