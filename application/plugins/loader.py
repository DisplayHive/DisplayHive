"""Finding plugins, loading and unloading them while the server runs, and the on/off state in the database.

Where plugins live:

* ``plugins/<id>/``           bundled with the application (read-only, part of the image or checkout);
* ``DATA_DIR/plugins/<id>/``  installed by an administrator (later: from a catalog or a ZIP).

``reconcile()`` makes the registry match the database: every enabled plugin is loaded, every other one
unloaded. It runs at start (for every app, also the ones for `flask dh` commands and tests) and again
whenever a plugin is enabled, disabled, installed or removed — no restart involved. A plugin that fails
to load is logged and skipped; it never stops the others or the server.

Python cannot unload a module for real. Unloading takes back everything the plugin registered and drops
its modules from ``sys.modules``; code that is still referenced stays in memory until the next restart.
That is what ``registry.retired`` counts, so the administrator can be offered a restart.
"""

import importlib.util
import logging
import re
import sys
from pathlib import Path
from typing import Optional

from application.plugins.api import PluginApi
from application.plugins.manifest import (
    MANIFEST_NAME, PLUGIN_API, Manifest, PluginError, host_accepts, read_manifest,
)
from application.plugins.registry import registry

logger = logging.getLogger(__name__)

BUNDLED_DIR = Path(__file__).resolve().parents[2] / 'plugins'
MODULE_PREFIX = 'dh_plugin_'


def _module_name(manifest: Manifest) -> str:
    """A name unique per plugin *and version*, so a new version loads next to the old one."""
    return MODULE_PREFIX + re.sub(r'[^0-9a-zA-Z]+', '_', f'{manifest.id}_{manifest.version}')


# --- Finding plugins -------------------------------------------------------------------------

def _scan(directory: Path, source: str) -> dict:
    found = {}
    if not directory or not Path(directory).is_dir():
        return found
    for entry in sorted(Path(directory).iterdir()):
        if not (entry / MANIFEST_NAME).is_file():
            continue
        try:
            manifest = read_manifest(entry)
        except PluginError as problem:
            logger.warning('Ignoring the plugin in %s: %s', entry, problem)
            continue
        found[manifest.id] = (manifest, source)
    return found


def discover(installed_dir: Optional[Path] = None) -> dict:
    """``{plugin id: (manifest, source)}`` of everything on disk. An installed plugin replaces a bundled
    one of the same id when its version is higher."""
    found = _scan(BUNDLED_DIR, 'bundled')
    for plugin_id, (manifest, source) in _scan(installed_dir, 'installed').items():
        bundled = found.get(plugin_id)
        if bundled is None or _version_key(manifest.version) > _version_key(bundled[0].version):
            found[plugin_id] = (manifest, source)
    return found


def _version_key(version: str) -> tuple:
    m = re.match(r'^(\d+)\.(\d+)\.(\d+)', version or '')
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


# --- Loading and unloading ---------------------------------------------------------------------

def load(manifest: Manifest, host_version: str = '') -> None:
    """Import the plugin's backend and let it register. Raises ``PluginError`` and leaves nothing behind."""
    if manifest.plugin_api != PLUGIN_API:
        raise PluginError(f'{manifest.id} is built for plugin API {manifest.plugin_api}; this DisplayHive offers {PLUGIN_API}')
    if not host_accepts(manifest.requires_host, host_version):
        raise PluginError(f'{manifest.id} needs DisplayHive {manifest.requires_host} (this is {host_version})')
    if registry.is_loaded(manifest.id):
        return
    from application.plugins import packages
    lacking = packages.unmet(manifest.requires_python_packages)
    if lacking:
        raise PluginError(
            f'{manifest.id} needs the Python package(s) {", ".join(lacking)}. DisplayHive does not install packages '
            "while it runs: install the server's requirements again (requirements/requirements.txt) and restart."
        )
    registry.add_plugin(manifest.id, {
        'version': manifest.version, 'kind': manifest.kind, 'name': manifest.name,
        'fieldhandlers': list(manifest.fieldhandlers), 'rights': [dict(r) for r in manifest.rights],
        'admin': manifest.admin, 'screen': manifest.screen, 'directory': str(manifest.directory or ''),
    })
    try:
        if manifest.backend:
            module = _import_backend(manifest)
            register = getattr(module, 'register', None)
            if not callable(register):
                raise PluginError(f'{manifest.id}: the backend has no register(api) function')
            register(PluginApi(manifest, registry))
        missing = [h for h in manifest.fieldhandlers if registry.owner_of(h) != manifest.id]
        if missing:
            raise PluginError(f'{manifest.id} declares the field handler(s) {", ".join(missing)} but did not register them')
    except Exception as problem:
        unload(manifest.id, _retire=False)
        _forget_modules(manifest)
        if isinstance(problem, PluginError):
            raise
        if isinstance(problem, ModuleNotFoundError) and problem.name:
            raise PluginError(
                f'{manifest.id} needs the Python package "{problem.name}", which is not installed here. '
                'Install the server\'s requirements again (requirements/requirements.txt) and restart.'
            ) from problem
        raise PluginError(f'{manifest.id} failed to load: {problem}') from problem


