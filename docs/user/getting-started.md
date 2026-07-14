# Getting started

This is a hands-on walkthrough that takes you from nothing installed to
seeing your own content live on a screen. It's meant to be followed in
order, on a throwaway/local instance — by the end you'll have imported demo
content, adopted a device, watched a live update happen, and published your
own content.

!!! tip "Use the demo instance for this, not production"
    Step 3 below wipes existing content. Follow this guide on a fresh local
    install (see below), not an instance anyone else already relies on.

## 1. Install it

See [Installation](installation.md) for platform-specific steps. For
following this guide, the **dev shell setup is enough** — you don't need a
full production/NixOS-module deployment just to try DisplayHive out locally.

## 2. Make sure everything is actually running

DisplayHive is three cooperating processes: the backend (Flask + Socket.IO),
the admin panel, and the screen client. Content only appears because the
backend pushes it live over Socket.IO to whichever screen clients are
connected — so nothing in the rest of this guide will work unless **all
three are up at once**. `npm run dev` (from the dev shell) starts all of
them together:

| Service | URL |
|---|---|
| Backend | http://localhost:5000 |
| Admin panel | http://localhost:5173 |
| Screen client | http://localhost:5174 |

Keep the admin panel and the screen client open in separate browser tabs (or
windows, side by side) for the rest of this walkthrough — you'll be watching
the screen client tab update live as you make changes in the admin tab.

## 3. Load the "Nordhofen Electric" example

The fastest way to get a fully-populated instance to explore — rather than
starting from an empty one — is to import the bundled demo package. On the
**Demo Mode** page (`/demo`), import **Company - Nordhofen Electric**.

!!! warning "This replaces existing content"
    Importing a demo package wipes and replaces all current content
    system-wide (user accounts are preserved). That's exactly what you want
    on a fresh instance, but see [Import & export](import-export.md) if you
    ever need to back up real content first.

This gives you working templates, content types, content, screens, and
screen groups to check the system with and to use as a reference while you
build your own.

## 4. Preview content without a screen

Before wiring up a real screen, you can see exactly what a piece of content
renders as directly in the admin panel. On the **Content** page (`/content`),
click the chevron on the left of any content row to expand it — this shows
its duration, schedule, field values, and a live scaled-down preview of its
actual rendered HTML.

## 5. Register a device and put a screen on it

Follow [Registering a device](screens-devices-groups.md#registering-a-device)
to adopt your open screen client tab as a **Device**, attaching it to a
**Screen** as you do. If you want to move it to a different screen
afterwards, open the device's edit dialog on the **Devices** page
(`/devices`) and pick a different one from there.

## 6. Watch a live change happen

With your screen client showing content, go back to the admin panel and edit
something it's currently displaying — change a content item's title, tweak
the welcome text in [Settings](settings.md), or edit a template's CSS. Watch
your screen client tab: the change appears immediately, with no refresh and
no publish step. This live push is the core of how DisplayHive works, and
it's worth seeing happen at least once before you build anything of your own.

## 7. Add your own content and show it on your screen

On the **Content** page, add a new content item into a container that's
allowed a text content type (the demo package includes one you can reuse,
e.g. **Free Text**) and that's rendered by the template your registered
screen (from step 5) is using. Fill in a title and the text field, and save.

Check your screen client tab: your text should now be showing live, the same
way the demo content did in step 6. If it landed in a container your screen
doesn't render, use **Move Content** to reassign it — see
[Templates, containers & content](content-and-templates.md) for how
containers and content types fit together.

From here, that page and
[Screens, devices & groups](screens-devices-groups.md) cover each of these
pieces in full depth.

## 8. Have a look around

Now that you've seen the whole flow once, take some time to click through
the rest of the admin panel and see how the Nordhofen Electric example is
put together — its templates, containers, content types, and screen groups
are all real, working examples you can learn from. Then head back to the
**Demo Mode** page (`/demo`) and check out the other example packages
(**Event**, **Hackerspace**) to see different ways templates and content can
be structured.
