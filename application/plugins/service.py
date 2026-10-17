"""What the Plugins page, the ``flask dh plugins`` commands and the tests do with plugins.

One place for "install this", "switch that off", "show me all" — each returns plain data or raises
``PluginError`` with a text that can be shown to the administrator.
"""

import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

from application.core import version as app_version
from application.plugins import installer, loader
from application.plugins.manifest import PluginError
from application.plugins.registry import registry

logger = logging.getLogger(__name__)


def installed_dir(app) -> Path:
    return Path(app.config['PLUGINS_FOLDER'])


def host_version() -> str:
    return app_version.release()


def describe(db, app) -> dict:
    """The state the Plugins page shows: every plugin on disk, and how many unloaded versions still sit in memory."""
    found = loader.discover(installed_dir(app))
    states = loader._states(db) or {}
    loaded = registry.loaded()
    plugins = []
    for plugin_id, (manifest, source) in sorted(found.items()):
        row = states.get(plugin_id)
        enabled = loader.wanted(manifest, row, set()) if row is None else bool(row.enabled)
        plugins.append({
            'id': plugin_id, 'name': manifest.name, 'kind': manifest.kind, 'version': manifest.version,
            'description': manifest.description, 'author': manifest.author, 'license': manifest.license,
            'homepage': manifest.homepage, 'source': source, 'enabled': enabled,
            'loaded': plugin_id in loaded, 'preinstalled': manifest.preinstalled,
            'fieldhandlers': list(manifest.fieldhandlers), 'removable': source == 'installed',
            'has_admin': bool(manifest.admin), 'has_screen': bool(manifest.screen),
            'requires_host': manifest.requires_host,
            'compatible': _compatible(manifest),
        })
    return {'plugins': plugins, 'retired': len(registry.retired()), 'host_version': host_version()}


def _compatible(manifest) -> bool:
    from application.plugins.manifest import PLUGIN_API, host_accepts
    try:
        return manifest.plugin_api == PLUGIN_API and host_accepts(manifest.requires_host, host_version())
    except PluginError:
        return False


def public_list(app) -> list:
    """What the admin and the screens need to load a plugin's frontend: the plugins that are active now."""
    out = []
    for plugin_id, info in sorted(registry.loaded().items()):
        out.append({
            'id': plugin_id, 'version': info.get('version', ''), 'name': info.get('name', ''),
            'kind': info.get('kind', ''), 'fieldhandlers': info.get('fieldhandlers', []),
            'admin': info.get('admin', ''), 'screen': info.get('screen', ''),
            'source': 'bundled' if not str(info.get('directory', '')).startswith(str(installed_dir(app))) else 'installed',
        })
    return out


def set_enabled(db, app, plugin_id: str, enabled: bool) -> list:
    problems = loader.set_enabled(db, plugin_id, enabled, installed_dir(app), host_version())
    mine = [p for p in problems if plugin_id in p]
    if enabled and mine:
        raise PluginError(mine[0])
    return problems


def _register(db, app, manifest) -> list:
    """Record a freshly installed plugin and make the running server match it."""
    from application.models import Plugin
    row = db.session.get(Plugin, manifest.id)
    if row is None:
        # An installed plugin is switched on by the person who installed it, unless it replaces one that was off.
        db.session.add(Plugin(id=manifest.id, version=manifest.version, source='installed', enabled=True))
    else:
        row.version, row.source = manifest.version, 'installed'
    db.session.commit()
    return loader.reconcile(db, installed_dir(app), host_version(), write=True)


def install_zip(db, app, data: bytes, **kwargs):
    manifest = installer.install_zip(data, installed_dir(app), host_version=host_version(), **kwargs)
    problems = _register(db, app, manifest)
    mine = [p for p in problems if manifest.id in p]
    if mine:
        raise PluginError(mine[0])
    return manifest


def install_url(db, app, url: str, sha256: str, expected_id: str = ''):
    manifest = installer.install_url(url, installed_dir(app), sha256=sha256, host_version=host_version(), expected_id=expected_id)
    problems = _register(db, app, manifest)
    mine = [p for p in problems if manifest.id in p]
    if mine:
        raise PluginError(mine[0])
    return manifest


def remove(db, app, plugin_id: str) -> None:
    """Remove an installed plugin: its code is unloaded and its files deleted; its data (tables) is kept."""
    from application.models import Plugin
    installer.remove(installed_dir(app), plugin_id)
    row = db.session.get(Plugin, plugin_id)
    still_bundled = plugin_id in loader.discover(installed_dir(app))
    if row is not None and not still_bundled:
        db.session.delete(row)
        db.session.commit()
    loader.reconcile(db, installed_dir(app), host_version(), write=True)


# --- Restart ------------------------------------------------------------------------------------

def _under_gunicorn() -> bool:
    return 'gunicorn' in os.environ.get('SERVER_SOFTWARE', '').lower() or 'gunicorn' in os.path.basename(sys.argv[0])


def _restart_method() -> str:
    if _under_gunicorn():
        return 'gunicorn'
    if sys.argv and sys.argv[0].endswith('app.py'):
        return 'exec'
    return ''


def can_restart() -> bool:
    return bool(_restart_method())


def restart_later(app, delay: float = 1.0) -> str:
    """Restart the server process in *delay* seconds (so the answer reaches the caller first).

    Under gunicorn the worker ends itself gracefully and the master starts a fresh one (the data-directory
    lock goes with the old process). A server started as ``python app.py`` replaces itself in place. Returns
    how it will be done; anything else — we do not know how the process is supervised — is refused.
    """
    how = _restart_method()
    if not how:
        raise PluginError('This server cannot restart itself; restart the service instead.')

    def go():
        time.sleep(delay)
        logger.warning('Restarting the server on request (%s)', how)
        if how == 'gunicorn':
            os.kill(os.getpid(), signal.SIGTERM)
        else:
            from application.core import worker_guard
            worker_guard.release(app.config['DATA_DIR'])
            os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=go, name='plugin-restart', daemon=True).start()
    return how
