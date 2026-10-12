"""`flask dh migrate`, `backup`, `backups`, `restore` and `copy-database`."""

import os
import sys

import click

from .group import dh


def _backup_context():
    from flask import current_app
    return (current_app.extensions['sqlalchemy'].engine, current_app.config['BACKUP_DIR'],
            current_app.config['BACKUP_SETTINGS'])


@dh.command('migrate')
@click.option('--no-backup', is_flag=True, help='Migrate without the backup first (same as MIGRATION_BACKUP=off).')
def migrate_command(no_backup):
    """Bring the database schema up to date, with a backup first.

    Run before the app starts (the Docker entrypoint and the NixOS unit do).
    Exits with status 78 if the backup or the migration fails: the app must not
    start on a database in an unknown state, and retrying will not help. The
    message names the backup; `flask dh restore` puts it back.
    """
    import logging
    from application.core import logfmt, migration
    engine, directory, settings = _backup_context()
    if logfmt.wanted(os.environ) == 'json':
        # Machine-readable logs: these lines are log records like the rest, not plain output.
        log = logging.getLogger('application.core.migration')
        log.setLevel(logging.INFO)
        say, fail, hint = log.info, log.error, log.error
    else:
        say = click.echo
        fail = lambda m: click.secho(f'\nMIGRATION FAILED: {m}', fg='red', bold=True, err=True)  # noqa: E731
        hint = lambda m: click.secho(m, fg='yellow', err=True)  # noqa: E731
    try:
        migration.migrate(engine, directory, settings, echo=say, do_backup=not no_backup)
    except migration.MigrationFailed as exc:
        fail(f'Migration failed: {exc}' if say is not click.echo else str(exc))
        if exc.backup_path:
            hint(f'The database was backed up first: {exc.backup_path}. '
                 f'Put it back with: flask dh restore {exc.backup_path.name}')
        sys.exit(migration.EXIT_FAILED)


@dh.command('backup')
@click.option('--media', 'with_media', is_flag=True, help='Also archive the uploaded media (previews are regenerated, not included).')
def backup_command(with_media):
    """Back up the database now (and, with --media, the uploaded files)."""
    from flask import current_app
    from application.core import backup
    engine, directory, settings = _backup_context()
    try:
        written = [backup.create_db_backup(engine, directory, 'manual')]
        if with_media:
            written.append(backup.create_media_backup(current_app.config['MEDIA_FOLDER'], directory))
    except backup.BackupError as exc:
        raise click.ClickException(str(exc))
    for path in written:
        click.echo(f'Written: {path} ({path.stat().st_size // 1024} KB)')
    click.echo('This directory is on the same disk as the data: copy the files elsewhere, too.')


@dh.command('backups')
def backups_command():
    """List the backups (newest first)."""
    from datetime import datetime, timezone
    from application.core import backup
    _engine, directory, _settings = _backup_context()
    found = backup.list_backups(directory)
    if not found:
        click.echo(f'No backups in {directory}.')
        return
    now = datetime.now(timezone.utc)
    for b in found:
        age = now - b.created
        ago = f'{age.days}d' if age.days else f'{age.seconds // 3600}h' if age.seconds >= 3600 else f'{age.seconds // 60}m'
        click.echo(f'{b.path.name:<70} {b.size // 1024:>9} KB  {ago:>4} ago')


@dh.command('restore')
@click.argument('file')
@click.option('--yes', is_flag=True, help="Don't ask for confirmation.")
def restore_command(file, yes):
    """Replace the database with a backup (a name from `backups`, or a path).

    STOP DisplayHive first: it must not write while this runs. The current state
    is saved as a `prerestore-…` backup before anything is replaced. Afterwards
    start the app: it migrates the restored database to the current version.
    """
    from pathlib import Path
    from application.core import backup
    engine, directory, _settings = _backup_context()
    path = Path(file)
    if not path.is_absolute() and not path.exists():
        path = Path(directory) / file
    if not yes:
        click.secho('The app must be stopped. This REPLACES the whole database.', fg='yellow')
        click.confirm(f'Restore {path.name}?', abort=True)
    try:
        safety = backup.restore_with_safety_backup(engine, path, directory, echo=click.echo)
    except backup.BackupError as exc:
        raise click.ClickException(str(exc))
    click.secho(f'Restored {path.name}. The previous state is kept as {safety.name}.', fg='green', bold=True)


