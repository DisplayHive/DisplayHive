# Project structure

A map of the repository: where things live and where a new file belongs.

## Top level

| Path | Contents |
| --- | --- |
| `app.py` | Entry point (`create_app` from `application/core/factory.py`). |
| `application/` | The Python backend (Flask + Socket.IO + SQLAlchemy). |
| `frontends/admin/` | Admin SPA (Vue 3, TypeScript, Vite). |
| `frontends/screen/` | Screen client shown on the displays. |
| `migrations/`, `alembic.ini` | Alembic database migrations. |
| `tests/` | Backend unit and integration tests (pytest). |
| `e2e/` | End-to-end tests (Playwright; specs in `e2e/specs/`); builds the admin itself. |
| `docs/`, `mkdocs.yml` | This documentation (`user/` and `developer/`). |
| `nix/`, `flake.nix`, `shell.nix` | Nix package, NixOS module and dev shell. |
| `Dockerfile`, `compose.yml` | Container image and compose setup (kept at the root: `docker build .` / `docker compose up`). |
| `deploy/` | Files the image and the NixOS module run: `docker-entrypoint.sh`, `gunicorn-logging.json`. |
| `requirements/` | Python dependencies: the `.in` inputs and the generated, hashed locks (`npm run deps:lock`). |
| `.github/` | CI workflows, `CONTRIBUTING.md`, `SECURITY.md`. |
| `examplecontent/` | Demo Mode example content package. |
| `scripts/` | Maintenance helpers (hashes, lock files). |
| `notes/` | Local notes (roadmap, technical debt). |

## Backend (`application/`)

- `admin/<domain>/` — one folder per admin domain (`content`, `devices`,
  `screens`, `layouts`, `designs`, `users`, …). Typical files:
  `sockethandlers.py` (the Socket.IO actions), `helper.py` (domain logic),
  plus `queries.py` / `serializers.py` where a domain grows large. A large
  `helper.py` is split by job, as in `importexport/` (`exporter.py`,
  `importer.py`, `common.py`, `service.py`, `registry.py`). Handlers
  go through `socketio_handlers/actions.py` (see
  [Architecture](architecture.md)).
- `models/` — SQLAlchemy models, split by area (`content`, `screen`,
  `device`, `user`, `rights`, `help`).
- `socketio_handlers/` — handlers for the screen/device side and the shared
  action wrapper.
- `web/` — plain HTTP routes (admin SPA, health, static files, import/export,
  screen page).
- `utils/` — small shared helpers.
- `core/` — configuration and start-up: `config`, `paths`, `db_url`,
  `startup`, `factory`, `logfmt`, `version`, `migration`, `dbcopy`, `backup`.
- `security/` — `auth`, `oidc`, `permissions`, `session`,
  `security_headers`, `net`.
- `cli.py` — the `flask dh …` commands. Domain helpers sit with their
  domain: `admin/media/renditions.py`, `admin/icons/libraries.py`,
  `admin/help/content.py`, `admin/screens/logs.py`, `utils/aspect_ratio.py`.

## Admin frontend (`frontends/admin/src/`)

- `views/` — one component per route (page).
- `components/` — reusable pieces; feature folders (`contentEdit/`,
  `designs/`, `layout/`, `fields/`, `media/`, `devices/`, `screengroups/`, `contenttypes/`,
  `pretalx/`, `settings/`, `users/`, `dashboard/`) hold
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

## Splitting a large view

A view over roughly 500 lines gets its self-contained parts (a dialog with
its own state and styles, a card) moved into a feature folder under
`components/`, as done for the Media page (`components/media/`:
`MediaEditDialog.vue`, `MediaUploadDialog.vue`; the view keeps filtering and
the grid), Devices (`devices/`: adopt, rename, assign), Screen Groups
(`screengroups/`: edit, screens, content), Content Types (`contenttypes/`:
the edit dialog), Pretalx (`pretalx/`: URL dialogs, cache viewer, the two
settings cards) and the Dashboard (`dashboard/DashboardCommunity.vue`).
A dialog owns its state and takes `v-model:visible` plus the
data it needs as props; CSS used by both the view and the part lives in a
plain `.css` file pulled in with `<style scoped src="…">`. `data-tour`
attributes stay on the same elements, so tours keep working.
