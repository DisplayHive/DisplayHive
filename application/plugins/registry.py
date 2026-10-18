"""The process-wide table of what the loaded plugins provide.

Plugins are loaded and unloaded while the server runs, from any request thread, so every change and
every look-up goes through one lock. Look-ups return the handler object itself; a handler that is
unregistered meanwhile finishes the render it is in.
"""

import logging
import threading
from typing import Optional

from application.plugins.handlers import FieldHandler

logger = logging.getLogger(__name__)


class PluginRegistry:
    def __init__(self):
        self._lock = threading.RLock()
        self._handlers: dict[str, tuple[str, FieldHandler]] = {}      # handler id -> (plugin id, handler)
        self._plugins: dict[str, dict] = {}                           # plugin id -> info about what is loaded
        self._routes: dict[tuple, tuple] = {}                         # (plugin id, subpath) -> (methods, view function)
        self._events: dict[tuple, object] = {}                        # (plugin id, event name) -> handler
        self._hooks: dict[str, list] = {}                             # plugin id -> functions to call on unload
        self._sections: dict[str, tuple] = {}                         # data section id -> (plugin id, DataSection)
        self._failures: dict[str, str] = {}                            # plugin id -> why it could not be loaded
        self._help: dict[str, tuple] = {}                              # help topic key -> (plugin id, topic dict)
        self._warned: set = set()
        self._retired: list = []                                      # (plugin id, version) unloaded, code still in memory

    # --- Changes ---------------------------------------------------------------------------

    def add_plugin(self, plugin_id: str, info: dict) -> None:
        with self._lock:
            self._plugins[plugin_id] = dict(info)

    def add_fieldhandler(self, plugin_id: str, handler: FieldHandler) -> None:
        if not isinstance(handler, FieldHandler) or not handler.id:
            raise ValueError('A field handler must be a FieldHandler with an id')
        with self._lock:
            taken = self._handlers.get(handler.id)
            if taken is not None and taken[0] != plugin_id:
                raise ValueError(f'The field handler "{handler.id}" already belongs to {taken[0]}')
            self._handlers[handler.id] = (plugin_id, handler)
            self._warned.discard(handler.id)

    def add_route(self, plugin_id: str, subpath: str, methods, view) -> None:
        with self._lock:
            self._routes[(plugin_id, subpath.strip('/'))] = (tuple(m.upper() for m in methods), view)

    def add_event(self, plugin_id: str, name: str, handler) -> None:
        with self._lock:
            self._events[(plugin_id, name)] = handler

    def add_unload_hook(self, plugin_id: str, hook) -> None:
        with self._lock:
            self._hooks.setdefault(plugin_id, []).append(hook)

    def add_section(self, plugin_id: str, section) -> None:
        with self._lock:
            taken = self._sections.get(section.id)
            if taken is not None and taken[0] != plugin_id:
                raise ValueError(f'The data section "{section.id}" already belongs to {taken[0]}')
            self._sections[section.id] = (plugin_id, section)

    def add_help(self, plugin_id: str, key: str, topic: dict) -> None:
        with self._lock:
            taken = self._help.get(key)
            if taken is not None and taken[0] != plugin_id:
                raise ValueError(f'The help topic "{key}" already belongs to {taken[0]}')
            self._help[key] = (plugin_id, dict(topic))

    def help_topics(self) -> dict:
        """``{key: topic}`` of the help topics of the loaded plugins."""
        with self._lock:
            return {key: dict(topic) for key, (_, topic) in self._help.items()}

    def remove_plugin(self, plugin_id: str) -> None:
        """Take back everything *plugin_id* has registered; its unload hooks run (a failing one is logged)."""
        with self._lock:
            hooks = self._hooks.pop(plugin_id, [])
            for handler_id in [h for h, (owner, _) in self._handlers.items() if owner == plugin_id]:
                del self._handlers[handler_id]
            for key in [k for k in self._routes if k[0] == plugin_id]:
                del self._routes[key]
            for key in [k for k in self._events if k[0] == plugin_id]:
                del self._events[key]
            for key in [k for k, (owner, _) in self._sections.items() if owner == plugin_id]:
                del self._sections[key]
            for key in [k for k, (owner, _) in self._help.items() if owner == plugin_id]:
                del self._help[key]
            self._plugins.pop(plugin_id, None)
        for hook in reversed(hooks):
            try:
                hook()
            except Exception:
                logger.exception('An unload hook of plugin %s failed', plugin_id)

    def set_failure(self, plugin_id: str, message: str) -> None:
        with self._lock:
            self._failures[plugin_id] = message

    def clear_failure(self, plugin_id: str) -> None:
        with self._lock:
            self._failures.pop(plugin_id, None)

    def failure(self, plugin_id: str) -> str:
        """Why *plugin_id* is switched on but not loaded ('' when it is fine)."""
        with self._lock:
            return self._failures.get(plugin_id, '')

    def retire(self, plugin_id: str, version: str) -> None:
        """Note that a plugin was unloaded; its code stays in memory until the server restarts."""
        with self._lock:
            self._retired.append((plugin_id, version))

    def retired(self) -> list:
        with self._lock:
            return list(self._retired)

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()
            self._plugins.clear()
            self._routes.clear()
            self._events.clear()
            self._hooks.clear()
            self._sections.clear()
            self._help.clear()
            self._warned.clear()
            self._failures.clear()
            self._retired.clear()

    # --- Look-ups --------------------------------------------------------------------------

    def fieldhandler(self, handler_id: str) -> Optional[FieldHandler]:
        with self._lock:
            entry = self._handlers.get(handler_id)
        return entry[1] if entry else None

    def fieldhandler_ids(self) -> list:
        with self._lock:
            return sorted(self._handlers)

    def owner_of(self, handler_id: str) -> Optional[str]:
        with self._lock:
            entry = self._handlers.get(handler_id)
        return entry[0] if entry else None

    def route(self, plugin_id: str, subpath: str):
        """``(methods, view)`` of a plugin's route, or ``None``."""
        with self._lock:
            return self._routes.get((plugin_id, subpath.strip('/')))

    def event(self, plugin_id: str, name: str):
        with self._lock:
            return self._events.get((plugin_id, name))

    def sections(self) -> dict:
        """``{section id: (plugin id, DataSection)}`` of what loaded plugins offer to export and import."""
        with self._lock:
            return dict(self._sections)

    def rights(self) -> list:
        """The ``(key, category, label)`` rights of all loaded plugins."""
        with self._lock:
            return [(r['id'], r['group'], r['label']) for info in self._plugins.values() for r in info.get('rights', [])]

    def loaded(self) -> dict:
        with self._lock:
            return {pid: dict(info) for pid, info in self._plugins.items()}

    def is_loaded(self, plugin_id: str) -> bool:
        with self._lock:
            return plugin_id in self._plugins

    def warn_missing_handler(self, handler_id: str) -> None:
        """Log (once per handler) that content uses a handler whose plugin is not active."""
        with self._lock:
            if handler_id in self._warned:
                return
            self._warned.add(handler_id)
        logger.warning('A field uses the handler "%s", but no active plugin provides it; the field renders empty',
                       handler_id)


registry = PluginRegistry()
