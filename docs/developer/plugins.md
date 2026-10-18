# Plugins

DisplayHive's field handlers and integrations are plugins. A plugin is a folder with a manifest
(`plugin.json`) and up to three parts: Python code for the server, a module for the admin and a module
for the screens. Plugins are loaded **while the server runs** — switching one on or off, installing,
updating and removing take effect at once, without a restart.

This page is for people who write plugins or work on the plugin system. Administrators: see
[Plugins](../user/plugins.md).

## Kinds

| Kind | What it is |
|---|---|
| `fieldhandler` | Exactly one field handler: what a field of a content type can hold (`countdown`, `image`, …). |
| `integration` | Anything larger. May bring field handlers, pages, rights, its own tables and background work (Pretalx is one). |

Everything that ships with DisplayHive — all field handlers, one plugin each — lives in `plugins/`
(`plugins/displayhive.countdown/` …). Nothing of a handler stays in the core: not its rendering, not its
editor, not its screen code. Plugins **installed** by an administrator live in `DATA_DIR/plugins/<id>/`; an
installed plugin replaces a bundled one of the same id when its version is higher.

## The manifest

```json
{
  "id": "acme.weather",
  "name": "Weather",
  "kind": "integration",
  "version": "1.2.0",
  "plugin_api": 1,
  "requires_host": ">=1.0.0",
  "preinstalled": false,
  "description": "…", "author": "…", "license": "MIT", "homepage": "https://…",
  "provides": { "fieldhandlers": ["weather"] },
  "backend": "backend",
  "admin": "admin/index.js",
  "screen": "screen/index.js",
  "migrations": "migrations",
  "requires_python_packages": ["segno>=1.6"],
  "rights": [{ "id": "acme.weather.manage", "group": "weather", "label": "Manage the weather sources" }],
  "adopts_tables": []
}
```

* `id` is `provider.name`, lower case. Rights, table names, socket events and routes are all derived from it,
  which is what keeps two plugins from clashing.
* `plugin_api` is the version of the interface the host offers (currently **1**). A plugin built for another
  version is not loaded. `requires_host` is `>=x.y.z` (a release candidate counts as its release).
* `preinstalled` — switched on the first time the host sees the plugin. Otherwise a plugin starts **off**,
  unless something already needs it (a field using one of its handlers, rows in a table it `adopts_tables`).
* `rights` — every id starts with the plugin's id. They appear in the Groups & Rights page like the host's.
* `adopts_tables` — tables that older versions created in the core and that now belong to the plugin
  (Pretalx). Rows in them switch the plugin on when an instance is upgraded.
* `requires_python_packages` — Python packages the plugin imports that the server must have (`name` or `name>=1.2`; `>=`, `>`,
  `<=`, `<`, `==`). DisplayHive **never installs packages while it runs** (the Docker image has no pip, the NixOS package is read-only):
  a plugin may use what the server ships. The list is checked when the plugin is installed and loaded and shown on the
  Plugins page, so a missing package is named before anything is imported and the plugin cannot be switched on. A bundled
  plugin's packages must also be in `requirements/requirements.in` (a test checks it).
* The paths (`backend`, `admin`, `screen`, `migrations`) are relative to the plugin and may not leave it.

## Backend

`backend/__init__.py` has a function `register(api)`. Everything a plugin adds goes through `api`, so the host can
take it all back:

```python
from application.plugins.handlers import FieldHandler, RenderContext

class Weather(FieldHandler):
    id = 'weather'
    refresh_after_show = False        # True: the screen asks for a fresh render after each display (live data)
    depends_on = ()                   # 'design' and/or 'media': content is rendered again when the Design / the media library change

    def render(self, rc: RenderContext):
        city = rc.value                      # the field's value
        unit = rc.option('unit', 'C')        # <name>__unit of the flat key bag
        return Markup(...)                   # or None: leave the stored value as it is

    def default_values(self, packed: str) -> dict:
        return {'default': packed}           # a container's packed default → the flat key bag, key "default"

def register(api):
    api.fieldhandlers.add(Weather())         # the id must be declared in plugin.json
    api.routes.add('forecast', view)         # GET /api/plugins/acme.weather/forecast
    api.events.on('refresh', handler)        # socket event, see below
    api.data.add(MySection())                # a node in export / import
    api.help.add('page.weather', 'What this page does.')   # in-app help topic, served while the plugin is active
    api.on_unload(stop_my_thread)
    models = api.models.once(build)          # SQLAlchemy models, see "Tables"
```

