# Alerting

DisplayHive can send Telegram notifications when a screen or device changes
state — useful for catching a display that's gone offline before an
audience notices.

!!! warning "Experimental"
    Alerting is experimental and may change in the future, including
    breaking changes to its configuration or behavior.

Configure alerting from the **Alerting** page (`/alerting`).

## Setup

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather) and copy
   its bot token into the Alerting page.
2. Message the bot from the Telegram account(s) you want to receive alerts.
3. Click **fetch users from bot** — this reads Telegram's update log and
   lists the chats that have messaged it.
4. Save one or more of those chats as a named **Telegram user**.

## Subscribing to alerts

For each saved Telegram user, choose which alert types they should receive:

- Screen offline / online
- Screen not maximized / maximized
- Screen in debug mode on / off
- Screen in find mode on / off
- Device offline / online

Use **send test message** to confirm delivery before relying on it. Alerts
fire automatically whenever the corresponding state change happens — there's
nothing further to trigger manually.
