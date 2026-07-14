# DisplayHive

Self-hosted digital signage for managing screens, content, and schedules in real time.

DisplayHive drives networks of displays (kiosks, TVs, info screens) from a single admin
panel. Content is composed from HTML/CSS templates with named containers, pushed to
screens instantly over Socket.IO, and organized into groups so you can target one
display or a hundred at once.

## Features

- **Live content push** — changes in the admin panel appear on screens immediately via Socket.IO, no polling or refresh required.
- **Templates & containers** — build layouts once, drop typed content elements into named containers, reuse across screens.
- **Magic tags** — `{{variable}}` placeholders for dynamic values inside templates.
- **Screens & groups** — register devices, assign them to screens, organize screens into groups, and manage assignments from a matrix view.
- **Pretalx integration** — pull conference schedules from a Pretalx instance and render them as content.
- **Alerting** — Telegram notifications when screens/devices go online, offline, or hit an error state.
- **Import/export** — back up or migrate a full instance (database + media) as a single archive.
- **JWT auth** — admin accounts with rate-limited login, no third-party auth dependency.

## A few clarifying words on the current state

DisplayHive is currently in its early stages of development. Even if it is already quite powerful, there may be some issues. If you encounter them or want to help, just contact us on Mastodon (displayhive@chaos.social).
Some of our main issues are:
- No rights management
- Some features are not as feature-rich or self-explanatory as they should be


## AI Usage

At the beginning of development, DisplayHive started without any AI usage. As the code evolved, more and more AI-generated code was introduced to the codebase. But there are no blind commits, and the code should be similar to that of a human programmer. In cases where things were AI-generated, there may be things that slipped through review. If you find something, get in touch. If you intend to use AI help for coding on DisplayHive, this is fine, but ensure small, topic-focused, and checkable commits/pull requests.


## Architecture

| Component | Stack | Purpose |
|---|---|---|
| **Backend** | Flask + Flask-SocketIO (eventlet), SQLAlchemy, Alembic | REST/API + realtime hub, serves both frontends |
| **Admin panel** | Vue 3, PrimeVue, Pinia, Vite | Manage content, screens, devices, templates, settings |
| **Screen client** | TypeScript (no framework), Vite | Kiosk-facing display client, renders pushed content |

SQLite is used for local development; set `DATABASE_URL` to point at PostgreSQL in
production. Schema changes are managed with Alembic migrations.

## Getting started

### Requirements

- [Nix](https://nixos.org/download) (recommended — provisions Python, Node, and all
  system dependencies for you), or manually: Python 3.13, Node.js, SQLite

### Setup

```bash
nix develop   # or: nix-shell
```

Entering the shell installs JS dependencies (root + both frontends) and runs
`alembic upgrade head` automatically. With [direnv](https://direnv.net/) hooked into
your shell, this happens automatically on `cd` into the repo (`direnv allow`).

### Run

```bash
npm run dev
```

Starts the backend and both frontends together:

| Service | Command | URL |
|---|---|---|
| Backend (Flask + Socket.IO) | `npm run dev:backend` | http://localhost:5000 |
| Admin panel | `npm run dev:admin` | http://localhost:5173 |
| Screen client | `npm run dev:screen` | http://localhost:5174 |

### Tests

```bash
npm run test:e2e         # Playwright, headless
npm run test:e2e:headed  # Playwright, headed
npm run test:e2e:ui      # Playwright interactive UI
```

## Configuration

Copy `.env.example` to `.env` (or export the variables in your shell) to configure:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (omit for local SQLite) |
| `SECRET_KEY` | Flask session/JWT signing key — set a real value before deploying |
| `CORS_ALLOWED_ORIGINS` | Comma-separated list of origins allowed to connect over Socket.IO/API |
| `TRUSTED_PROXY_COUNT` | Number of reverse proxies in front of the app, for correct client IPs behind nginx |
| `FLASK_DEBUG` | Enables the Werkzeug debugger — local development only, never on a network-reachable host |
| `LOG_LEVEL` | Python logging level (default `INFO`) |

## Documentation

The full docs are published at **[displayhive.github.io/DisplayHive](https://displayhive.github.io/DisplayHive/)**
(rebuilt automatically on every push to `main` that touches `docs/`).

The source lives in [`docs/`](docs/) and is built with
[MkDocs](https://www.mkdocs.org/) + Material. To browse it locally instead:

```bash
npm run docs:serve   # http://localhost:8000
```

- **User guide** ([`docs/user/`](docs/user/)) — using the admin panel:
  templates, content, magic tags, screens/devices/groups, integrations,
  import/export, and settings.
- **Developer guide** ([`docs/developer/`](docs/developer/)) — architecture,
  the real-time content push pipeline, and how to contribute.

## Deployment

A NixOS module ([`nix/module.nix`](nix/module.nix)) is included for running one or more
DisplayHive instances as systemd services, each with its own PostgreSQL database and
(optionally) a webhook-triggered auto-deploy on git push. See
[`nix/example.nix`](nix/example.nix) for a full example configuration.

## License

[MIT](LICENSE)
