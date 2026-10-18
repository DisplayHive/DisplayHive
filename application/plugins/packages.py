"""The Python packages a plugin needs, and whether this server has them.

A plugin lists them in ``plugin.json`` (``"requires_python_packages": ["segno>=1.6"]``). DisplayHive never installs
packages while it runs (the Docker image has no pip and the NixOS package is read-only): a plugin may use what the
server ships. The list lets the Plugins page and the loader say *what* is missing before anything is imported, instead
of an import error in the middle of loading.

A requirement is a package name, optionally with one comparison: ``segno``, ``segno>=1.6``, ``pillow==10.2.0``
(``>=``, ``>``, ``<=``, ``<``, ``==``; the version is compared as numbers up to the first letter).
"""

import re
from importlib import metadata

from application.plugins.manifest import PluginError

_REQUIREMENT = re.compile(r'^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:(>=|<=|==|>|<)\s*(\d+(?:\.\d+)*))?\s*$')


def parse_requirement(text: str) -> tuple:
    """``(name, operator or '', version tuple)``; ``PluginError`` if *text* is not understood."""
    match = _REQUIREMENT.match(text) if isinstance(text, str) else None
    if not match:
        raise PluginError(f'"{text}" is not a Python package requirement (use e.g. segno>=1.6)')
    name, op, version = match.groups()
    return name, op or '', tuple(int(p) for p in version.split('.')) if version else ()


def _installed_version(name: str) -> tuple:
    """The installed version as numbers, or ``None`` when the package is not installed."""
    try:
        text = metadata.version(name)
    except metadata.PackageNotFoundError:
        return None
    numbers = re.match(r'\d+(?:\.\d+)*', text)
    return tuple(int(p) for p in numbers.group(0).split('.')) if numbers else ()


def _satisfied(installed: tuple, op: str, wanted: tuple) -> bool:
    if not op:
        return True
    size = max(len(installed), len(wanted))
    a, b = installed + (0,) * (size - len(installed)), wanted + (0,) * (size - len(wanted))
    return {'>=': a >= b, '>': a > b, '<=': a <= b, '<': a < b, '==': a == b}[op]


def unmet(requirements) -> list:
    """What is missing or too old, as text for the administrator (``[]`` when everything is there)."""
    problems = []
    for text in requirements or ():
        name, op, version = parse_requirement(text)
        installed = _installed_version(name)
        if installed is None:
            problems.append(f'{text.strip()} (not installed)')
        elif not _satisfied(installed, op, version):
            problems.append(f'{text.strip()} (installed: {".".join(map(str, installed))})')
    return problems
