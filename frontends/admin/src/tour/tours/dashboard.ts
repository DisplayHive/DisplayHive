import type { TourDefinition } from '../types'

export const dashboardTour: TourDefinition = {
  id: 'dashboard',
  title: 'Dashboard',
  description: 'What each at-a-glance status tile on the Dashboard is telling you.',
  icon: 'pi pi-home',
  category: 'user',
  steps: [
    {
      route: '/',
      selector: '[data-tour="dashboard-stats-grid"]',
      title: 'Status tiles',
      description:
        'Each tile is a live count for one area of DisplayHive — turning orange/red flags something worth a look. Clicking a tile jumps straight to that page.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="stat-screens"]',
      title: 'Screens',
      description:
        'How many screens are registered, how many are currently online, and — once any screen is fullscreen or windowed — that split too. Any screen offline turns this tile orange.',
      side: 'right',
    },
    {
      selector: '[data-tour="stat-devices"]',
      title: 'Devices',
      description: 'How many active devices you have, and how many are currently online. Any active device offline turns this tile orange.',
      side: 'left',
    },
    {
      selector: '[data-tour="stat-content"]',
      title: 'Content',
      description:
        'Your total content elements, and how many aren\'t assigned to any screen group — unassigned content never shows anywhere, so this flags content that\'s effectively invisible.',
      side: 'right',
    },
    {
      selector: '[data-tour="stat-screengroups"]',
      title: 'Screen Groups',
      description: 'How many screen groups currently exist.',
      side: 'left',
    },
    {
      selector: '[data-tour="stat-media"]',
      title: 'Media',
      description: 'How many files are in your media library.',
      side: 'right',
    },
    {
      selector: '[data-tour="stat-find"]',
      title: 'Find Mode',
      description:
        'How many screens currently have Find Mode active (flashing an on-screen marker so you can locate the physical device) — left on by accident, it\'s easy to forget about, so this tile flags it.',
      side: 'left',
    },
    {
      selector: '[data-tour="stat-debug"]',
      title: 'Debug Mode',
      description:
        'How many screens currently have their diagnostic overlay switched on — same idea as Find Mode: easy to leave on after troubleshooting, so this tile flags it.',
      side: 'right',
    },
  ],
}
