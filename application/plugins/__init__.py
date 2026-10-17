"""The plugin system: field handlers (and later integrations) loaded from `plugins/` and `DATA_DIR/plugins`.

* ``manifest``  — reading and checking a plugin's ``plugin.json``.
* ``handlers``  — what a field handler is (the Python side).
* ``registry``  — the process-wide table of what the loaded plugins provide.
* ``loader``    — finding plugins, loading and unloading them at run time, keeping the database state.

The host asks the registry, never a plugin by name: ``registry.fieldhandler('countdown')``.
"""

from application.plugins.registry import registry  # noqa: F401  (the singleton)
