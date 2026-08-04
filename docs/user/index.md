# User Guide

This guide covers day-to-day use of the DisplayHive admin panel — the web
interface where you manage layouts, designs, content, screens, and devices.

Everything here happens at `/admin/` on your DisplayHive instance and pushes
to screens live, no publish step or refresh needed.

## How the pieces fit together

DisplayHive has a handful of core concepts, each covered in its own page —
this is how they relate to each other:

```mermaid
graph LR
  Layout -->|groups positioned| Container
  Design -->|styles| Container
  ContentType -->|scoped to one| Layout
  ContentType -->|allowed in| Container
  Content -->|is an instance of| ContentType
  Content -->|assigned to| Screengroup
  Screengroup -->|contains| Screen
  Device -->|connects as| Screen
```

In short: a **Layout** groups positioned **Containers** on a canvas, and a
**Design** (exactly one active instance-wide) styles them — colors,
gradients, backgrounds, per-container CSS. A **Content Type** is scoped to
one layout and declares which of its containers it's allowed into, and
**Content** is a specific item of a content type, assigned to a **Screen
Group**. Every **Screen** in that group shows it. A **Device** is the
physical/browser player that connects to a screen. See
[Layouts, designs, content types & content](content-and-templates.md) and
[Screens, devices & groups](screens-devices-groups.md) for the details
behind each box.

## Where to start

If you're setting up DisplayHive for the first time, work through these pages
roughly in order:

1. **[Installation](installation.md)** — get an instance running.
2. **[Getting started](getting-started.md)** — a hands-on walkthrough: load
   the demo content, register a device, watch a live update happen, and
   publish your own content type end to end.
3. **[Users & login](users-and-login.md)** — log in for the first time, set
   a real password, and (if you're setting up others) understand rights &
   groups.
4. **[Layouts, designs, content types & content](content-and-templates.md)**
   — build a layout and put content on it.
5. **[Screens, devices & groups](screens-devices-groups.md)** — register a
   physical/browser display and point it at your content.

Once the basics are running, see [Magic tags](magic-tags.md) for reusable
placeholder values, and [Pretalx](pretalx.md) / [Alerting](alerting.md) for
optional integrations (both experimental — see their pages for details).
[Import & export](import-export.md) covers backups,
and [Settings](settings.md) covers instance-wide options. If something's
unclear, check the [FAQ](faq.md) first.
