"""DATABASE_URL handling shared by the app and Alembic.

PostgreSQL is the database DisplayHive runs on. SQLite is supported for
development and tests only — and only when asked for explicitly with a
``sqlite:///…`` URL: there is no silent fallback to a file when DATABASE_URL is
unset (in a container such a file lands outside every volume and is lost on the
next recreate), and the Docker image and the NixOS module refuse SQLite.
"""

import os
from typing import Iterable, Optional


class DatabaseConfigError(ValueError):
    """DATABASE_URL is missing or not usable here; the message says what to do."""


def normalize_database_url(url: str) -> str:
    """Make the PostgreSQL driver explicit (psycopg2).

    A bare ``postgresql://`` URL leaves the driver choice to SQLAlchemy, whose
    default changed between releases (psycopg2 in 2.0, psycopg 3 in 2.1) — an
    unpinned image build then fails with "No module named 'psycopg'" although
    psycopg2 is what we install. Naming the driver makes the result independent
    of that. URLs that already name a driver (``postgresql+psycopg://``…) and
    non-PostgreSQL URLs are left alone.
    """
    for prefix in ('postgresql://', 'postgres://'):
        if url.startswith(prefix):
            return 'postgresql+psycopg2://' + url[len(prefix):]
    return url


def is_sqlite_url(url: str) -> bool:
    return url.startswith('sqlite')


def sqlite_path_from_url(url: str) -> Optional[str]:
    """The absolute file path a ``sqlite:///…`` URL points at; None for other
    databases and for in-memory SQLite."""
    if not is_sqlite_url(url):
        return None
    from sqlalchemy.engine import make_url
    database = make_url(url).database
    if not database or database == ':memory:':
        return None
    return os.path.abspath(database)


def sqlite_url_for(path: str) -> str:
    """The ``sqlite:///…`` URL for a file path (absolute paths get four slashes)."""
    return 'sqlite:///' + os.path.abspath(path)


def resolve_database_url(environ, deployment: str = 'manual', existing_sqlite_files: Iterable[str] = ()) -> str:
    """The database URL to use, from DATABASE_URL — or a DatabaseConfigError.

    *deployment* is 'docker', 'nixos' or 'manual' (see paths.deployment_kind);
    *existing_sqlite_files* are SQLite files that earlier versions would have
    picked up silently, named in the error so nobody thinks their data is gone.
    """
    raw = (environ.get('DATABASE_URL') or '').strip()
    if not raw:
        message = (
            'DATABASE_URL is not set. DisplayHive runs on PostgreSQL: set DATABASE_URL, '
            'e.g. postgresql://displayhive:PASSWORD@localhost:5432/displayhive '
            '(see docs/user/installation.md). For local development only, an explicit SQLite '
            'URL works: DATABASE_URL=sqlite:///data/db/project.db'
        )
        found = list(existing_sqlite_files)
        if found:
            first = found[0]
            message += (
                f'\n\nFound an existing SQLite database: {first}\n'
                'Earlier versions used such a file silently when DATABASE_URL was unset. Your data is '
                'still in it; nothing was moved or deleted. Either keep using it for development with '
                f'DATABASE_URL={sqlite_url_for(first)}, or move to PostgreSQL: set DATABASE_URL to the '
                f'new PostgreSQL database, run `alembic upgrade head`, then '
                f'`flask dh copy-database --from {sqlite_url_for(first)}`. '
                'In a Docker container the file is inside the container: copy it out with '
                '`docker cp` before the container is removed (see docs/user/installation.md).'
            )
        raise DatabaseConfigError(message)

    url = normalize_database_url(raw)
    if is_sqlite_url(url) and deployment in ('docker', 'nixos'):
        where = 'the Docker image' if deployment == 'docker' else 'the NixOS module'
        raise DatabaseConfigError(
            f'SQLite is for development only and is not supported by {where}. Use PostgreSQL: '
            'DATABASE_URL=postgresql://user:password@host:5432/displayhive. To move an existing SQLite '
            'database over, see `flask dh copy-database` in docs/user/installation.md.'
        )
    return url
