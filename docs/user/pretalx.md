# Pretalx integration

DisplayHive can pull a conference schedule from a [Pretalx](https://pretalx.com/)
instance and render it as live content — useful for "next up in this room"
displays at conferences.

!!! warning "Experimental"
    The Pretalx integration is experimental and may change in the future,
    including breaking changes to its configuration or behavior.

## Configuring a source

On the **Pretalx** page (`/pretalx`):

1. Add a **Pretalx API URL**: a name plus the schedule URL (`schedule.json` /
   widget URL) for the event.
2. DisplayHive validates it with a test fetch.
3. Optionally enable **polling** with an interval (minimum 30 seconds) so
   the schedule refreshes automatically in the background.

Global display settings are also configured on this page: time format, an
"end of day" cutoff, the text shown for "no session running" / "coming up
next" / invalid data, and an optional simulated date/time for previewing how
the schedule will look at a future point.

## Showing it on a screen

Create a **Content Type** (see
[Templates, containers & content](content-and-templates.md)) with a field
using the **pretalx** handler. When creating content of that type, pick:

- which Pretalx URL/room to pull from,
- a room name filter,
- how many sessions to show,
- which schedule fields/columns to display,
- layout (list or track list),
- toggles like "show author under title" or "group by day".

The content re-renders and pushes to screens automatically every time the
Pretalx source is successfully re-fetched — no manual refresh needed.
