"""``plugin.json``: what a plugin is and what it provides."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

PLUGIN_API = 1                      # the version of the interface the host offers plugins
MANIFEST_NAME = 'plugin.json'
KINDS = ('fieldhandler', 'integration')
_ID = re.compile(r'^[a-z0-9][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+$')     # provider.name, lower case
_HANDLER_ID = re.compile(r'^[a-z][a-z0-9_]{0,48}$')
_VERSION = re.compile(r'^\d+\.\d+\.\d+([-+][0-9A-Za-z.-]+)?$')


class PluginError(Exception):
    """A plugin cannot be read or loaded. ``str(e)`` is safe to show an administrator."""


@dataclass(frozen=True)
class Manifest:
    id: str
    name: str
    kind: str
    version: str
    plugin_api: int
    requires_host: str = ''
    preinstalled: bool = False
    fieldhandlers: tuple = ()
    backend: str = ''                 # folder (relative to the plugin) of the Python package
    admin: str = ''                   # ES module for the admin
    screen: str = ''                  # ES module for the screens
    description: str = ''
    author: str = ''
    license: str = ''
    homepage: str = ''
    rights: tuple = ()                # ({id, group, label}, …): rights the plugin adds, ids start with "<plugin id>."
    migrations: str = ''              # folder with the plugin's schema migrations
    adopts_tables: tuple = ()         # tables older versions created in the core, which now belong to the plugin
    requires_python_packages: tuple = ()   # Python packages the server must have, e.g. ("segno>=1.6",)
    directory: Path = field(default=None, compare=False)
    raw: dict = field(default_factory=dict, compare=False)


def _text(data: dict, key: str, required: bool = True) -> str:
    value = data.get(key, '')
    if value in ('', None):
        if required:
            raise PluginError(f'{MANIFEST_NAME}: "{key}" is missing')
        return ''
    if not isinstance(value, str):
        raise PluginError(f'{MANIFEST_NAME}: "{key}" must be text')
    return value.strip()


def _relative(value: str, key: str) -> str:
    """A path inside the plugin: never absolute, never leaving the folder."""
    if not value:
        return ''
    parts = Path(value).parts
    if Path(value).is_absolute() or '..' in parts:
        raise PluginError(f'{MANIFEST_NAME}: "{key}" must be a path inside the plugin')
    return value


_TABLE = re.compile(r'^[a-z][a-z0-9_]{0,62}$')


def _adopted(plugin_id: str, data) -> tuple:
    if not isinstance(data, list) or not all(isinstance(t, str) and _TABLE.match(t) for t in data):
        raise PluginError(f'{plugin_id}: "adopts_tables" must be a list of table names')
    return tuple(data)


def _packages(plugin_id: str, data) -> tuple:
    from application.plugins.packages import parse_requirement
    if not isinstance(data, list):
        raise PluginError(f'{plugin_id}: "requires_python_packages" must be a list')
    for text in data:
        parse_requirement(text)         # a PluginError for one that is not understood
    return tuple(str(t).strip() for t in data)


_RIGHT = re.compile(r'^[a-z0-9][a-z0-9.-]*\.[a-z][a-z0-9_]*$')


def _rights(plugin_id: str, data) -> tuple:
    """The rights a plugin adds: ``[{"id": "acme.demo.manage", "group": "Demo", "label": "…"}]``. Every id
    starts with the plugin's own id, so plugins can neither clash nor claim a right of the host."""
    if not isinstance(data, list):
        raise PluginError(f'{plugin_id}: "rights" must be a list')
    out = []
    for item in data:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item.get(k) for k in ('id', 'group', 'label')):
            raise PluginError(f'{plugin_id}: every right needs an id, a group and a label')
        right_id = item['id']
        if not right_id.startswith(plugin_id + '.') or not _RIGHT.match(right_id):
            raise PluginError(f'{plugin_id}: the right "{right_id}" must start with "{plugin_id}."')
        out.append({'id': right_id, 'group': item['group'], 'label': item['label']})
    return tuple(out)


