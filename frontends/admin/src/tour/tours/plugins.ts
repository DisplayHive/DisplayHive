import type { TourDefinition } from '../types'

export const pluginsTour: TourDefinition = {
  id: 'plugins',
  title: 'Plugins',
  description: 'Switch field handlers and integrations on and off, install new ones, and free the server\'s memory with a restart.',
  icon: 'pi pi-box',
  category: 'admin',
  steps: [
    {
      route: '/plugins',
      selector: '[data-tour="plugins-page"]',
      title: 'Plugins',
      description:
        'Field handlers (what a field of a content type can hold) and integrations are plugins. Everything here takes effect at once — no restart.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="plugins-integrations"]',
      title: 'Integrations',
      description: 'Larger add-ons with a page of their own, like Pretalx. Switch one on with its toggle; switching off keeps its data.',
      side: 'top',
    },
    {
      selector: '[data-tour="plugins-handlers"]',
      title: 'Field handlers',
      description:
        'One plugin per kind of field. Switch off the ones you never use and they disappear from the field-handler lists. Content that uses a switched-off handler shows that field empty until it is back on.',
      side: 'top',
    },
    {
      selector: '[data-tour="plugins-install"]',
      title: 'Install a plugin',
      description:
        'From a ZIP file, from a link plus its SHA-256 checksum, or from the catalog if one is set up. A plugin is program code with the server\'s rights — install only what you trust.',
      side: 'top',
    },
    {
      selector: '[data-tour="plugins-page"]',
      title: 'Restart offer',
      description:
        'When you switch off or replace a plugin, its old code stays in the server\'s memory. A notice at the top of this page counts those versions and offers a restart; nothing is wrong until then.',
      side: 'bottom',
    },
  ],
}
