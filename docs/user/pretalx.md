# Pretalx integration

DisplayHive can pull a conference schedule from a [Pretalx](https://pretalx.com/)
instance and render it as live content — useful for "next up in this room"
displays at conferences.

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

## Where Pretalx may be

DisplayHive fetches the address you enter from the server, so it does not
connect to addresses inside your own network by default — otherwise whoever can
add a source could make the server reach internal services. An address that
points to a private network (10.x.x.x, 192.168.x.x, 172.16–31.x.x, `localhost`,
`fc00::/7`, …) is refused when you add it, with a message saying so. Public
addresses work as before; so does a name that resolves to a public address.

If your Pretalx really runs inside the network, a **Superadmin** switches on
**Settings → Security → Allow requests to private networks** (or the operator
sets `OUTBOUND_ALLOW_PRIVATE=1`). The cloud metadata address
(`169.254.169.254`) and other special-purpose addresses stay blocked either way,
and redirects are checked address by address. The same applies to the SSO
provider addresses.

## Showing it on a screen

Create a **Content Type** (see
[Layouts, designs, content types & content](content-and-templates.md)) with
a field using the **Pretalx Table** handler. When creating content of that
type, pick:

- which Pretalx URL/room to pull from,
- a room name filter,
- how many sessions to show,
- which schedule fields/columns to display,
- layout (list or track list),
- toggles like "show author under title" or "group by day".

The content re-renders and pushes to screens automatically every time the
Pretalx source is successfully re-fetched — no manual refresh needed.
