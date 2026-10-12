"""What version of DisplayHive is running — shown in the admin footer, returned
by the admin API, and part of the cache-busting ``ASSET_VERSION``.

* ``release()``: the contents of the ``VERSION`` file in the repository root
  (the one place to bump on a release).
* ``revision()``: the commit it was built from, first found of
  ``DISPLAYHIVE_REVISION`` (set by the Docker image, whose build context has no
  .git), a ``REVISION`` file in the repository root, ``git rev-parse`` in the
  checkout (NixOS and development), else ``unknown``.
"""

import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = 'unknown'
_SHORT = 7


def _short(revision: str) -> str:
    revision = revision.strip()
    return revision[:_SHORT] if re.fullmatch(r'[0-9a-fA-F]{12,64}', revision) else revision


@lru_cache(maxsize=1)
def release() -> str:
    try:
        return (ROOT / 'VERSION').read_text(encoding='utf-8').strip() or '0.0.0'
    except OSError:
        return '0.0.0'


@lru_cache(maxsize=1)
def revision() -> str:
    from_env = os.environ.get('DISPLAYHIVE_REVISION', '').strip()
    if from_env:
        return _short(from_env)
    try:
        from_file = (ROOT / 'REVISION').read_text(encoding='utf-8').strip()
        if from_file:
            return _short(from_file)
    except OSError:
        pass
    try:
        result = subprocess.run(
            ['git', 'rev-parse', f'--short={_SHORT}', 'HEAD'],
            cwd=ROOT, capture_output=True, text=True, timeout=3, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return UNKNOWN


def info() -> dict:
    return {'version': release(), 'revision': revision()}


def display() -> str:
    rev = revision()
    return release() if rev == UNKNOWN else f'{release()} ({rev})'


def asset_version() -> str:
    """Query-string value for cache-busting the screen's JS/CSS: changes with
    every release or commit. Without a known commit, the build time of the screen
    bundle stands in, so a redeploy still busts caches."""
    rev = revision()
    if rev == UNKNOWN:
        try:
            rev = str(int((ROOT / 'dist' / 'screen' / 'screen.js').stat().st_mtime))
        except OSError:
            rev = ''
    return re.sub(r'[^A-Za-z0-9._-]', '', f'{release()}-{rev}' if rev else release())