* **Handlers** escape what they output. A handler returns `Markup` only for HTML it built itself. A field whose
  handler is not available (plugin off, not installed) renders **empty** — the stored value is kept and comes back
  when the plugin is active again. A handler that raises is logged and renders empty; it never breaks a scene.
* **Stored rendering.** Content is stored rendered (`ContentElement.html`). A handler whose output depends on more than the
  field's own values says so with `depends_on`: `'design'` (the icon handler resolves a palette colour when it renders) or
  `'media'` (a random image by tag puts the matching files into the HTML). When the active Design is saved or changed, or
  media are uploaded, tagged or deleted, the content that uses such a handler is rendered again and pushed to the screens
  (application/admin/content/rerender.py; bursts are coalesced into one run). After an import everything is rendered again.
* **Routes** live under `/api/plugins/<id>/<subpath>`. Flask accepts no new routes once the first request was
  served, so there is one dispatcher route for all plugins. A route is **not** authenticated by itself — check
  with `api.require(right)` or your own means.
* **Socket events** are called through the one admin event `displayhive:plugin:call` with
  `{plugin, event, data}`; the handler receives `data` and returns the acknowledgement
  (`application.socketio_handlers.actions`: `ok()`, `Fail`). Start a handler with `api.require('<right>')`.
  What a plugin pushes to the admins is `api.emit_admins('displayhive:plugin:<id>:stc:<name>', payload)`.
* `api.db`, `api.app` are for use inside handlers, not while `register` runs.
* A plugin runs **in the server's process with its rights**. There is no sandbox.

### Loading, and what "unload" means

Loading imports `backend/` under the module name `dh_plugin_<id>_<version>` and calls `register`. Unloading takes
back everything registered through `api`, runs the `on_unload` hooks and drops the plugin's modules. Python cannot
remove code from memory for real: what is still referenced stays until the next restart. The Plugins page counts
those retired versions and offers a restart. A new version loads next to the old one under its own module name.

A plugin that fails to load (an exception, a bad manifest, a handler it did not declare) is logged and skipped;
it never stops the others or the server, and leaves nothing behind.

### Tables

A plugin's tables are created by **its own migrations**: files `migrations/0001_name.py` with a function
`upgrade(connection)`, run in order when the plugin is switched on or updated; the number of the last one that ran
is kept in `plugin.schema_version`. Tables are named `plg_<plugin id with _>_…`. Tables are **kept** when a plugin
is switched off or removed.

SQLAlchemy cannot forget a mapped class, so models are not defined at module level but handed to
`api.models.once(build)`: `build(db)` runs the first time in a process and returns the classes; later loads get the
same ones (see `application/plugins/orm.py`). Alembic ignores `plg_*` tables and the adopted legacy ones
(`migrations/env.py`).

## Admin

The admin module is `plugins/<id>/admin/index.ts` (bundled) or a finished ES module `admin/index.js` (installed).
Its default export receives the host:

```ts
export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({
    id: 'weather', label: 'Weather', editor: Editor,            // Editor uses useFieldContext()
    defaults: (name) => ({ [name]: '', [`${name}__unit`]: 'C' }),
    blankDefault: () => '{"city":""}',                            // a container's packed default
    container: { unpack, pack },                                  // packed default <-> the editor's key bag
  })
  host.pages.add({ path: '/weather', name: 'weather', component: () => import('./View.vue'),
                   title: 'Weather', icon: 'pi pi-cloud', right: 'acme.weather.manage',
                   menu: { group: 'Integrations', label: 'Weather' } })
  host.tours.add(weatherTour)
}
```

The editor of a field is also the editor of a container's default content — `FieldValueEditor` works on a field
named `default`, and `container.unpack`/`pack` translate between the key bag and the one string
`ContentContainer.default_content` holds (for most handlers the string simply is the value). A field's values live
in one flat key bag: `<name>`, `<name>__<suffix>`.