# --- copy-database ----------------------------------------------------------------


def _revision_of(engine):
    from alembic.runtime.migration import MigrationContext
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _upgrade_to_head(engine):
    """`alembic upgrade head` on *engine*, whatever DATABASE_URL says (see migrations/env.py)."""
    from application.core.migration import upgrade_to_head
    try:
        upgrade_to_head(engine)
    except Exception as exc:
        raise click.ClickException(f'Could not upgrade the source database: {exc}')


@dh.command('copy-database')
@click.option('--from', 'source_url', required=True, metavar='URL',
              help='Database to copy FROM, e.g. sqlite:////data/db/project.db. The configured DATABASE_URL is the target.')
@click.option('--upgrade-source', is_flag=True,
              help='First bring the --from database up to the current schema version (in place: work on a copy of the file).')
@click.option('--yes', is_flag=True, help="Don't ask before replacing the target's contents.")
def copy_database_command(source_url, upgrade_source, yes):
    """Move a SQLite installation to PostgreSQL: copy everything into DATABASE_URL.

    Copies users, groups and rights, SSO providers, devices and their keys,
    settings and content 1:1 from the --from database into the configured one,
    which is EMPTIED first (all or nothing: on an error the target is left as
    it was). Prepare the target with `alembic upgrade head`, and stop the app
    (screens reconnect afterwards). Media files are not in the database: keep
    using the same DATA_DIR / volumes.
    """
    import sqlalchemy as sa
    from flask import current_app
    from application.core.dbcopy import CopyError, copy_database
    from application.core.db_url import normalize_database_url
    from application.web.health import _migration_heads

    db = current_app.extensions['sqlalchemy']
    target_url = current_app.config['SQLALCHEMY_DATABASE_URI']
    source_url = normalize_database_url(source_url.strip())
    if sa.engine.make_url(source_url) == sa.engine.make_url(target_url):
        raise click.ClickException('--from and DATABASE_URL are the same database.')
    if current_app.config.get('SQLITE_IN_USE'):
        click.secho('Note: the target (DATABASE_URL) is SQLite — the usual target is PostgreSQL.', fg='yellow')

    source = sa.create_engine(source_url)
    target = db.engine
    heads = set(_migration_heads())
    if upgrade_source:
        _upgrade_to_head(source)
    for label, engine, hint in (('Source', source, 'add --upgrade-source (it migrates the --from database in place; work on a copy)'),
                                ('Target', target, 'run `alembic upgrade head` on it')):
        try:
            revision = _revision_of(engine)
        except Exception as exc:
            raise click.ClickException(f'{label} database is not reachable: {exc}')
        if revision not in heads:
            raise click.ClickException(
                f'{label} database is not at the current schema version ({revision or "unmigrated"}): {hint}.')

    host = lambda url: sa.engine.make_url(url).render_as_string(hide_password=True)  # noqa: E731
    click.echo(f'From: {host(source_url)}\nTo:   {host(target_url)}')
    if not yes:
        click.confirm('This REPLACES everything in the target database. Continue?', abort=True)
    try:
        counts = copy_database(source, target, db.metadata, echo=click.echo)
    except CopyError as exc:
        raise click.ClickException(str(exc))
    click.secho(f'Done: {sum(counts.values())} row(s) in {len(counts)} table(s) copied.', fg='green', bold=True)
    click.echo('Start DisplayHive against the new database. Devices keep their keys and reconnect by themselves.')


# --- check-config --------------------------------------------------------------
