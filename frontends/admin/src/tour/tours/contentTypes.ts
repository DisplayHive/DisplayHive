import type { TourDefinition } from '../types'

export const contentTypesTour: TourDefinition = {
  id: 'content-types',
  title: 'Content Types',
  description: 'What a content type is, and how it shapes the content you create.',
  icon: 'pi pi-file',
  category: 'user',
  steps: [
    {
      route: '/contenttypes',
      selector: '.contenttypes-view',
      title: 'Content Types',
      description:
        'A content type is a template — it defines which fields a piece of content has (text, image, table, ...) before you fill any of them in.',
      side: 'bottom',
    },
    {
      route: '/contenttypes',
      selector: '[data-tour="contenttypes-new"]',
      title: 'Create a content type',
      description: 'Start here to define a new content type: give it a name and add fields to it.',
      side: 'bottom',
    },
    {
      route: '/contenttypes',
      selector: '[data-tour="contenttypes-table"]',
      title: 'Your content types',
      description:
        'Every content type you define shows up here, along with the layout it is used with and how many fields it has.',
      side: 'top',
    },
    {
      route: '/contenttypes',
      selector: '[data-tour="contenttypes-filter"]',
      title: 'Finding a content type',
      description: 'Once you have more than a handful, filter the list by name here.',
      side: 'bottom',
    },
  ],
}
