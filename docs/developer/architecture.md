# Architecture

| Component | Stack | Purpose |
|---|---|---|
| Backend | Flask + Flask-SocketIO (threading mode, gunicorn `gthread`), SQLAlchemy, Alembic | REST/API + realtime hub, serves both frontends |
| Admin panel | Vue 3, PrimeVue, Pinia, Vite | Manage content, screens, devices, layouts/designs, settings |
| Screen client | TypeScript (no framework), Vite | Kiosk-facing display client, renders pushed content |

## Backend entrypoint

`app.py` is a thin entry point: it calls the application factory
`create_app()` ([`application/factory.py`](https://github.com/DisplayHive/DisplayHive/blob/main/application/factory.py))
and exposes the result as `app` / `socketio` — what `gunicorn app:app`,
`flask --app app …` and `python app.py` expect. The pieces:

| Module | Responsibility |
|---|---|
| `application/factory.py` | `create_app(overrides=None, *, startup=True)` builds a complete, independent app and returns `(app, socketio)`; `run_dev()` is the `python app.py` server. Importing it has no side effects. |
| `application/config.py` | Environment → configuration (CORS origins, pool options, proxy count, secret key, data paths) as small pure functions; `apply_config()` copies them onto the app. |
| `application/startup.py` | The one-time work of a real server: raise the open-files limit, run the startup steps, start the log-retention and rendition-backfill tasks. |
| `application/web/` | The HTTP surface outside Socket.IO and the admin API: `static_routes`, `screen_page`, `admin_spa` (Blueprints) and `importexport_routes` (`register_importexport_routes`, because its auth decorators take the app). |
| `application/admin/importexport/service.py` | The import/export/demo workflow itself (parse uploads, stage, extract media, wipe, broadcast) — no request handling, so it is unit-tested directly. |

`create_app(startup=False)` skips the startup work: that is what a
`flask dh …` maintenance command gets when it is loaded next to a live
instance (`app.py` detects the CLI), and what tests use to build their own
apps. Tests may call `create_app({...overrides}, startup=False)` for an
isolated app (`tests/test_factory.py`); `tests/conftest.py` still shares one
default app for the bulk of the suite.

The backend in detail:

- Flask-SocketIO runs in **threading** mode (`async_mode='threading'`):
  every Socket.IO event, HTTP request and background task runs in its own OS
  thread, WebSockets via `simple-websocket`, served by gunicorn's `gthread`
  worker — one process, many threads. There is no monkey-patching. Shared
  in-memory state is guarded by locks: the login rate limiter
  (`application/auth.py`, which also counts a login attempt *before* the
  password check so parallel guesses can't slip past it), pending SSO
  logins (`application/oidc.py`) and the connection registry
  (`registry_lock` in `application/socketio_handlers/lifecycle.py`). New
  module-level state shared between requests needs the same — and tests
  for it need real `threading.Thread`s.
- The Flask app is configured with the DB URI (`DATABASE_URL`, required:
  PostgreSQL, or an explicit `sqlite:///…` URL for development only — there is
  no fallback file, and the Docker image and NixOS module refuse SQLite
  (`application/db_url.py`)), CORS restricted to `/api/*`
  with an allowlist from `CORS_ALLOWED_ORIGINS`, and a `SocketIO` instance
  sharing the same CORS origins. `max_http_buffer_size` is 10 MB — room
  for large content payloads, not files: media uploads are a separate HTTP
  multipart route (`POST /admin/api/media/upload`,
  `application/admin/media/routes.py`) whose file part Werkzeug streams
  straight to a temp file in `DATA_DIR` (the app-wide `DataDirRequest`
  request class), which is then hard-linked into the media folder.
- There are no Flask blueprints for the *admin feature areas*.
  `application/admin/auth/routes.py` registers plain `@app.route` HTTP
  routes for login/session check, wired via `register_auth_routes(app, db)`.
  The JWT-protected export/import/demo endpoints (`/admin/export/tree`,
  `/admin/export/download`, `/admin/import/preview`, `/admin/import/confirm`,
  `/admin/demo/list`, `/admin/demo/import`) live in
  `application/web/importexport_routes.py` and call
  `application/admin/importexport/service.py`. Static files, the screen page
  and the admin SPA are Blueprints in `application/web/`. Everything else
  under `application/admin/*` is Socket.IO handlers, not HTTP.
  `tests/test_route_map.py` pins the whole HTTP route table, so moving
  routes between modules can't silently drop or rename one.
- On startup (`application/startup.py`, inside `app.app_context()`), the app resets stale
  `Device.is_online` flags, enforces exactly one default design, prunes old
  screen logs, seeds the built-in Superadmin group and right-definition
  catalog (`sync_right_definitions()`, see `application/permissions.py`),
  and bootstraps an admin user if none exists.
- `register_all_handlers(socketio, app, db)`
  ([`application/socketio_handlers/__init__.py`](https://github.com/DisplayHive/DisplayHive/blob/main/application/socketio_handlers/__init__.py))
  is the central registry: it imports and calls each feature's
  `register_*` function, both from `application/socketio_handlers/*.py` and
  from each `application/admin/<feature>/sockethandlers.py`.
- In production, schema migrations are applied by running
  `alembic upgrade head` as a deploy step (see
  [`nix/module.nix`](https://github.com/DisplayHive/DisplayHive/blob/main/nix/module.nix)).
  `db.create_all()` in the startup steps only runs for SQLite (development) as a dev
  convenience and is a no-op once tables exist.

## Data model

Defined under `application/models/`:

- **`content.py`** — `ContentElement` (a placed content item; FK to
  `Contenttype`, and many-to-many with `Screengroup`), `Design` (the
  instance-wide skin: backdrop, background effect, default color palette,
  an `isDefault` flag, plus HTML/CSS for anything not covered by the
  structured options), `Gradient` / `DesignGradient` (reusable named CSS
  gradients, ordered/stacked per `Design`), `DesignContainerStyle` /
  `DesignGlobalStyle` (per-container / all-container CSS property
  overrides, scoped to one `Design`), `Layout` (a named, reusable group of
  positioned containers — purely organizational, no "screen uses this
  layout" concept), `ContentContainer` (a screen-relative position/size,
  reusable across multiple `Layout`s, with an optional default field
  handler/content), `Contenttype` (bound to one `Layout`; a reusable field
  schema), `TagConfig` (one field definition on a `Contenttype`, targeting
  one container, with `default_value` and per-sub-setting `option_flags`
  for locking/hiding), `LayoutVariation` (a `Layout` at one non-base aspect
  ratio: its own member containers) and `ContainerPosition` (a container's
  position/size at one non-base ratio; 16:9 is the base and lives in
  `layout_container` / the container's own columns — see
  `application/aspect_ratio.py`; `Design.aspect_ratios` is the ratio list and
  `Screen.aspect_ratio` picks the best-matching variation in `upd_content`),
  `SystemSetting`,
  Telegram alerting models (`AlertSubscription`, `TelegramUser`), `Media`,
  and the Pretalx models (`PretalxApiUrl`, `PretalxApiCache`,
  `PretalxSettings`).
- **`device.py`** — `Device` (a physical/browser player: `devicekey`,
  `is_online`, FK to `Screen`).
- **`screen.py`** — `Screen` (a logical display slot — resolution,
  monitoring/debug flags; no per-screen design/layout override, every
  screen renders the same instance-wide `Design`), `ScreenLog`,
  `Screengroup`.
- **`user.py`** — `AdminUser`.
- **`rights.py`** — the rights system: `RightDefinition` (the right
  catalog, synced from `application/permissions.py`'s `RIGHTS` list on
  startup), `Group` (nestable via `parent_group_id`; `is_superadmin`
  grants everything), `GroupRight` (allow-only grants on a group),
  `UserGroup` (user↔group membership), `UserRight` (per-user allow/deny
  override; absence of a row means inherit from group membership). See
  `application/permissions.py` for the resolution algorithm.
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
| `contenttypes` | CRUD for `Contenttype` and its `TagConfig` fields |
| `designs` | CRUD for `Design`, `Gradient`, and per-container/global style overrides |
| `devices` | Connection/adoption handshake (`connection.py`) and management: list, ping, update, assign to screen, find, delete (`management.py`) |
| `importexport` | Selective DB + media export/import as a zip (type/item tree selection, uuid-based dependency closure, reset/merge import modes) — no Socket.IO handlers of its own; the file transfer and selection endpoints are plain routes in `application/web/importexport_routes.py`, the workflow is `application/admin/importexport/service.py` |
| `layouts` | CRUD for `Layout` and `ContentContainer` positioning/assignment |
| `matrix` | No handlers of its own — the Matrix page calls the same `screens`/`screengroups` mutations directly |
| `media` | Media library CRUD, folders, uploads |
| `pretalx` | Pretalx URL/settings/room config, cache; triggers a content push when data refreshes |
| `rights` | CRUD for `Group`/`GroupRight`, user↔group membership, per-user `UserRight` overrides |
| `screengroups` | CRUD for `Screengroup` plus screen/content membership |
| `screens` | Create/delete/rename `Screen`, toggle monitoring/debug, reset size |
| `settings` | Default design, instance-wide `SystemSetting`s |
| `users` | CRUD + activate/deactivate for `AdminUser` |

## Socket.IO handlers (`application/socketio_handlers/*.py`)

These handle the device/screen side of the realtime connection rather than
admin panel features:

- **`lifecycle.py`** — `disconnect` handling; broadcasts device-list updates
  to the `admins` room.
- **`content.py`** — legacy/basic screen-facing content and playlist
  queries, debug-mode and logger-state emits.
- **`devconfig.py`** — emits `upd_deviceconfig` to a device/room.
- **`logger.py`** — the screen log: receives a screen's lines (stored via
  `application/screen_logs.py`), live feed (subscribe/unsubscribe) and the filtered `query`.
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

### Writing an admin handler

Admin handlers (`application/admin/*/sockethandlers.py`) answer with an acknowledgement
`{'success': True, …}` or `{'success': False, 'error': '…'}`. Use the helpers in
`application/socketio_handlers/actions.py` instead of repeating the checks:

```python
@socketio.on('displayhive:admin:users:cts:delete_user')
@admin_action('users.delete')            # any of the listed rights; none = any valid admin
def handle_delete_user(data):
    user = get_or_fail(db, AdminUser, fields(data, 'id')[0], 'User')   # 'Missing id' / 'User not found'
    if total_users() <= 1:
        raise Fail('Cannot delete the last remaining admin user')      # rolls back, answers the error
    db.session.delete(user)
    db.session.commit()
    return ok()
```

- A socket that is not a valid admin gets no answer; an admin without the right gets
  `Permission denied`; an unexpected exception is logged, rolled back and answered with
  `Internal error` (never an empty answer).
- Send replies to the requester with `room=request.sid` — an emit without a room reaches **every**
  connected client, screens included.
- Don't call `fetch()` on the page right after a change the handler already broadcasts (see the
  styleguide's page-actions section).
- The page side is `useAck()` (`frontends/admin/src/composables/useAck.ts`): 
  `const ack = await request('displayhive:…', payload, { success: 'Saved', error: 'Save failed' })` sends the
  event, shows the success or error toast, and returns the answer — or `null` when it failed (the person
  has already been told). Don't write `try { emitWithAck … } catch { toast }` blocks by hand; pass
  `onError` when the problem belongs inside a dialog instead of a toast.
- Every handler answers `{success, …}`; the old `{ok, …}` format is gone.
- Older handlers still use `@require_right` (silent denial, `None` on error); convert them when
  you touch them.

## Frontends

**Admin panel** (`frontends/admin/src`) — Vue 3 SPA:

- `stores/` — one Pinia store per domain (`auth`, `content`, `devices`,
  `media`, `rights`, `screengroups`, `screens`, `settings`). Designs,
  layouts, and content types talk to their
  sockets directly from their views rather than through a dedicated store.
  Stores emit `displayhive:admin:...:cts:*` events and listen for the
  matching `:stc:*` responses.
- `composables/useSocket.ts` — a singleton `socket.io-client` wrapper that
  queues listeners/emits until the connection is established.
- `App.vue` is only the page frame. Its parts: `composables/useSessionLifecycle.ts` (session,
  connect, reload after an outage), `composables/useSecurityStatus.ts` (server version and
  configuration warnings), `composables/useAdminNavigation.ts` (the menu and the page titles — a
  new page is one line in each table there), `components/AppBanners.vue`, `AppHeader.vue`,
  `PageHeader.vue`, and the global CSS in `assets/shell/` (loaded in the order of `index.css`).
- Calling the server: `composables/useAck.ts` (see "Writing an admin handler") and
  `composables/useConfirmAction.ts` (the red delete confirmation); dialog headers are
  `components/DialogTitle.vue`.
- The Designs page: `views/DesignsView.vue` is the list and the dialog shell; the dialog's sections are
  `components/designs/Design*Panel.vue` (each in a collapsible `DesignPanel`, loading and saving its own
  data), the Gradient library is `composables/designs/useGradients.ts` + `GradientDialogs.vue`.
- The Layout editor: `components/LayoutCanvasEditor.vue` only composes; its state and behaviour are the
  composables in `composables/layoutEditor/` (core, snaplines, design preview, persistence, container
  actions, canvas pointer handling, ratio variations — assembled by `useLayoutEditor.ts`) and its screen
  parts the components in `components/layout/`, which get the editor by injection. The pure parts
  (snapping, the preview document, default-content shapes) are in `utils/layoutGeometry.ts`,
  `layoutPreviewDoc.ts` and `containerDefaultContent.ts`, with unit tests.
- Field editors: `components/FieldValueEditor.vue` picks the editor of a field's handler from
  `components/fields/registry.ts`; each handler is a component in `components/fields/` that gets its field
  (name, value bag, mode, lock/hide flags) through `useFieldContext()` and lays out its options with
  `FieldSlot`. A new handler is one component plus one line in the registry. The generic `fve-*` layout
  classes are `assets/field-editors.css`; the live previews of the date format and countdown are
  `utils/fieldPreviews.ts`.
- Users & Rights: `views/UsersView.vue` is only the tabs; what the tabs and dialogs share (gates, account
  list, rights data) is `composables/users/useUsersPage.ts`, the tabs and dialogs are `components/users/`.
- The content edit page: `views/ContentEditView.vue` composes `components/contentEdit/`; the form, saving,
  screen assignment and preview are `composables/contentEdit/` (`useContentEditor.ts` assembles them).
  Starting values per field handler: `utils/contentFieldDefaults.ts`.
- The Dashboard: `views/DashboardView.vue` holds the stat tiles; quick actions and the schedule panels
  (on air, ending/starting soon, recently changed) are `components/dashboard/DashboardOverview.vue`, judged
  in the browser by `utils/contentSchedule.ts` (the schedule is wall-clock text, read in the viewer's time
  zone like a screen does). `ContentElement.updated_at` feeds "recently changed".
- Ctrl+K: `components/CommandPalette.vue` (opened by `composables/useCommandPalette.ts`) lists pages, actions
  and the items of the stores; the matching is `utils/commandSearch.ts`. A new page shows up through
  `useAdminNavigation`; a new kind of item is one block in the palette's `entries`.
- Media in use: `application/admin/media/usage.py` scans content, presets, container defaults, designs and
  settings for a file's URL (and random-by-tag image fields); the media list carries it as `used_by`.
- Put anything a page shows in the header's action area into `components/PageHeaderSlot.vue` (or use
  `PageActions`); a plain `<Teleport to="#page-header-actions">` crashes the page on a reload.
- `views/`, `components/`, `router/`, `types/`, `utils/`.

**Screen client** (`frontends/screen/ts/screen`) — vanilla TypeScript, no
framework:

- `socket-connection.ts` — builds connection options from the device key /
  adoption key and opens the `io()` connection.
- `socket-handlers.ts` — every `socket.on(...)` listener, including
  `upd_content`.
- `content-display.ts` / `container-manager.ts` — render playlists and HTML
  into positioned containers.
- `adopt.ts` — the device adoption flow (QR code / token).
- `reconnect.ts` — how a screen comes back after losing the server: Socket.IO retries forever with a
  1 s → 30 s backoff (±25 % jitter, so many screens do not hit a restarting server together); a manual
  retry with the same timing covers what Socket.IO does not retry (server refused or closed the connection).
- `status-indicator.ts` — the dot in the corner that appears only when something is wrong: red `con`
  (connection), yellow `mim` (content/media missing) and `js` (script error); the codes also go to the
  screen log, and Settings can switch the dot off (`statusindicator` in `upd_deviceconfig`).
- `clock.ts`, `storage.ts`, `debug-panel.ts`, `viewport-tracker.ts`,
  `preload-iframes.ts` — supporting concerns.

## Migrations

Schema changes are managed with Alembic. Version files live in
`migrations/versions/`, named `<12-hex-revision>_<snake_case description>.py`
(e.g. `f3b4c5d6e7f8_initial_schema.py`). Generate a new one the usual Alembic
way and apply it with `alembic upgrade head`.
