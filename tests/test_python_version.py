"""One Python version everywhere: .python-version is the source of truth for
the dev shell (nix/python.nix), the NixOS module, CI (setup-python's
python-version-file) and the Docker image (PYTHON_VERSION build arg).

These checks fail when a copy drifts — e.g. someone hardcodes a version in
a workflow, or bumps .python-version but not the Dockerfile's default."""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def _version():
    raw = _read('.python-version').strip()
    assert re.fullmatch(r'\d+\.\d+', raw), f'.python-version should be "major.minor", got {raw!r}'
    return raw


def test_tests_run_on_the_pinned_version():
    """Catches a dev shell or CI job running another interpreter."""
    assert f'{sys.version_info.major}.{sys.version_info.minor}' == _version()


def test_dockerfile_default_matches():
    match = re.search(r'^ARG PYTHON_VERSION=(\S+)$', _read('Dockerfile'), re.MULTILINE)
    assert match, 'Dockerfile should declare ARG PYTHON_VERSION=<version>'
    assert match.group(1) == _version()
    assert 'FROM python:${PYTHON_VERSION}-slim' in _read('Dockerfile')


def test_workflows_read_the_version_file():
    workflows = os.path.join(ROOT, '.github', 'workflows')
    for name in sorted(os.listdir(workflows)):
        text = _read(os.path.join('.github', 'workflows', name))
        assert not re.search(r'^\s*python-version:', text, re.MULTILINE), \
            f'{name} hardcodes python-version — use python-version-file: .python-version'
        if 'actions/setup-python' in text:
            assert "python-version-file: '.python-version'" in text, name


def test_nix_uses_the_shared_interpreter():
    for rel in ('shell.nix', 'nix/module.nix'):
        text = _read(rel)
        assert 'python.nix' in text, f'{rel} should take its interpreter from nix/python.nix'
        assert not re.search(r'pkgs\.python3\d*\.withPackages', text), \
            f'{rel} picks a Python version itself instead of nix/python.nix'
