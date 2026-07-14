# Architecture

| Component | Stack | Purpose |
|---|---|---|
| Backend | Flask + Flask-SocketIO (eventlet), SQLAlchemy, Alembic | REST/API + realtime hub, serves both frontends |
| Admin panel | Vue 3, PrimeVue, Pinia, Vite | Manage content, screens, devices, templates, settings |
| Screen client | TypeScript (no framework), Vite | Kiosk-facing display client, renders pushed content |

## Backend entrypoint

Everything starts in [`app.py`](https://github.com/DisplayHive/DisplayHive/blob/main/app.py):

- `eventlet.monkey_patch()` runs first, before any other import, so
  networking stays cooperative under eventlet's async model.
- The Flask app is created and configured with the DB URI (`DATABASE_URL`
  for Postgres, falling back to local SQLite), CORS restricted to `/api/*`
  with an allowlist from `CORS_ALLOWED_ORIGINS`, and a `SocketIO` instance
  sharing the same CORS origins with `max_http_buffer_size` raised to
  100 MB to accommodate media uploads.
- There are **no Flask blueprints** for the admin feature areas — only
  `application/admin/auth/routes.py` registers plain `@app.route` HTTP
  routes (login, session check, and the JWT-protected export/import/demo
  endpoints), wired via `register_auth_routes(app, db)`. Everything else
  under `application/admin/*` is Socket.IO handlers, not HTTP.
- On startup (inside `app.app_context()`), the app resets stale
  `Device.is_online` flags, enforces exactly one default template, prunes
  old screen logs, and bootstraps an admin user if none exists.
- `register_all_handlers(socketio, app, db)`
  ([`application/socketio_handlers/__init__.py`](https://github.com/DisplayHive/DisplayHive/blob/main/application/socketio_handlers/__init__.py))
  is the central registry: it imports and calls each feature's
  `register_*` function, both from `application/socketio_handlers/*.py` and
  from each `application/admin/<feature>/sockethandlers.py`.
- In production, schema migrations are applied by running
  `alembic upgrade head` as a deploy step (see
  [`nix/module.nix`](https://github.com/DisplayHive/DisplayHive/blob/main/nix/module.nix)).
  `db.create_all()` in `app.py` only runs for local SQLite as a dev
  convenience and is a no-op once tables exist.

## Data model

Defined under `application/models/`:

- **`content.py`** — `ContentElement` (a placed content item; FK to
  `Contenttype`, `ContentContainer`, and many-to-many with `Screengroup`),
  `Template` (a page's HTML/CSS, with an `isDefault` flag), `ContentContainer`
  (a named region within a template), `Contenttype` (a reusable
  HTML/CSS + field schema), `TagConfig` (one field definition on a
  `Contenttype`), `MagicTag`, `SystemSetting`, Telegram alerting models
  (`AlertSubscription`, `TelegramUser`), `Media`, and the Pretalx models
  (`PretalxApiUrl`, `PretalxApiCache`, `PretalxSettings`).
- **`device.py`** — `Device` (a physical/browser player: `devicekey`,
  `is_online`, FK to `Screen`).
- **`screen.py`** — `Screen` (a logical display slot, FK to `Template`),
  `ScreenLog`, `Screengroup`.
- **`user.py`** — `AdminUser`.
- **`base.py`** — the `Screen` ↔ `Screengroup` and `ContentElement` ↔
  `Screengroup` many-to-many association tables.

## Admin feature areas (`application/admin/*`)

Each subfolder is a self-contained Socket.IO handler package for one admin
panel feature, using a `displayhive:admin:<feature>:cts:*` (client-to-server)
/ `:stc:*` (server-to-client) event naming convention:

| Folder | Responsibility |
|---|---|
| `alerting` | Telegram bot token, discovered chat users, per-user alert-type subscriptions, test sends |
| `auth` | HTTP-only: login, session check, JWT issuing |
| `content` | Query + mutation handlers for `ContentElement` (create/update/move/delete); mutations trigger a content push |
| `contenttypes` | CRUD for `Contenttype` |
| `devices` | Connection/adoption handshake (`connection.py`) and management: list, ping, update, assign to screen, find, delete (`management.py`) |
| `importexport` | Full DB + media export/import as a zip, mirrored by an HTTP route for the actual file transfer |
| `magictags` | CRUD for `MagicTag` |
| `matrix` | No handlers of its own — the Matrix page calls the same `screens`/`screengroups` mutations directly |
| `media` | Media library CRUD, folders, uploads |
| `pretalx` | Pretalx URL/settings/room config, cache; triggers a content push when data refreshes |
| `screengroups` | CRUD for `Screengroup` plus screen/content membership |
| `screens` | Create/delete/rename `Screen`, toggle monitoring/debug, reset size |
| `settings` | Default template, instance-wide `SystemSetting`s |
| `templates` | CRUD for `Template` |
| `users` | CRUD + activate/deactivate for `AdminUser` |

## Socket.IO handlers (`application/socketio_handlers/*.py`)

These handle the device/screen side of the realtime connection rather than
admin panel features:

- **`lifecycle.py`** — `disconnect` handling; broadcasts device-list updates
  to the `admins` room.
- **`content.py`** — legacy/basic screen-facing content and playlist
  queries, debug-mode and logger-state emits.
- **`devconfig.py`** — emits `upd_deviceconfig` to a device/room.
- **`logger.py`** — remote log streaming (subscribe/unsubscribe/get
  history/log entry).
- **`screens.py`** — reload one or all screens, fetch a screen's groups,
  rename a screen; emits a `RELOAD` command and triggers a content push.
- **`refresh_content.py`** — server time sync, and
  `displayhive:screen:cts:refresh_content`, used by content items flagged
  `update_after_show` (e.g. randomized images, Pretalx tables) to re-render
  themselves after being shown; throttled and scoped to the requesting
  device's own screen.
- **`upd_content.py`** — not an event handler itself, but the shared
  `send_upd_content(...)` helper every mutation calls to push a fresh
  payload to affected screens. See
  [Real-time content push](realtime-push.md) for the full trace.

## Frontends

**Admin panel** (`frontends/admin/src`) — Vue 3 SPA:

- `stores/` — one Pinia store per domain (`auth`, `content`, `devices`,
  `magicTags`, `media`, `screengroups`, `screens`, `settings`, `templates`).
  Stores emit `displayhive:admin:...:cts:*` events and listen for the
  matching `:stc:*` responses.
- `composables/useSocket.ts` — a singleton `socket.io-client` wrapper that
  queues listeners/emits until the connection is established.
- `views/`, `components/`, `router/`, `types/`, `utils/`.

**Screen client** (`frontends/screen/ts/screen`) — vanilla TypeScript, no
framework:

- `socket-connection.ts` — builds connection options from the device key /
  adoption key and opens the `io()` connection.
- `socket-handlers.ts` — every `socket.on(...)` listener, including
  `upd_content`.
- `content-display.ts` / `container-manager.ts` — render playlists and HTML
  into template containers.
- `adopt.ts` — the device adoption flow (QR code / token).
- `clock.ts`, `storage.ts`, `debug-panel.ts`, `viewport-tracker.ts`,
  `preload-iframes.ts` — supporting concerns.

## Migrations

Schema changes are managed with Alembic. Version files live in
`migrations/versions/`, named `<12-hex-revision>_<snake_case description>.py`
(e.g. `f3b4c5d6e7f8_initial_schema.py`). Generate a new one the usual Alembic
way and apply it with `alembic upgrade head`.
