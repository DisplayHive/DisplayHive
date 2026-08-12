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

DisplayHive is by now mostly stable. Things will keep changing, but we don't expect updates to break your running system. Right now, the main rough edges are usability and documentation — some parts of the admin panel aren't as self-explanatory as they could be, and the docs don't yet cover everything. Both have already improved a lot and keep getting better. If you run into a bug, please [open a ticket](https://github.com/DisplayHive/DisplayHive/issues) so we can track it. For everything else, reach out on [Mastodon](https://chaos.social/@DisplayHive), join our [Telegram group](https://t.me/DisplayHiveDicussion) or follow the [announcement channel](https://t.me/DisplayHive) — more ways to reach us at [displayhive.org/contact](https://displayhive.org/contact/).

## AI Usage

At the beginning of development, DisplayHive started without any AI usage. As the code evolved, more and more AI-generated code was introduced to the codebase. But there are no blind commits, and the code should be similar to that of a human programmer. In cases where things were AI-generated, there may be things that slipped through review. If you find something, get in touch. If you intend to use AI help for coding on DisplayHive, this is fine, but ensure small, topic-focused, and checkable commits/pull requests.

## Architecture

| Component         | Stack                                                  | Purpose                                               |
| ----------------- | ------------------------------------------------------ | ----------------------------------------------------- |
| **Backend**       | Flask + Flask-SocketIO (eventlet), SQLAlchemy, Alembic | REST/API + realtime hub, serves both frontends        |
| **Admin panel**   | Vue 3, PrimeVue, Pinia, Vite                           | Manage content, screens, devices, layouts/designs, settings |
| **Screen client** | TypeScript (no framework), Vite                        | Kiosk-facing display client, renders pushed content   |

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

| Service                     | Command               | URL                   |
| --------------------------- | --------------------- | --------------------- |
| Backend (Flask + Socket.IO) | `npm run dev:backend` | http://localhost:5000 |
| Admin panel                 | `npm run dev:admin`   | http://localhost:5173 |
| Screen client               | `npm run dev:screen`  | http://localhost:5174 |

### Tests

```bash
npm run test:e2e         # Playwright, headless
npm run test:e2e:headed  # Playwright, headed
npm run test:e2e:ui      # Playwright interactive UI
```

## Configuration

Copy `.env.example` to `.env` (or export the variables in your shell) to configure:

| Variable                   | Purpose                                                                                   |
| -------------------------- | ----------------------------------------------------------------------------------------- |
| `DATABASE_URL`             | PostgreSQL connection string (omit for local SQLite)                                      |
| `SECRET_KEY`               | Flask session/JWT signing key — set a real value before deploying                         |
| `POSTGRES_PASSWORD`        | Password for the bundled PostgreSQL service (Docker Compose)                              |
| `ADMIN_BOOTSTRAP_USERNAME` | Username of the admin account created on first start (default `admin`)                    |
| `ADMIN_BOOTSTRAP_PASSWORD` | Password for the bootstrap admin account, set on first start                              |
| `CORS_ALLOWED_ORIGINS`     | Comma-separated list of origins allowed to connect over Socket.IO/API                     |
| `TRUSTED_PROXY_COUNT`      | Number of reverse proxies in front of the app, for correct client IPs behind nginx        |
| `FLASK_DEBUG`              | Enables the Werkzeug debugger — local development only, never on a network-reachable host |
| `LOG_LEVEL`                | Python logging level (default `INFO`)                                                     |

## Documentation

The full docs are published at **[displayhive.github.io/DisplayHive](https://displayhive.github.io/DisplayHive/)**
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

## Deployment

### Docker (single container + PostgreSQL)

The [`Dockerfile`](Dockerfile) builds a single image that bundles the Flask/Socket.IO
backend _and_ both pre-built frontends. A [`compose.yml`](compose.yml) is included that
runs this container alongside a PostgreSQL service.

**Requirements:** Docker with the Compose plugin.

```bash
cp .env.example .env      # then edit .env and set the secrets
# Generate a strong SECRET_KEY:  openssl rand -hex 32

docker compose up -d
```

On startup the container applies Alembic migrations (`alembic upgrade head`), then
launches gunicorn with the eventlet worker. Once it's up, everything is served from a
single port:

| Surface               | URL                          |
| --------------------- | ---------------------------- |
| Screen / kiosk client | http://localhost:5000/       |
| Admin panel           | http://localhost:5000/admin/ |
| REST API + Socket.IO  | http://localhost:5000/       |

Set at least `SECRET_KEY`, `POSTGRES_PASSWORD`, and `ADMIN_BOOTSTRAP_PASSWORD` in `.env`
before first start. Uploaded media and generated previews persist in the `media` and
`media_previews` Docker volumes; the database persists in `pgdata`, so they survive
container upgrades.

Useful commands:

```bash
docker compose logs -f displayhive   # follow app logs
docker compose up -d                  # pull the latest image and restart
docker compose down                   # stop (add -v to also delete volumes/data)
```

By default [`compose.yml`](compose.yml) pulls the pre-built
`ghcr.io/displayhive/displayhive:latest` image, published automatically by the
[`docker-image`](.github/workflows/docker-image.yml) workflow on every push to `main`
and on version tags. To build locally from source instead, comment out the `image:`
line and uncomment `build: .`, then run `docker compose up -d --build`.

### NixOS

A NixOS module ([`nix/module.nix`](nix/module.nix)) is included for running one or more
DisplayHive instances as systemd services, each with its own PostgreSQL database and
(optionally) a webhook-triggered auto-deploy on git push. See
[`nix/example.nix`](nix/example.nix) for a full example configuration.

## License

[MIT](LICENSE)
