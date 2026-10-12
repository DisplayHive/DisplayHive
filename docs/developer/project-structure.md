# Project structure

A map of the repository: where things live and where a new file belongs.

## Top level

| Path | Contents |
| --- | --- |
| `app.py` | Entry point (`create_app` from `application/factory.py`). |
| `application/` | The Python backend (Flask + Socket.IO + SQLAlchemy). |
| `frontends/admin/` | Admin SPA (Vue 3, TypeScript, Vite). |
| `frontends/screen/` | Screen client shown on the displays. |
| `migrations/`, `alembic.ini` | Alembic database migrations. |
| `tests/` | Backend unit and integration tests (pytest). |
| `testing/` | End-to-end tests (Playwright); builds the admin itself. |
| `docs/`, `mkdocs.yml` | This documentation (`user/` and `developer/`). |
| `nix/`, `flake.nix`, `shell.nix` | Nix package, NixOS module and dev shell. |
| `Dockerfile`, `compose.yml`, `docker-entrypoint.sh` | Container deployment. |
| `examplecontent/` | Demo Mode example content package. |
| `scripts/` | Maintenance helpers (hashes, lock files). |
| `notes/` | Local notes (roadmap, technical debt). |

## Backend (`application/`)

- `admin/<domain>/` — one folder per admin domain (`content`, `devices`,
  `screens`, `layouts`, `designs`, `users`, …). Typical files:
  `sockethandlers.py` (the Socket.IO actions), `helper.py` (domain logic),
  plus `queries.py` / `serializers.py` where a domain grows large. Handlers
  go through `socketio_handlers/actions.py` (see
  [Architecture](architecture.md)).
- `models/` — SQLAlchemy models, split by area (`content`, `screen`,
  `device`, `user`, `rights`, `help`).
- `socketio_handlers/` — handlers for the screen/device side and the shared
  action wrapper.
- `web/` — plain HTTP routes (admin SPA, health, static files, import/export,
  screen page).
- `utils/` — small shared helpers.
- Top-level modules — configuration and start-up (`config`, `paths`,
  `startup`, `factory`, `db_url`, `migration`, `backup`, `dbcopy`, `cli`),
  security (`auth`, `oidc`, `permissions`, `session`, `security_headers`,
  `net`) and a few domain helpers (`aspect_ratio`, `media_renditions`,
  `icon_libraries`, `screen_logs`).

## Admin frontend (`frontends/admin/src/`)

- `views/` — one component per route (page).
- `components/` — reusable pieces; feature folders (`contentEdit/`,
  `designs/`, `layout/`, `fields/`, `settings/`, `users/`, `dashboard/`) hold
  what belongs to one feature. Field handlers live in `components/fields/`
  with the registry in `fields/registry.ts`.
- `composables/` — shared stateful logic (`useXxx.ts`), grouped in folders
  per feature.
- `stores/` — Pinia stores.
- `router/`, `types/`, `utils/` — routing, shared types, pure helpers.
- `tour/` — the guided tour system (see `CLAUDE.md`).

## Backend tests (`tests/`)

Tests are grouped by area; the folder says which part of the backend a test
covers, and a test sits in the folder of the module it exercises.

| Folder | Covers |
| --- | --- |
| `tests/core/` | Config, paths, start-up, factory, migrations, backup, CLI, logging, version, route table, dependency/Python version sync. |
| `tests/security/` | Authentication, OIDC, permissions, session cookie, security headers, network/outbound policy. |
| `tests/admin/` | Admin domain logic and actions: content, designs, layouts, devices, presence, import/export. |
| `tests/media/` | Media upload and renditions, aspect ratios, icon libraries. |
| `tests/screen/` | Screen page, template and screen logs. |

Shared fixtures are in `tests/conftest.py`. A test that needs a helper or
fixture from another test module imports it by its full path, e.g.
`from tests.admin.test_admin_actions import superadmin_client`. Tests that
read repository files compute the root relative to their folder
(`Path(__file__).resolve().parents[2]`).
