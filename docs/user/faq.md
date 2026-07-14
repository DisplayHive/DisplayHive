# FAQ

## What exactly does DisplayHive do?

DisplayHive is self-hosted digital signage: it drives a network of displays
(kiosks, TVs, info screens) from one admin panel. You build page layouts as
HTML/CSS **templates**, drop typed **content** (text, images, tables,
Pretalx schedules, etc.) into named **containers** within them, and assign
that content to **screen groups**. Changes appear on screens instantly over
Socket.IO — there's no publish step, caching, or refresh delay. See
[Templates, containers & content](content-and-templates.md) for the full
workflow.

## Is there something else than a NixOS deployment?

Yes. The [NixOS module](https://github.com/DisplayHive/DisplayHive/blob/main/nix/module.nix)
is a convenience wrapper, not a requirement. Underneath, DisplayHive is a
plain Flask + Flask-SocketIO app, and the module's systemd service is
ultimately just:

```bash
alembic upgrade head
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:<port> app:app
```

You can run that yourself on any Linux host with Python 3.13, Node.js, and
a database (SQLite for small/single-instance setups, or PostgreSQL via
`DATABASE_URL`) — install dependencies from `requirements.txt`, build the
two frontends, put a reverse proxy (e.g. nginx) in front for TLS and
WebSocket forwarding, and manage the process with systemd, another process
supervisor, or a container of your own making. See the root
[README](https://github.com/DisplayHive/DisplayHive#configuration) for the
environment variables involved. There's no official Docker image yet — the
NixOS module is just the only *packaged* path today, not the only
*possible* one.

## How many screens can I connect?

There's no built-in limit — a screen or device is just a database row, and
nothing in the code caps or licenses that count. The practical ceiling
comes from how the backend runs: the standard deployment uses a **single**
`gunicorn` worker process (`--worker-class eventlet -w 1`). Eventlet
handles many concurrent Socket.IO connections efficiently within that one
process, but all traffic is serialized through it — there's no built-in
horizontal scaling across multiple worker processes. The README describes
DisplayHive as comfortable driving "one display or a hundred at once,"
which is the scale it's been built and tested around; nothing stops you
from trying more, but very large deployments haven't been a focus yet.

## What happens if a screen loses its online connection?

- **On screen**: it keeps showing whatever content was last rendered —
  losing connection doesn't blank the display or reload the page. The
  screen client retries the connection automatically (a fixed 20-second
  delay between attempts) until it reaches the server again.
- **On reconnect**: the screen re-syncs and picks up any content changes
  made while it was offline.
- **In the admin panel**: the affected device and screen immediately show
  as **Offline** (a red badge) on the Devices, Screens, Screen Groups, and
  Matrix pages, so you can see at a glance which displays have dropped.
- **Alerting**: if you've set up [Telegram alerting](alerting.md), a
  `Screen Offline` / `Device Offline` notification fires as soon as the
  disconnect is detected, and a matching `Online` notification fires on
  reconnect.

There's no local content cache beyond what's already in the page, so a
screen that loses power (not just network) and restarts will show a blank
page until it reconnects and receives a fresh content push.
