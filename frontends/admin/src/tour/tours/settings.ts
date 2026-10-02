import type { TourDefinition } from '../types'

export const settingsTour: TourDefinition = {
  id: 'settings',
  title: 'Settings',
  description: 'The first things to configure on a new instance: branding, visibility, and time.',
  icon: 'pi pi-cog',
  category: 'admin',
  steps: [
    {
      route: '/settings',
      selector: '[data-tour="settings-page"]',
      title: 'Settings',
      description: 'System-wide settings, split into a few independent cards — each has its own Save.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="settings-welcome-fields"]',
      title: 'Welcome message',
      description: 'The headline and text shown on the Dashboard\'s welcome card — customize it for your organization.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="settings-visibility-toggles"]',
      title: 'Hide things you don\'t need',
      description:
        'Each toggle removes one optional piece of UI — community links, the screen footer badge, Demo Mode, or either half of the Guided Tour catalog — without affecting anything else.',
      side: 'top',
    },
    {
      selector: '[data-tour="settings-dashboard-save"]',
      title: 'Save',
      description: 'Each card on this page saves independently — this one only applies the Dashboard fields above.',
      side: 'top',
    },
    {
      selector: '[data-tour="settings-content-preview-fields"]',
      title: 'Content editor preview size',
      description:
        'How much room the live preview takes up on the Content edit page, and in a content row\'s expanded view in the Content list.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="settings-content-save"]',
      title: 'Save',
      description: 'Takes effect immediately, even for anyone with the Content edit page already open.',
      side: 'top',
    },
    {
      selector: '[data-tour="settings-timezone-field"]',
      title: 'Timezone',
      description:
        'DisplayHive Time above updates live as you pick a timezone — compare it against Server time before saving to make sure you picked the right one.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="settings-time-save"]',
      title: 'Save',
      description: 'Scheduling across the whole instance (content start/end dates, durations) is interpreted in this timezone.',
      side: 'top',
    },
  ],
}