def parse_manifest(data, directory: Path = None) -> Manifest:
    """Check *data* (the decoded ``plugin.json``) and return the manifest; ``PluginError`` if it is not valid."""
    if not isinstance(data, dict):
        raise PluginError(f'{MANIFEST_NAME} must be an object')
    plugin_id = _text(data, 'id')
    if not _ID.match(plugin_id):
        raise PluginError(f'"{plugin_id}" is not a valid plugin id (use provider.name, lower case)')
    kind = _text(data, 'kind')
    if kind not in KINDS:
        raise PluginError(f'{plugin_id}: kind must be one of {", ".join(KINDS)}')
    version = _text(data, 'version')
    if not _VERSION.match(version):
        raise PluginError(f'{plugin_id}: "{version}" is not a version like 1.0.0')
    api = data.get('plugin_api')
    if not isinstance(api, int) or isinstance(api, bool):
        raise PluginError(f'{plugin_id}: "plugin_api" must be a whole number')
    provides = data.get('provides') or {}
    if not isinstance(provides, dict):
        raise PluginError(f'{plugin_id}: "provides" must be an object')
    handlers = provides.get('fieldhandlers') or []
    if not isinstance(handlers, list) or not all(isinstance(h, str) and _HANDLER_ID.match(h) for h in handlers):
        raise PluginError(f'{plugin_id}: "provides.fieldhandlers" must be a list of handler ids like countdown')
    if kind == 'fieldhandler' and len(handlers) != 1:
        raise PluginError(f'{plugin_id}: a field handler plugin provides exactly one handler')
    rights = _rights(plugin_id, data.get('rights') or [])
    return Manifest(
        id=plugin_id,
        name=_text(data, 'name'),
        kind=kind,
        version=version,
        plugin_api=api,
        requires_host=_text(data, 'requires_host', required=False),
        preinstalled=bool(data.get('preinstalled', False)),
        fieldhandlers=tuple(handlers),
        backend=_relative(_text(data, 'backend', required=False), 'backend'),
        admin=_relative(_text(data, 'admin', required=False), 'admin'),
        screen=_relative(_text(data, 'screen', required=False), 'screen'),
        description=_text(data, 'description', required=False),
        author=_text(data, 'author', required=False),
        license=_text(data, 'license', required=False),
        homepage=_text(data, 'homepage', required=False),
        rights=rights,
        migrations=_relative(_text(data, 'migrations', required=False), 'migrations'),
        adopts_tables=_adopted(plugin_id, data.get('adopts_tables') or []),
        requires_python_packages=_packages(plugin_id, data.get('requires_python_packages') or []),
        directory=directory,
        raw=data,
    )


def read_manifest(directory: Path) -> Manifest:
    """Read ``<directory>/plugin.json``."""
    path = Path(directory) / MANIFEST_NAME
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise PluginError(f'{path} does not exist') from None
    except (OSError, ValueError) as problem:
        raise PluginError(f'{path} cannot be read: {problem}') from None
    return parse_manifest(data, Path(directory))


def host_accepts(requires: str, host_version: str) -> bool:
    """Whether *host_version* satisfies a requirement like ``>=1.0.0`` (empty means any)."""
    requires = (requires or '').strip()
    if not requires:
        return True
    m = re.match(r'^>=\s*(\d+)\.(\d+)\.(\d+)$', requires)
    if not m:
        raise PluginError(f'requires_host "{requires}" is not understood (use >=1.0.0)')
    host = re.match(r'^(\d+)\.(\d+)\.(\d+)', host_version or '')
    if not host:
        return True
    # A pre-release of the required version (1.0.0-rc1 for >=1.0.0) counts as that version.
    return tuple(int(x) for x in host.groups()) >= tuple(int(x) for x in m.groups())
