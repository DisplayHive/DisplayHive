"""Applying database migrations safely: back up first, stop clearly on failure.

``migrate()`` is what ``flask dh migrate`` runs — by the Docker entrypoint, the
compose ``migrate`` service and the NixOS unit before the app starts:

1. Already at the newest schema: nothing to do.
2. A new, empty database: migrate, no backup (there is nothing to lose).
3. Otherwise: back up first (``premigrate-…``, see application/backup.py), and
   only if that worked, migrate. A failed migration raises ``MigrationFailed``
   naming the backup; the caller exits with ``EXIT_FAILED`` so that nothing
   starts the app on a half-migrated database and a restart policy has no
   reason to retry.
4. After a successful migration, old upgrade backups are pruned.

PostgreSQL runs all migrations in one transaction, so a failure there leaves
the schema as it was; SQLite (development) does not.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from application import backup

logger = logging.getLogger(__name__)

EXIT_FAILED = 78   # EX_CONFIG: retrying the same thing will not help


class MigrationFailed(Exception):
    def __init__(self, message: str, backup_path: Optional[Path] = None):
        super().__init__(message)
        self.backup_path = backup_path


@dataclass
class Result:
    status: str                       # uptodate | initialized | upgraded
    backup_path: Optional[Path] = None


def heads() -> set:
    from application.web.health import _migration_heads
    return set(_migration_heads())


def current_revisions(engine: Engine) -> set:
    from alembic.runtime.migration import MigrationContext
    with engine.connect() as connection:
        return set(MigrationContext.configure(connection).get_current_heads())


def is_empty(engine: Engine) -> bool:
    """No tables of ours yet (a fresh database)."""
    return not set(inspect(engine).get_table_names()) - {'alembic_version'}


def upgrade_to_head(engine: Engine) -> None:
    """``alembic upgrade head`` on *engine*, in one transaction where the database
    supports transactional DDL (migrations/env.py takes the connection)."""
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / 'alembic.ini'))
    config.set_main_option('script_location', str(root / 'migrations'))
    alembic_log = logging.getLogger('alembic.runtime.migration')
    previous = alembic_log.level
    alembic_log.setLevel(logging.INFO)   # "Running upgrade a -> b" lines, whatever LOG_LEVEL says
    try:
        with engine.begin() as connection:
            config.attributes['connection'] = connection
            command.upgrade(config, 'head')
    finally:
        alembic_log.setLevel(previous)


def migrate(engine: Engine, backups_dir, settings: backup.Settings, echo: Callable[[str], None] = print,
            upgrade: Optional[Callable[[Engine], None]] = None, do_backup: bool = True) -> Result:
    upgrade = upgrade or upgrade_to_head   # looked up per call, so tests can replace it
    target = heads()
    try:
        current = current_revisions(engine)
        empty = is_empty(engine)
    except Exception as exc:
        raise MigrationFailed(f'The database is not reachable: {exc}') from exc
    if current == target:
        echo('Database schema is up to date.')
        return Result('uptodate')

    backup_path = None
    if empty:
        echo('New database: creating the schema.')
    elif settings.migration_backup and do_backup:
        from_rev = ','.join(sorted(current)) if current else None
        to_rev = ','.join(sorted(target))
        echo('Backing up the database before migrating...')
        try:
            backup_path = backup.create_premigrate_backup(engine, backups_dir, from_rev, to_rev)
        except backup.BackupError as exc:
            raise MigrationFailed(
                f'The backup before the migration failed, so nothing was migrated: {exc} '
                '(MIGRATION_BACKUP=off skips the backup — only if you have your own.)') from exc
        echo(f'Backup written: {backup_path}')
    else:
        echo('Migrating WITHOUT a backup (disabled).')

    echo('Applying database migrations...')
    try:
        upgrade(engine)
    except Exception as exc:
        raise MigrationFailed(f'The migration failed: {exc}', backup_path) from exc

    pruned = backup.prune_premigrate(backups_dir, settings.migration_keep)
    if pruned:
        echo(f'Removed {len(pruned)} old upgrade backup(s).')
    echo('Database schema is up to date.')
    return Result('initialized' if empty else 'upgraded', backup_path)
