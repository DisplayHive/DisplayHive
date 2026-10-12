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
  `importer.py` with `payload.py` and `rows.py`, `common.py`, `service.py`,
  `registry.py`) and `content/` (`helper.py` for rendering, `scene.py` for
  composing a layout's containers). Handlers
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
- `cli/` — the `flask dh …` commands, one module per topic (`users`, `media`,
  `database`, `check`) on the shared group in `group.py`. Domain helpers sit with their
  domain: `admin/media/renditions.py`, `admin/icons/libraries.py`,
  `admin/help/content.py`, `admin/screens/logs.py`, `utils/aspect_ratio.py`.

## Admin frontend (`frontends/admin/src/`)

- `views/` — one component per route (page). A view keeps the page's
  filtering, table and wiring; self-contained parts live in `components/`.
- `components/` — grouped by what a component belongs to:
  - `ui/` — generic building blocks (`DialogTitle`, `DialogFooter`,
    `PageActions`, `PageHeader`, `RouteLink`, `ColorPicker`, …),
  - `app/` — the app shell (`AppHeader`, `AppBanners`, `CommandPalette`, …),
  - one folder per feature (`media/`, `devices/`, `screens/`, `screengroups/`,
    `contenttypes/`, `pretalx/`, `importexport/`, `settings/`, `users/`,
    `dashboard/`, `designs/`, `layout/`, `content/`, `contentEdit/`).
    Field handlers live in `fields/` with the registry in `fields/registry.ts`.
- `composables/` — shared stateful logic (`useXxx.ts`), grouped in folders
  per feature; a page's socket state can live here too (`useAlerting.ts`).
- `stores/` — Pinia stores.
- `utils/` — pure helpers, grouped by topic (`content/`, `design/`,
  `layout/`, `media/`); unit tests in `utils/__tests__/`.
- `router/`, `types/` — routing and shared types.
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
`components/`: Media (`media/`: edit and upload dialog), Devices (`devices/`),
Screens (`screens/`), Screen Groups (`screengroups/`), Content Types
(`contenttypes/`), Pretalx (`pretalx/`), Im-/Export (`importexport/`),
Settings (`settings/`) and the Dashboard (`dashboard/DashboardCommunity.vue`).
Page state that is mostly socket plumbing moves into a composable instead
(Alerting: `composables/useAlerting.ts`).

A dialog owns its state and takes `v-model:visible` plus the data it needs as
props; it fills itself when it opens (a `watch` on `visible`). A card that
shows server settings takes them as a prop and copies them into its own
form state. CSS used by both the view and a part lives in a plain `.css`
file pulled in with `<style scoped src="…">`. `data-tour` attributes stay on
the same elements, so tours keep working.