* A plugin talks to its server side with `usePluginSocket('<id>')` (`call`, `rawCall`, `onPush`).
* Bundled plugins import from the host with `@/…` (the admin's `src/`) and share its Vue and PrimeVue. Installed
  plugins ship a finished module: they get `host.lib` (Vue, `useFieldContext`, `useSocket`, the basic field
  components) instead of bundling their own Vue.
* The admin gets the list of active plugins when it connects and again whenever it changes
  (`displayhive:admin:stc:active_plugins`); pages, field editors and tours appear and disappear without a reload.
* Installed plugins' files are served as `/api/plugins/<id>/assets/<version>/<path>` (only `admin/`, `screen/` and
  `assets/`; cached for good — the URL carries the version).

## Screen

`screen/index.ts` (or `index.js`) exports a default function that receives
`{ pluginId, getNow(), afterRender(cb), log() }`. `afterRender` is called for every container each time a scene has
been put on the screen, with `{ id, element, changed }`; the countdown plugin starts its ticker there, the icon and
image plugins swap their placeholders for the real thing. The list of plugins a screen loads is written into the
page (`<script type="application/json" id="dh-plugins">`), so a screen that is offline and shows its cached page
knows the same plugins it had; the service worker caches a plugin's screen module like the bundle.

## Lifecycle

| Step | What happens |
|---|---|
| Start | `reconcile`: every plugin found on disk gets a row in `plugin` the first time (`enabled` = preinstalled / in use / adopted data); every enabled plugin is migrated and loaded. |
| Switch on / off | The row changes; the plugin is loaded or unloaded; rights are synced; content that uses its handlers is rendered again and the screens reload; admins get the new state. |
| Install | ZIP upload, download link + SHA-256, or the catalog (`PLUGIN_CATALOG_URL`, a `catalog.json`). The archive is unpacked by hand (limits on size and count, no path outside the folder, no links), the manifest checked, then the plugin is switched on. |
| Update | Install a higher version over it: the old version is retired, the new one loaded. |
| Remove | Installed plugins only: unloaded, files deleted, row removed. **Bundled plugins can be switched off, not removed.** Data stays. |
| Restart | The Plugins page offers one (the worker ends itself and gunicorn starts a new one; `python app.py` replaces itself). |

Trust: there is **no signature**. A download needs a SHA-256 checksum (the catalog carries one per entry); it proves
the file is the one published, not that it is harmless.

Command line: `flask dh plugins list | enable | disable | install | remove`.

## Export and import

A plugin offers data with `api.data.add(section)` (`DataSection`: `items`, `export_rows`, `import_rows`, `clear`,
`existing_uuids`). The section is one more node in the export and import trees, ticked or not like the core
types; its rows go under `plugin_data` in the file. On import a block is applied only when its plugin is active
here. Rows carry a `uuid` so the same row is recognised on another instance.

## Rights, events and names

| What | Name |
|---|---|
| Rights | `<plugin id>.<name>`, declared in the manifest |
| Socket events | `displayhive:plugin:call` with `{plugin, event}`; pushes `displayhive:plugin:<id>:stc:<name>` |
| Routes | `/api/plugins/<id>/<subpath>` |
| Tables | `plg_<id>_…` (legacy tables listed in `adopts_tables` keep their names) |

## Tests

* `tests/core/test_plugins.py`, `tests/core/test_plugin_install.py` — manifest, registry, loading, installing,
  routes, events, rights, tables.
* `tests/admin/test_render_handlers.py` — the rendered HTML of every handler, byte for byte
  (`tests/admin/golden/render_handlers.json`; regenerate deliberately with `UPDATE_GOLDEN=1`). Write the golden case
  before changing how a handler renders.
* `frontends/admin/src/plugins/__tests__/` — the admin registry and the bundled plugins' container translations.

## Known limits

* Python dependencies of a plugin are not installed: a plugin may use what the host ships and declares what it needs
  (`requires_python_packages`). Shipping packages inside a plugin's ZIP is not supported; it will be looked at when a plugin
  from outside the repository needs it.
