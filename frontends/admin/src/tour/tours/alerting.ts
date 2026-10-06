import type { TourDefinition } from '../types'

export const alertingTour: TourDefinition = {
  id: 'alerting',
  title: 'Alerting & Logger',
  description: 'Get notified when a screen goes offline, and watch what\'s actually happening live.',
  icon: 'pi pi-bell',
  category: 'admin',
  steps: [
    {
      route: '/alerting',
      selector: '[data-tour="alerting-page"]',
      title: 'Alerting',
      description: 'Routes system alerts (like a screen going offline) to specific people over Telegram.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="alerting-token-field"]',
      title: 'Telegram bot token',
      description: 'The token for your own Telegram bot — create one via @BotFather, then paste its token here and Save.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="alerting-saved-users"]',
      title: 'Alert users',
      description: 'Everyone who currently receives alerts — send a test message to confirm delivery, or remove someone.',
      side: 'top',
    },
    {
      selector: '[data-tour="alerting-bot-users"]',
      title: 'Add a recipient',
      description: 'Anyone who has messaged your bot shows up here once you refresh — add them to turn them into an alert user.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="alerting-matrix"]',
      title: 'Alert routing',
      description: 'Check which alert types each user should receive — saves instantly, no confirmation.',
      side: 'top',
    },
    {
      route: '/logger',
      selector: '[data-tour="logger-page"]',
      title: 'Logger',
      description: 'A live feed of log entries from the admin backend and every connected screen — useful for watching something happen in real time.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="logger-controls"]',
      title: 'Auto-scroll, Test, Clear',
      description:
        'Auto-scroll keeps the view pinned to the newest entry; Test Log adds one harmless entry to confirm the feed is live; Clear only empties this view — it never touches the underlying logs.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="logger-filters"]',
      title: 'Filter the feed',
      description: 'Narrow it down by severity or by a specific screen.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="logger-log-container"]',
      title: 'The feed',
      description: 'Each entry shows its timestamp, severity, originating screen, and the function that logged it.',
      side: 'top',
    },
  ],
}
