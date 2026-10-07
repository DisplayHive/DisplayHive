"""Where DisplayHive keeps its data on disk — the single place that decides it.

Everything the app writes lives under one data directory, ``DATA_DIR``
(default: ``<app root>/data``), so the code tree itself can stay read-only
and backups/volumes cover a single directory::

    DATA_DIR/                 0750
    ├── db/                   0700  project.db (+ journal/WAL) — SQLite only
    ├── media/                0750  uploads, served at /static/media/
    ├── media_previews/       0750  thumbnails, served at /static/media_previews/
    ├── media_renditions/     0750  scaled copies, served at /static/media_renditions/
    └── import-staging/       0700  uploaded import files between preview and confirm

The URLs stay /static/media/… etc. (they're stored in content), only the
files moved; app.py serves them from here explicitly.

Older installs kept these inside the code tree (``static/media…`` and
``project.db`` in the app root). Nothing is moved automatically — for every
location whose old copy still holds data while the new one doesn't, the old
path keeps being used and is reported in ``DataPaths.legacy``, which the
admin UI turns into a banner with migration steps.

Imported by app.py, migrations/env.py and rerender_all_content.py, so it
must not depend on Flask or the app being set up.
"""

import logging
import os
import stat
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Subdirectories of DATA_DIR that hold media, with their old location
# relative to APP_ROOT.
MEDIA_DIRS = ('media', 'media_previews', 'media_renditions')


@dataclass
class DataPaths:
    data_dir: str
    media: str
    media_previews: str
    media_renditions: str
    import_staging: str
    # SQLite file, or None when DATABASE_URL points elsewhere (PostgreSQL).
    db_path: str | None
    # Old locations still in use: [{'kind': 'media', 'path': '/app/static/media'}, …]
    legacy: list[dict] = field(default_factory=list)


def _has_content(path: str) -> bool:
    try:
        with os.scandir(path) as entries:
            return any(True for _ in entries)
    except OSError:
        return False


def resolve(environ=None, app_root: str | None = None) -> DataPaths:
    """Work out every data location from the environment (no side effects)."""
    env = os.environ if environ is None else environ
    app_root = app_root or APP_ROOT  # read at call time, so tests can point it elsewhere
    data_dir = os.path.abspath(env.get('DATA_DIR') or os.path.join(app_root, 'data'))
    legacy = []

    resolved = {}
    for name in MEDIA_DIRS:
        new = os.path.join(data_dir, name)
        old = os.path.join(app_root, 'static', name)
        if _has_content(old) and not _has_content(new):
            resolved[name] = old
            legacy.append({'kind': name, 'path': old})
        else:
            resolved[name] = new

    db_path = None
    if not env.get('DATABASE_URL'):
        if env.get('TEST_DB_PATH'):
            db_path = env['TEST_DB_PATH']
        else:
            new_db = os.path.join(data_dir, 'db', 'project.db')
            old_db = os.path.join(app_root, 'project.db')
            if os.path.isfile(old_db) and not os.path.isfile(new_db):
                db_path = old_db
                legacy.append({'kind': 'database', 'path': old_db})
            else:
                db_path = new_db

    return DataPaths(
        data_dir=data_dir,
        media=resolved['media'],
        media_previews=resolved['media_previews'],
        media_renditions=resolved['media_renditions'],
        import_staging=os.path.join(data_dir, 'import-staging'),
        db_path=db_path,
        legacy=legacy,
    )


def _make_dir(path: str, mode: int) -> None:
    """Create *path* with *mode* if missing. Existing directories keep their
    permissions — an admin may have set them deliberately."""
    if os.path.isdir(path):
        return
    os.makedirs(path, exist_ok=True)
    os.chmod(path, mode)  # makedirs' mode is filtered through the umask


def ensure_dirs(paths: DataPaths) -> None:
    """Create the data directories DisplayHive writes to, with tight permissions."""
    _make_dir(paths.data_dir, 0o750)
    for name in MEDIA_DIRS:
        _make_dir(getattr(paths, name), 0o750)
    _make_dir(paths.import_staging, 0o700)
    if paths.db_path:
        _make_dir(os.path.dirname(os.path.abspath(paths.db_path)), 0o700)
        _warn_if_db_readable(paths.db_path)


def _warn_if_db_readable(db_path: str) -> None:
    try:
        mode = os.stat(db_path).st_mode
    except OSError:
        return  # not created yet
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        logger.warning(
            'The SQLite database %s is readable by other users (mode %o). It holds password hashes '
            'and secrets — consider: chmod 600 %s', db_path, stat.S_IMODE(mode), db_path,
        )


def deployment_kind(environ=None) -> str:
    """'docker', 'nixos' or 'manual' — set by the Docker image / NixOS module,
    so the admin UI can show the matching migration steps."""
    env = os.environ if environ is None else environ
    kind = (env.get('DISPLAYHIVE_DEPLOYMENT') or '').strip().lower()
    return kind if kind in ('docker', 'nixos') else 'manual'
