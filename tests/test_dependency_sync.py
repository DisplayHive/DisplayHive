"""One source of Python packages: the lock files.

requirements.txt (runtime) and requirements-dev.txt (runtime + test/docs
tools) are the only place package versions are decided. The Docker image
and CI install them with pip; the Nix dev shell (shell.nix) and the NixOS
module (nix/module.nix) take only the *interpreter* from Nix and sync a venv
from them with uv. These checks fail if a second source creeps back in — a
Nix package list that would drift from the lock, as eventlet,
simple-websocket and cryptography each once did."""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def test_nix_defines_no_python_package_list():
    for rel in ('shell.nix', 'nix/module.nix'):
        assert 'withPackages' not in _read(rel), \
            f'{rel} builds its own Python package set — packages come from the lock files'


def test_dev_shell_syncs_the_dev_lock():
    assert re.search(r'uv pip sync .*requirements-dev\.txt', _read('shell.nix'))


def test_module_syncs_the_runtime_lock():
    module = _read('nix/module.nix')
    assert re.search(r'uv\S* pip sync', module)
    assert '/requirements.txt' in module
    assert 'requirements-dev' not in module, 'production must not install test/docs tools'


def test_runtime_lock_has_no_dev_tools():
    lock = _read('requirements.txt').lower()
    for tool in ('pytest', 'mkdocs', 'pyan3'):
        assert not re.search(rf'^{tool}[=-]', lock, re.MULTILINE), f'{tool} is in the runtime lock'


def test_tests_run_on_the_locked_versions():
    """Catches running the suite outside the synced venv (e.g. a stale one)."""
    import importlib.metadata as md
    pins = dict(re.findall(r'^([A-Za-z0-9_.\-]+)==([^\s\\;]+)', _read('requirements-dev.txt'), re.MULTILINE))
    for name in ('flask', 'flask-socketio', 'sqlalchemy', 'pytest'):
        pinned = next(v for k, v in pins.items() if k.lower() == name)
        assert md.version(name) == pinned, f'{name} {md.version(name)} installed, lock says {pinned}'
