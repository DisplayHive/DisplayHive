"""Where DisplayHive keeps its data on disk — the single place that decides it.

Everything the app writes lives under one data directory, ``DATA_DIR``
(default: ``<app root>/data``), so the code tree itself can stay read-only
and backups/volumes cover a single directory::

    DATA_DIR/                 0750
    ├── db/                   0700  only if DATABASE_URL points into it (SQLite, development)
    ├── media/                0750  uploads, served at /static/media/
    ├── media_previews/       0750  thumbnails, served at /static/media_previews/
    ├── media_renditions/     0750  scaled copies, served at /static/media_renditions/
    ├── icons/                0750  installed icon libraries, served at /static/icons/ (application/icon_libraries.py)
    ├── import-staging/       0700  uploaded import files between preview and confirm
    └── backups/              0700  database dumps and media archives (application/backup.py)

The URLs stay /static/media/… etc. (they're stored in content), only the
files moved; app.py serves them from here explicitly.

Older installs kept the media inside the code tree (``static/media…``).
Nothing is moved automatically — for every location whose old copy still holds
data while the new one doesn't, the old path keeps being used and is reported in
``DataPaths.legacy``, which the admin UI turns into a banner with migration
steps. (The database has no such fallback any more: DATABASE_URL is required,
see application/db_url.py; ``existing_sqlite_files`` finds files that earlier
versions would have used silently.)

Imported by app.py and migrations/env.py, so it
must not depend on Flask or the app being set up.
"""

import logging
import os
import stat
from dataclasses import dataclass, field

from application.db_url import normalize_database_url, sqlite_path_from_url

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
    backups: str
    icons: str
    # The SQLite file DATABASE_URL points at, or None (PostgreSQL, or unset).
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

    db_path = sqlite_path_from_url(normalize_database_url(env.get('DATABASE_URL') or ''))

    return DataPaths(
        data_dir=data_dir,
        media=resolved['media'],
        media_previews=resolved['media_previews'],
        media_renditions=resolved['media_renditions'],
        import_staging=os.path.join(data_dir, 'import-staging'),
        backups=os.path.join(data_dir, 'backups'),
        icons=os.path.join(data_dir, 'icons'),
        db_path=db_path,
        legacy=legacy,
    )


def existing_sqlite_files(environ=None, app_root: str | None = None) -> list[str]:
    """SQLite files at the places earlier versions used when DATABASE_URL was
    unset (DATA_DIR/db/project.db, project.db in the app root)."""
    env = os.environ if environ is None else environ
    app_root = app_root or APP_ROOT
    data_dir = os.path.abspath(env.get('DATA_DIR') or os.path.join(app_root, 'data'))
    candidates = [os.path.join(data_dir, 'db', 'project.db'), os.path.join(app_root, 'project.db')]
    return [path for path in candidates if os.path.isfile(path)]


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
    _make_dir(paths.icons, 0o750)
    _make_dir(paths.import_staging, 0o700)
    _make_dir(paths.backups, 0o700)
    if paths.db_path:
        _make_dir(os.path.dirname(os.path.abspath(paths.db_path)), 0o700)
        _warn_if_db_readable(paths.db_path)


def db_exposed(db_path: str) -> bool:
    """True if users other than the owner can actually read *db_path*: the
    file is group/other-readable *and* its directory lets them in. A 0644
    file inside the 0700 db/ directory is not exposed."""
    try:
        mode = os.stat(db_path).st_mode
        dir_mode = os.stat(os.path.dirname(os.path.abspath(db_path))).st_mode
    except OSError:
        return False
    return bool((mode & (stat.S_IRGRP | stat.S_IROTH)) and (dir_mode & (stat.S_IXGRP | stat.S_IXOTH)))


def _warn_if_db_readable(db_path: str) -> None:
    if db_exposed(db_path):
        mode = os.stat(db_path).st_mode
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
