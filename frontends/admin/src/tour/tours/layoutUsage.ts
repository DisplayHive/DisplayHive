import type { TourDefinition } from '../types'

export const layoutUsageTour: TourDefinition = {
  id: 'layout-usage',
  title: 'Layouts',
  description: 'How layouts arrange containers, and how content types plug into them.',
  icon: 'pi pi-th-large',
  category: 'admin',
  steps: [
    {
      route: '/layouts',
      selector: '[data-tour="layouts-page"]',
      title: 'Layouts',
      description:
        'A layout arranges one or more containers on screen — each container later holds content from a content type you assign to it.',
      side: 'bottom',
    },
    {
      route: '/layouts',
      selector: '[data-tour="layouts-new"]',
      title: 'Create a layout',
      description: 'Start a new layout here, then use the layout editor to draw and size its containers.',
      side: 'bottom',
      advanceOnClick: true,
    },
    {
      selector: '[data-tour="layout-name-field"]',
      title: 'Name it',
      description: 'Give the layout a name you\'ll recognize later — you can always change it afterwards.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="layout-create-actions"]',
      title: 'Create',
      description:
        'Saving creates the layout and opens its canvas, where you draw containers directly on the page — drag to move/resize, or draw new ones on empty space.',
      side: 'top',
    },
    {
      route: '/layouts',
      selector: '[data-tour="layouts-table"]',
      title: 'Your layouts',
      description:
        'Each row is a layout, with how many containers it has. A layout cannot be deleted while a content type is still using it.',
      side: 'top',
    },
    {
      route: '/layouts',
      selector: '[data-tour="layouts-filter"]',
      title: 'Finding a layout',
      description: 'Once you have more than a handful, filter the list by name here.',
      side: 'bottom',
    },
    {
      route: '/layouts',
      selector: '[data-tour="layouts-row-actions"]',
      title: 'Edit a layout',
      description:
        'Open the layout editor from here — container content now follows its container automatically as you resize it.',
      side: 'left',
    },
  ],
}
