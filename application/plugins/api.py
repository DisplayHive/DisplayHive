"""The object a plugin's ``register(api)`` receives: the only way a plugin reaches the host.

Everything a plugin adds goes through ``api``, so the host can take it all back when the plugin is
disabled or removed.
"""

from application.plugins.handlers import FieldHandler
from application.plugins.manifest import Manifest
from application.plugins.registry import PluginRegistry


class _FieldHandlers:
    def __init__(self, api: 'PluginApi'):
        self._api = api

    def add(self, handler: FieldHandler) -> None:
        """Offer *handler*; its id must be one the manifest declares under ``provides.fieldhandlers``."""
        api = self._api
        if handler.id not in api.manifest.fieldhandlers:
            raise ValueError(
                f'{api.plugin_id} registers the field handler "{handler.id}", which plugin.json does not declare'
            )
        api._registry.add_fieldhandler(api.plugin_id, handler)


class _Routes:
    def __init__(self, api: 'PluginApi'):
        self._api = api

    def add(self, subpath: str, view, methods=('GET',)) -> None:
        """Serve ``/api/plugins/<plugin id>/<subpath>``. *view* is called with the Flask request context and
        returns what a Flask view returns. The caller is not authenticated: use ``require_right`` inside."""
        self._api._registry.add_route(self._api.plugin_id, subpath, methods, view)


class _Events:
    def __init__(self, api: 'PluginApi'):
        self._api = api

    def on(self, name: str, handler=None):
        """Handle the admin Socket.IO event ``displayhive:plugin:<plugin id>:<name>``. *handler*
        receives ``(data)`` and returns the acknowledgement; it runs as an admin action (see below).
        Usable as a decorator."""
        def add(fn):
            self._api._registry.add_event(self._api.plugin_id, name, fn)
            return fn
        return add(handler) if handler is not None else add


class _Data:
    def __init__(self, api: 'PluginApi'):
        self._api = api

    def add(self, section) -> None:
        """Offer a section of the plugin's own data to export and import."""
        if not section.id.startswith(self._api.plugin_id):
            raise ValueError(f'The data section id must start with "{self._api.plugin_id}"')
        self._api._registry.add_section(self._api.plugin_id, section)


class _Models:
    def __init__(self, api: 'PluginApi'):
        self._api = api

    def once(self, build):
        """The plugin's SQLAlchemy models; ``build(db)`` runs the first time only (see application/plugins/orm.py)."""
        from application.plugins import orm
        return orm.once(self._api.plugin_id, build)


class PluginApi:
    def __init__(self, manifest: Manifest, registry: PluginRegistry):
        self.manifest = manifest
        self.plugin_id = manifest.id
        self._registry = registry
        self.fieldhandlers = _FieldHandlers(self)
        self.routes = _Routes(self)
        self.events = _Events(self)
        self.data = _Data(self)
        self.models = _Models(self)

    @property
    def app(self):
        """The Flask app (``None`` while it is still being built; use it from handlers, not from ``register``)."""
        from application.plugins import host
        return host.app()

    @property
    def db(self):
        from application.plugins import host
        return host.db()

    def require(self, right: str) -> None:
        """In an event handler: refuse the caller unless they have *right* (a right the plugin declared or a host one)."""
        from application.plugins import host
        host.require(right)

    def emit_admins(self, event: str, payload=None) -> None:
        """Push *event* to every connected admin; use names like ``displayhive:plugin:<id>:stc:<what>``."""
        from application.plugins import host
        host.emit_admins(event, payload)

    def on_unload(self, hook) -> None:
        """Call *hook()* when the plugin is switched off or removed (stop threads, close connections)."""
        self._registry.add_unload_hook(self.plugin_id, hook)
