"""Database models that plugins bring.

SQLAlchemy cannot forget a model class once it is mapped, and a table can be declared only once per
process. So a plugin does not define its models at the top of a module (that would run again each time the
plugin is loaded, after it was switched off and on, or updated) but hands the definition to
:func:`once`; the classes are built the first time and the same classes are returned afterwards.

    def build(db):
        class Note(db.Model):
            __tablename__ = 'plg_acme_demo_note'
            ...
        return SimpleNamespace(Note=Note)

    models = api.models.once(build)

The tables themselves are created by the plugin's migrations (``plugin.json`` → ``migrations``), never by
``create_all``. Table names start with ``plg_`` and the plugin's id; a plugin that takes over tables that
older versions of DisplayHive created in the core lists them as ``adopts_tables`` in its manifest.
"""

import threading
from typing import Callable

_lock = threading.Lock()
_built: dict = {}


def once(key: str, build: Callable):
    """The models of plugin *key*: ``build(db)`` the first time, the same result afterwards."""
    with _lock:
        if key not in _built:
            from application.models import db
            _built[key] = build(db)
        return _built[key]


def is_plugin_table(name: str, legacy: set) -> bool:
    """Whether a database table belongs to a plugin (and so is not in the core models' metadata)."""
    return name.startswith('plg_') or name in legacy