def _import_backend(manifest: Manifest):
    package_dir = (manifest.directory / manifest.backend).resolve()
    init = package_dir / '__init__.py'
    if not init.is_file():
        raise PluginError(f'{manifest.id}: {manifest.backend}/__init__.py does not exist')
    if manifest.directory.resolve() not in package_dir.parents:
        raise PluginError(f'{manifest.id}: the backend folder is outside the plugin')
    name = _module_name(manifest)
    spec = importlib.util.spec_from_file_location(name, init, submodule_search_locations=[str(package_dir)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _forget_modules(manifest: Manifest) -> None:
    prefix = _module_name(manifest)
    for name in [n for n in sys.modules if n == prefix or n.startswith(prefix + '.')]:
        del sys.modules[name]


def unload(plugin_id: str, _retire: bool = True) -> None:
    """Take back everything *plugin_id* registered. Its code stays in memory until a restart."""
    info = registry.loaded().get(plugin_id)
    registry.remove_plugin(plugin_id)
    if info:
        prefix = MODULE_PREFIX + re.sub(r'[^0-9a-zA-Z]+', '_', f'{plugin_id}_{info.get("version", "")}')
        for name in [n for n in sys.modules if n == prefix or n.startswith(prefix + '.')]:
            del sys.modules[name]
        if _retire:
            registry.retire(plugin_id, info.get('version', ''))


# --- The plugin's own tables -------------------------------------------------------------------

_MIGRATION_FILE = re.compile(r'^(\d{4})_[a-z0-9_]+\.py$')


def pending_migrations(manifest: Manifest, applied: int) -> list:
    """``[(number, path)]`` of the plugin's migrations newer than *applied*, in order.

    A plugin's schema changes are files ``<migrations folder>/0001_name.py`` with a function
    ``upgrade(connection)``; tables are named ``plg_<plugin id>_…`` (dots and dashes become ``_``).
    The number of the last one that ran is kept in ``plugin.schema_version``.
    """
    if not manifest.migrations or manifest.directory is None:
        return []
    folder = (manifest.directory / manifest.migrations).resolve()
    if not folder.is_dir() or manifest.directory.resolve() not in folder.parents:
        return []
    found = []
    for entry in sorted(folder.iterdir()):
        m = _MIGRATION_FILE.match(entry.name)
        if m and int(m.group(1)) > applied:
            found.append((int(m.group(1)), entry))
    return found


def run_migrations(db, manifest: Manifest, row) -> None:
    """Bring the plugin's tables up to date. ``PluginError`` (and the database untouched by the failing
    step) if one fails."""
    for number, path in pending_migrations(manifest, row.schema_version or 0):
        spec = importlib.util.spec_from_file_location(f'{_module_name(manifest)}_migration_{number}', path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            module.upgrade(db.session.connection())
            row.schema_version = number
            db.session.commit()
        except Exception as problem:
            db.session.rollback()
            logger.exception('Migration %s of plugin %s failed', path.name, manifest.id)
            raise PluginError(f'{manifest.id}: the migration {path.name} failed: {problem}') from problem
        logger.info('Plugin %s: applied migration %s', manifest.id, path.name)


def _sync_rights(db) -> None:
    from application.security.permissions import sync_right_definitions
    try:
        sync_right_definitions(db)
    except Exception:
        db.session.rollback()
        logger.exception('Could not register the rights of the plugins')


# --- The state in the database ---------------------------------------------------------------

def _states(db) -> Optional[dict]:
    """``{plugin id: Plugin row}``, or ``None`` when the database has no plugin table (yet)."""
    from sqlalchemy.exc import SQLAlchemyError
    from application.models import Plugin
    try:
        return {row.id: row for row in db.session.execute(db.select(Plugin)).scalars().all()}
    except SQLAlchemyError:
        db.session.rollback()
        logger.debug('No plugin table; using the default set of plugins', exc_info=True)
        return None


def _handlers_in_use(db) -> set:
    """Field handler ids that content types or container defaults refer to."""
    from sqlalchemy.exc import SQLAlchemyError
    from application.models import ContentContainer, TagConfig
    try:
        used = set(db.session.execute(db.select(TagConfig.field_handler).distinct()).scalars().all())
        used |= set(db.session.execute(db.select(ContentContainer.default_field_handler).distinct()).scalars().all())
    except SQLAlchemyError:
        db.session.rollback()
        return set()
    return {h for h in used if h}


def _has_rows(db, tables: tuple) -> bool:
    """Whether any of *tables* exists and holds a row (older versions kept the data in the core)."""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import SQLAlchemyError
    try:
        existing = set(inspect(db.session.connection()).get_table_names())
        for name in tables:
            if name in existing and db.session.execute(text(f'SELECT 1 FROM "{name}" LIMIT 1')).first() is not None:
                return True
    except SQLAlchemyError:
        db.session.rollback()
    return False


def wanted(manifest: Manifest, row, in_use: set, db=None) -> bool:
    """Whether *manifest* should be active: what the row says, or for a plugin seen the first time, whether it
    ships switched on or something in the data already needs it (a field using its handler, rows in a table it
    adopts from an older version)."""
    if row is not None:
        return bool(row.enabled)
    if manifest.preinstalled or set(manifest.fieldhandlers) & in_use:
        return True
    return bool(db is not None and manifest.adopts_tables and _has_rows(db, manifest.adopts_tables))


def reconcile(db, installed_dir: Optional[Path] = None, host_version: str = '', write: bool = True) -> list:
    """Make the registry match the database; returns a list of problems (text) for display.

    With ``write`` a plugin seen for the first time gets its row (so a later change of the defaults never
    switches it on or off behind the administrator's back). Apps built for ``flask dh`` commands and tests
    pass ``write=False``: they load what the database says, or the defaults, and leave it alone.
    """
    problems = []
    found = discover(installed_dir)
    states = _states(db)
    in_use = _handlers_in_use(db) if states is not None else set()
    for plugin_id, (manifest, source) in sorted(found.items()):
        row = (states or {}).get(plugin_id)
        active = wanted(manifest, row, in_use, db if states is not None else None)
        if write and states is not None and row is None:
            from application.models import Plugin
            db.session.add(Plugin(id=plugin_id, version=manifest.version, source=source, enabled=active))
            db.session.commit()
        loaded = registry.loaded().get(plugin_id)
        if loaded and (not active or loaded.get('version') != manifest.version):
            unload(plugin_id)
            loaded = None
        if active:
            try:
                if write and states is not None:
                    from application.models import Plugin
                    current = db.session.get(Plugin, plugin_id)
                    if current is not None:
                        run_migrations(db, manifest, current)       # whatever is not applied yet, loaded or not
                if not loaded:
                    load(manifest, host_version)
                registry.clear_failure(plugin_id)
            except PluginError as problem:
                registry.set_failure(plugin_id, str(problem))
                logger.error('Plugin %s could not be loaded: %s', plugin_id, problem)
                problems.append(str(problem))
    for plugin_id in list(registry.loaded()):
        if plugin_id not in found:
            unload(plugin_id)
    for plugin_id, row in (states or {}).items():
        if row.enabled and plugin_id not in found:
            problems.append(f'{plugin_id} is switched on but its files are missing')
            logger.warning('Plugin %s is switched on but its files are missing', plugin_id)
    if write and states is not None:
        _sync_rights(db)
    return problems


def set_enabled(db, plugin_id: str, enabled: bool, installed_dir: Optional[Path] = None, host_version: str = '') -> list:
    """Switch a plugin on or off, effective at once. Returns the problems ``reconcile`` found."""
    from datetime import datetime, timezone
    from application.models import Plugin
    found = discover(installed_dir)
    if plugin_id not in found:
        raise PluginError(f'There is no plugin {plugin_id}')
    manifest, source = found[plugin_id]
    row = db.session.get(Plugin, plugin_id)
    if row is None:
        row = Plugin(id=plugin_id, version=manifest.version, source=source, enabled=enabled)
        db.session.add(row)
    row.enabled = enabled
    row.version = manifest.version
    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    problems = reconcile(db, installed_dir, host_version, write=True)
    return problems
