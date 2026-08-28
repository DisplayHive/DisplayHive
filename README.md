# DisplayHive

Self-hosted digital signage for managing screens, content, and schedules in real time.

DisplayHive drives networks of displays (kiosks, TVs, info screens) from a single admin
panel. Content is composed on drag-and-drop layouts with named containers, styled
instance-wide with a design, pushed to screens instantly over Socket.IO, and organized
into groups so you can target one display or a hundred at once.

## Features

- **Live content push** — changes in the admin panel appear on screens immediately via Socket.IO, no polling or refresh required.
- **Layouts & containers** — position named containers on a drag-and-drop canvas (with snapping), reuse across screens.
- **Designs** — style a layout with color palettes, gradients, and animated/dynamic backgrounds, independent of its container placement.
- **Content types** — reusable field schemas (text, image, icon, link, table, Pretalx table, date/time, WYSIWYG, ...) that populate containers.
- **Magic tags** — `{{ var_name }}` placeholders for dynamic values inside designs.
- **Screens & groups** — register devices, assign them to screens, organize screens into groups, and manage assignments from a matrix view.
- **Live preview** — watch exactly what a screen renders from the admin panel without a physical device.
- **Demo mode** — import ready-made example content packages to explore the admin panel with data already in place.
- **Pretalx integration** — pull conference schedules from a Pretalx instance and render them as content.
- **Alerting** — Telegram notifications when screens/devices go online, offline, or hit an error state.
- **Import/export** — back up or migrate any part of an instance (or all of it), by type or individual item, with dependencies auto-included; import can reset the instance or merge into existing data.
- **Rights & groups** — granular per-feature permissions, nested groups, and per-user allow/deny overrides on top of JWT-authenticated, rate-limited login.

## A few clarifying words on the current state

DisplayHive is mostly stable. Things will keep changing, but we don't expect updates to break your running system. See [Contributing](#contributing) for how to reach out or report a bug.

## Architecture

Flask + Flask-SocketIO backend (REST/API + realtime hub), a Vue 3 admin panel, and a
framework-free TypeScript screen client, all served by the same process. See
[Architecture](https://docs.displayhive.org/developer/architecture/) in the docs for the
full breakdown.

## Getting started

```bash
git clone https://github.com/DisplayHive/DisplayHive.git
cd DisplayHive
nix develop   # or: nix-shell — provisions everything and runs first-time setup
npm run dev   # backend + admin panel (:5173) + screen client (:5174)
```

See [Installation](https://docs.displayhive.org/user/installation/) in the docs for
requirements without Nix and production deployment (Docker, NixOS), and
[CONTRIBUTING.md](CONTRIBUTING.md) for running tests and other dev workflows.

## Configuration

Copy `.env.example` to `.env` (or export the variables in your shell). At minimum, set a
real `SECRET_KEY` before deploying. See
[Installation → Configuration](https://docs.displayhive.org/user/installation/#configuration)
in the docs for the full list of environment variables.

## Documentation

The full docs are published at **[docs.displayhive.org](https://docs.displayhive.org/)**
(rebuilt automatically on every push to `main` that touches `docs/`).

The source lives in [`docs/`](docs/) and is built with
[MkDocs](https://www.mkdocs.org/) + Material. To browse it locally instead:

```bash
npm run docs:serve   # http://localhost:8000
```

- **User guide** ([`docs/user/`](docs/user/)) — using the admin panel:
  layouts, designs, content, magic tags, screens/devices/groups, rights &
  groups, integrations, import/export, and settings.
- **Developer guide** ([`docs/developer/`](docs/developer/)) — architecture,
  the real-time content push pipeline, and how to contribute.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get set up, PR conventions,
and our AI-assisted contributions policy. Please report security
vulnerabilities privately per [SECURITY.md](SECURITY.md) rather than as a
public issue. Participation in this project is governed by our
[Code of Conduct](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE)
