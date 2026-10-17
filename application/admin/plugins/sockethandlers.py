"""Admin socket handlers for the Plugins page, and the one door through which plugins get their own events.

    displayhive:admin:cts:get_plugins        → {plugins: [...], retired, host_version, catalog_url}
    displayhive:admin:cts:set_plugin_enabled {id, enabled}
    displayhive:admin:cts:install_plugin_url {url, sha256}
    displayhive:admin:cts:install_plugin_catalog {id}
    displayhive:admin:cts:get_plugin_catalog → {entries}
    displayhive:admin:cts:remove_plugin      {id}
    displayhive:admin:cts:restart_server
    displayhive:plugin:call                  {plugin, event, data}   → whatever the plugin's handler answers

The state is pushed to every admin as ``displayhive:admin:stc:plugins`` whenever it changes, together with
the list of active plugins' frontends (``displayhive:admin:stc:active_plugins``) so open tabs load or drop
the plugin's pages and field editors without a reload.
"""

import logging

from application.plugins import host, loader, service
from application.plugins.manifest import PluginError
from application.plugins.registry import registry
from application.socketio_handlers.actions import Fail, admin_action, ok
from application.socketio_handlers.auth import fields

logger = logging.getLogger(__name__)


def catalog_url(app) -> str:
    return app.config.get('PLUGIN_CATALOG_URL', '') or ''


def refresh_content_of(socketio, app, db, handlers) -> None:
    """After a plugin was switched, updated or removed: render again what its field handlers produce and
    tell the screens and admin tabs. Content is stored rendered, so without this it would stay as it was."""
    from application.models import TagConfig
    from application.admin.importexport.service import broadcast_import_update
    handlers = [h for h in handlers if h]
    if handlers:
        ids = sorted({row for row in db.session.execute(
            db.select(TagConfig.contenttype_id).where(TagConfig.field_handler.in_(handlers))).scalars().all()})
        if ids:
            from application.cli.media import rerender_all
            try:
                rerender_all(db, ids, echo=lambda *a, **k: None)
            except Exception:
                logger.exception('Rendering the content of the plugin again failed')
    broadcast_import_update(socketio, app, db)


def register_admin_plugin_handlers(socketio, app, db):
    host.init(app, db, socketio)

    def state() -> dict:
        data = service.describe(db, app)
        data['catalog_url'] = catalog_url(app)
        data['can_restart'] = service.can_restart()
        return data

    def push() -> None:
        with app.app_context():
            socketio.emit('displayhive:admin:stc:plugins', state(), room='admins')
            socketio.emit('displayhive:admin:stc:active_plugins', {'plugins': service.public_list(app)}, room='admins')

    app.extensions['plugins_push'] = push

    def handlers_of(plugin_id: str) -> list:
        found = loader.discover(service.installed_dir(app)).get(plugin_id)
        return list(found[0].fieldhandlers) if found else []

    def changed(plugin_id: str, extra_handlers=()) -> None:
        push()
        refresh_content_of(socketio, app, db, handlers_of(plugin_id) + list(extra_handlers))

    @socketio.on('displayhive:admin:cts:get_plugins')
    @admin_action('plugins.page', 'plugins.manage')
    def get_plugins(data=None):
        return ok(**state())

    @socketio.on('displayhive:admin:cts:get_active_plugins')
    @admin_action()
    def get_active_plugins(data=None):
        return ok(plugins=service.public_list(app))

    @socketio.on('displayhive:admin:cts:set_plugin_enabled')
    @admin_action('plugins.manage')
    def set_plugin_enabled(data):
        plugin_id, enabled = fields(data, 'id', 'enabled')
        try:
            service.set_enabled(db, app, plugin_id, bool(enabled))
        except PluginError as problem:
            push()
            raise Fail(str(problem)) from None
        changed(plugin_id)
        return ok()

    @socketio.on('displayhive:admin:cts:get_plugin_catalog')
    @admin_action('plugins.manage')
    def get_plugin_catalog(data=None):
        try:
            from application.plugins import installer
            return ok(entries=installer.fetch_catalog(catalog_url(app)))
        except PluginError as problem:
            raise Fail(str(problem)) from None

    def installed(manifest):
        changed(manifest.id, manifest.fieldhandlers)
        return ok(id=manifest.id, version=manifest.version)

    @socketio.on('displayhive:admin:cts:install_plugin_url')
    @admin_action('plugins.manage')
    def install_plugin_url(data):
        url, sha256 = fields(data, 'url', 'sha256')
        if not isinstance(url, str) or not url.strip():
            raise Fail('Enter the download link.')
        try:
            return installed(service.install_url(db, app, url.strip(), sha256 or ''))
        except PluginError as problem:
            raise Fail(str(problem)) from None

    @socketio.on('displayhive:admin:cts:install_plugin_catalog')
    @admin_action('plugins.manage')
    def install_plugin_catalog(data):
        (plugin_id,) = fields(data, 'id')
        from application.plugins import installer
        try:
            entry = next((e for e in installer.fetch_catalog(catalog_url(app)) if e['id'] == plugin_id), None)
            if entry is None:
                raise Fail('This plugin is not in the catalog.')
            return installed(service.install_url(db, app, entry['url'], entry['sha256'], expected_id=plugin_id))
        except PluginError as problem:
            raise Fail(str(problem)) from None

    @socketio.on('displayhive:admin:cts:remove_plugin')
    @admin_action('plugins.manage')
    def remove_plugin(data):
        (plugin_id,) = fields(data, 'id')
        handlers = handlers_of(plugin_id)
        try:
            service.remove(db, app, plugin_id)
        except PluginError as problem:
            raise Fail(str(problem)) from None
        push()
        refresh_content_of(socketio, app, db, handlers)
        return ok()

    @socketio.on('displayhive:admin:cts:restart_server')
    @admin_action('plugins.manage')
    def restart_server(data=None):
        try:
            how = service.restart_later(app)
        except PluginError as problem:
            raise Fail(str(problem)) from None
        return ok(how=how)

    @socketio.on('displayhive:plugin:call')
    @admin_action()
    def plugin_call(data):
        plugin_id, event, payload = fields(data, 'plugin', 'event', 'data')
        handler = registry.event(plugin_id, event) if isinstance(plugin_id, str) and isinstance(event, str) else None
        if handler is None:
            raise Fail('This plugin is not active.')
        return handler(payload)
