"""Backups of the database and the media files, and their retention.

Files live in ``DATA_DIR/backups`` (0700, files 0400: they contain password
hashes and secrets) and are named so that nothing needs a catalogue::

    scheduled-20261008T040000Z.dump                       the periodic backup
    premigrate-20261008T041500Z-from-<rev>-to-<rev>-original.dump
    premigrate-…-retry1.dump / …-partial.dump             see plan_premigrate_tag
    prerestore-…dump                                      taken by `restore` first
    manual-…dump                                          `flask dh backup`
    media-20261008T040000Z.tar                            uploaded media (optional)

``.dump`` is a ``pg_dump --format=custom`` archive (PostgreSQL), ``.sqlite`` a
SQLite file (development). A backup is never overwritten: it is written under a
hidden temporary name and then published with ``os.link``, which fails if the
name exists.

The pre-migration backups protect the *original*: the first backup for an upgrade
is tagged ``original`` and is not removed by any retention rule until the upgrade
has succeeded and newer upgrades have pushed it out; see ``prune_premigrate``.
"""

import logging
import os
import re
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Mapping, Optional

from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

TIMESTAMP = '%Y%m%dT%H%M%SZ'
_NAME = re.compile(
    r'^(?:(?P<kind>scheduled|premigrate|prerestore|manual)-(?P<ts>\d{8}T\d{6}Z)(?:-(?P<n>\d+))?'
    r'(?:-from-(?P<from>[0-9A-Za-z]+)-to-(?P<to>[0-9A-Za-z]+)-(?P<tag>original|retry\d+|partial))?'
    r'\.(?P<fmt>dump|sqlite)|media-(?P<mts>\d{8}T\d{6}Z)(?:-(?P<mn>\d+))?\.tar)$'
)
MIN_FREE_BYTES = 50 * 1024 * 1024


class BackupError(Exception):
    """A backup or restore could not be done; the message says why."""


@dataclass(frozen=True)
class Settings:
    interval_hours: float = 24.0          # BACKUP_INTERVAL_HOURS, 0 = no scheduled backups
    keep: int = 7                         # BACKUP_KEEP: scheduled database backups to keep
    media_interval_days: int = 0          # BACKUP_MEDIA_INTERVAL_DAYS, 0 = never
    media_keep: int = 2                   # BACKUP_MEDIA_KEEP
    migration_backup: bool = True         # MIGRATION_BACKUP
    migration_keep: int = 3               # MIGRATION_BACKUPS_KEEP: upgrades whose backups are kept

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> 'Settings':
        def number(name, default, cast=float, minimum=0):
            try:
                return max(minimum, cast(environ.get(name, '') or default))
            except ValueError:
                return default
        return cls(
            interval_hours=number('BACKUP_INTERVAL_HOURS', cls.interval_hours),
            keep=number('BACKUP_KEEP', cls.keep, int, 1),
            media_interval_days=number('BACKUP_MEDIA_INTERVAL_DAYS', cls.media_interval_days, int),
            media_keep=number('BACKUP_MEDIA_KEEP', cls.media_keep, int, 1),
            migration_backup=(environ.get('MIGRATION_BACKUP', 'on') or 'on').strip().lower() not in ('0', 'off', 'no', 'false'),
            migration_keep=number('MIGRATION_BACKUPS_KEEP', cls.migration_keep, int, 1),
        )


@dataclass(frozen=True)
class Backup:
    path: Path
    kind: str                       # scheduled | premigrate | prerestore | manual | media
    created: datetime
    fmt: str                        # dump | sqlite | tar
    from_rev: Optional[str] = None
    to_rev: Optional[str] = None
    tag: Optional[str] = None       # original | retryN | partial (premigrate only)

    @property
    def size(self) -> int:
        return self.path.stat().st_size


def parse_name(path: Path) -> Optional[Backup]:
    match = _NAME.match(path.name)
    if not match:
        return None
    if match['mts']:
        return Backup(path, 'media', datetime.strptime(match['mts'], TIMESTAMP).replace(tzinfo=timezone.utc), 'tar')
    if (match['kind'] == 'premigrate') != bool(match['tag']):
        return None   # an upgrade backup always says which upgrade, and only those do
    return Backup(
        path, match['kind'], datetime.strptime(match['ts'], TIMESTAMP).replace(tzinfo=timezone.utc), match['fmt'],
        match['from'], match['to'], match['tag'],
    )


def list_backups(directory) -> list:
    """All backups in *directory*, newest first. Other files are ignored."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    found = [b for b in (parse_name(p) for p in directory.iterdir() if p.is_file()) if b]
    return sorted(found, key=lambda b: (b.created, b.path.name), reverse=True)


# --- writing without ever overwriting ---------------------------------------------


def _name(kind, now, n, from_rev=None, to_rev=None, tag=None, fmt='dump') -> str:
    stamp = now.strftime(TIMESTAMP) + (f'-{n}' if n else '')
    upgrade = f'-from-{from_rev}-to-{to_rev}-{tag}' if tag else ''
    return f'{kind}-{stamp}{upgrade}.{fmt}'


def _publish(partial: Path, directory: Path, make_name: Callable[[int], str]) -> Path:
    """Move *partial* to its final, so far unused name; read-only afterwards.
    ``os.link`` (or an exclusive create where hard links aren't available) fails
    rather than replace an existing file."""
    for n in range(1000):
        final = directory / make_name(n)
        try:
            os.link(partial, final)
        except FileExistsError:
            continue
        except OSError:
            try:
                with open(partial, 'rb') as src, open(final, 'xb') as dst:
                    shutil.copyfileobj(src, dst)
            except FileExistsError:
                continue
        partial.unlink()
        os.chmod(final, 0o400)
        return final
    raise BackupError(f'No free backup name in {directory}')


def _prepare_directory(directory) -> Path:
    directory = Path(directory)
    if not directory.is_dir():
        directory.mkdir(parents=True, mode=0o700)
        os.chmod(directory, 0o700)
    return directory


def _check_space(directory: Path, needed: int) -> None:
    free = shutil.disk_usage(directory).free
    if free < needed + MIN_FREE_BYTES:
        raise BackupError(
            f'Not enough free space in {directory}: {free // 2**20} MB free, about {needed // 2**20} MB '
            f'(+{MIN_FREE_BYTES // 2**20} MB reserve) needed. Free some space or move the backup directory.'
        )


# --- the database -------------------------------------------------------------------


def _server_major(engine: Engine) -> int:
    from sqlalchemy import text
    with engine.connect() as connection:
        return int(connection.execute(text('SHOW server_version_num')).scalar()) // 10000


def _tool(name: str, major: int) -> str:
    """The PostgreSQL client tool *name* of the server's major version.

    A dump is only guaranteed to restore on the version it came from: pg_dump 17
    writes settings (``SET transaction_timeout``) a version 16 server refuses, so
    a mismatched tool makes backups that cannot be restored. Debian/PGDG keep one
    directory per major version; otherwise the one on the PATH must match."""
    versioned = Path(f'/usr/lib/postgresql/{major}/bin/{name}')
    if versioned.exists():
        return str(versioned)
    found = shutil.which(name)
    if not found:
        raise BackupError(f'{name} was not found. Install postgresql-client-{major} (the Docker image has it).')
    out = subprocess.run([found, '--version'], capture_output=True, text=True, check=False).stdout
    match = re.search(r'(\d+)(?:\.\d+)?\s*(?:\(|$)', out.strip())
    have = int(match.group(1)) if match else None
    if have != major:
        raise BackupError(
            f'{name} is version {have or "unknown"} but the database server is version {major}: its backups '
            f'could not be restored on this server. Install postgresql-client-{major}.')
    return found


def _pg_env(url) -> dict:
    """libpq settings from a SQLAlchemy URL, in the environment: the password
    never appears on a command line (visible to other users via ps)."""
    env = os.environ.copy()
    host = url.host or url.query.get('host')
    for key, value in (('PGHOST', host), ('PGPORT', url.port), ('PGUSER', url.username),
                       ('PGPASSWORD', url.password), ('PGDATABASE', url.database),
                       ('PGSSLMODE', url.query.get('sslmode'))):
        if value:
            env[key] = str(value)
    return env


def _database_size(engine: Engine) -> int:
    from sqlalchemy import text
    if engine.dialect.name == 'postgresql':
        with engine.connect() as connection:
            return int(connection.execute(text('SELECT pg_database_size(current_database())')).scalar() or 0)
    path = engine.url.database
    return os.path.getsize(path) if path and os.path.exists(path) else 0


def _last_lines(text: str, n: int = 5) -> str:
    return ' | '.join(line for line in (text or '').strip().splitlines()[-n:])


def create_db_backup(engine: Engine, directory, kind: str, *, from_rev=None, to_rev=None, tag=None,
                     now: Optional[datetime] = None) -> Path:
    """Dump the database behind *engine* into *directory*; returns the file."""
    directory = _prepare_directory(directory)
    now = now or datetime.now(timezone.utc)
    _check_space(directory, _database_size(engine))
    postgres = engine.dialect.name == 'postgresql'
    fmt = 'dump' if postgres else 'sqlite'
    partial = directory / f'.{kind}-{now.strftime(TIMESTAMP)}-{os.getpid()}.partial'
    partial.unlink(missing_ok=True)
    try:
        if postgres:
            result = subprocess.run(
                [_tool('pg_dump', _server_major(engine)), '--format=custom', '--no-owner', '--no-acl', '--file', str(partial)],
                env=_pg_env(engine.url), capture_output=True, text=True, check=False,
            )
            if result.returncode != 0:
                raise BackupError(f'pg_dump failed: {_last_lines(result.stderr)}')
        elif engine.dialect.name == 'sqlite' and engine.url.database:
            source = sqlite3.connect(f'file:{engine.url.database}?mode=ro', uri=True)
            target = sqlite3.connect(str(partial))
            try:
                source.backup(target)
            finally:
                target.close()
                source.close()
        else:
            raise BackupError(f'Backups are not supported for {engine.dialect.name} databases.')
        os.chmod(partial, 0o600)
        return _publish(partial, directory, lambda n: _name(kind, now, n, from_rev, to_rev, tag, fmt))
    finally:
        partial.unlink(missing_ok=True)


def _restore_postgres(engine: Engine, backup_file: Path) -> None:
    """Replace the public schema with the dump's contents in ONE transaction:
    the script (DROP/CREATE SCHEMA, then the dump as SQL from pg_restore) runs
    through psql with ON_ERROR_STOP and --single-transaction, so a failure leaves
    the database exactly as it was — never a dropped schema and a half restore."""
    major = _server_major(engine)
    pg_restore, psql = _tool('pg_restore', major), _tool('psql', major)
    env = _pg_env(engine.url)
    listing = subprocess.run([pg_restore, '--list', str(backup_file)], env=env, capture_output=True, text=True, check=False)
    if listing.returncode != 0:
        raise BackupError(f'{backup_file.name} cannot be read as a backup: {_last_lines(listing.stderr)}')
    with tempfile.TemporaryFile() as psql_errors, tempfile.TemporaryFile() as restore_errors:
        script = subprocess.Popen([pg_restore, '--no-owner', '--no-acl', '-f', '-', str(backup_file)],
                                  env=env, stdout=subprocess.PIPE, stderr=restore_errors)
        loader = subprocess.Popen(
            [psql, '--no-psqlrc', '--quiet', '--single-transaction', '--set', 'ON_ERROR_STOP=1', '--file', '-'],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=psql_errors, env=env)
        try:
            loader.stdin.write(b'DROP SCHEMA public CASCADE;\nCREATE SCHEMA public;\n')
            shutil.copyfileobj(script.stdout, loader.stdin)
        except BrokenPipeError:
            pass                                  # psql stopped on an error; its message is below
        finally:
            script.stdout.close()
            try:
                loader.stdin.close()
            except BrokenPipeError:
                pass
        script.wait()
        loader.wait()
        for handle in (psql_errors, restore_errors):
            handle.seek(0)
        loader_message = _last_lines(psql_errors.read().decode(errors='replace'))
        restore_message = _last_lines(restore_errors.read().decode(errors='replace'))
    if loader.returncode != 0:
        raise BackupError(f'The restore failed and nothing was changed: {loader_message or "psql stopped"}')
    if script.returncode != 0:
        raise BackupError(f'pg_restore failed: {restore_message}')


def restore_db_backup(engine: Engine, backup_file) -> None:
    """Replace the database behind *engine* with the contents of *backup_file*.
    The caller makes the safety backup first (see ``restore_with_safety_backup``)."""
    backup_file = Path(backup_file)
    parsed = parse_name(backup_file)
    if not backup_file.is_file() or not parsed or parsed.kind == 'media':
        raise BackupError(f'{backup_file} is not a DisplayHive database backup.')
    postgres = engine.dialect.name == 'postgresql'
    if (parsed.fmt == 'dump') != postgres:
        raise BackupError(f'{backup_file.name} is a {parsed.fmt} backup and cannot be restored into {engine.dialect.name}.')
    if postgres:
        _restore_postgres(engine, backup_file)
    else:
        engine.dispose()
        source = sqlite3.connect(f'file:{backup_file}?mode=ro', uri=True)
        target = sqlite3.connect(engine.url.database)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
    engine.dispose()


def restore_with_safety_backup(engine: Engine, backup_file, directory, echo=lambda _m: None) -> Path:
    """Back the current state up as ``prerestore-…`` first, then restore. If the
    restore fails, the safety backup is put back (best effort). Returns the
    safety backup's path."""
    safety = create_db_backup(engine, directory, 'prerestore')
    echo(f'Current state saved as {safety.name}')
    try:
        restore_db_backup(engine, backup_file)
    except BackupError as exc:
        try:
            restore_db_backup(engine, safety)
        except BackupError as again:
            raise BackupError(
                f'{exc} Putting the previous state back failed too ({again}); it is saved in {safety}.') from exc
        raise BackupError(f'{exc} The previous state was put back.') from exc
    return safety


# --- the media ----------------------------------------------------------------------


def create_media_backup(media_dir, directory, now: Optional[datetime] = None) -> Path:
    """An (uncompressed: images are compressed already) tar of the uploaded media.
    Previews and renditions are regenerated and not part of it."""
    media_dir = Path(media_dir)
    directory = _prepare_directory(directory)
    now = now or datetime.now(timezone.utc)
    total = sum(f.stat().st_size for f in media_dir.rglob('*') if f.is_file()) if media_dir.is_dir() else 0
    _check_space(directory, total)
    partial = directory / f'.media-{now.strftime(TIMESTAMP)}-{os.getpid()}.partial'
    partial.unlink(missing_ok=True)
    try:
        with tarfile.open(partial, 'w') as archive:
            if media_dir.is_dir():
                archive.add(media_dir, arcname='media')
        os.chmod(partial, 0o600)
        return _publish(partial, directory, lambda n: f'media-{now.strftime(TIMESTAMP)}' + (f'-{n}' if n else '') + '.tar')
    finally:
        partial.unlink(missing_ok=True)


# --- the upgrade backup: original, retries, partial ---------------------------------


def plan_premigrate_tag(existing, from_rev: str, to_rev: str) -> str:
    """How to label the backup taken before migrating *from_rev* to *to_rev*:

    * ``original``: the first one for this upgrade;
    * ``retryN``: the database is still at the revision the original was taken
      at (a failed attempt rolled back) — a repeat;
    * ``partial``: the database has moved on (a half-applied migration): it must
      never be mistaken for, or replace, the original.
    """
    group = [b for b in existing if b.kind == 'premigrate' and b.to_rev == to_rev]
    originals = [b for b in group if b.tag == 'original']
    if not originals:
        return 'original'
    if from_rev != originals[0].from_rev:
        return 'partial'
    retries = [int(b.tag[5:]) for b in group if b.tag and b.tag.startswith('retry')]
    return f'retry{max(retries, default=0) + 1}'


def create_premigrate_backup(engine: Engine, directory, from_rev: Optional[str], to_rev: str) -> Path:
    from_rev = from_rev or 'none'
    tag = plan_premigrate_tag(list_backups(directory), from_rev, to_rev)
    return create_db_backup(engine, directory, 'premigrate', from_rev=from_rev, to_rev=to_rev, tag=tag)


def _delete(backup: Backup) -> None:
    try:
        backup.path.unlink()
        logger.info('Removed old backup %s', backup.path.name)
    except OSError as exc:
        logger.warning('Could not remove old backup %s: %s', backup.path.name, exc)


def prune_premigrate(directory, keep_upgrades: int, keep_retries: int = 2) -> list:
    """After a *successful* migration: keep every backup of the newest
    *keep_upgrades* upgrades (grouped by target revision) and, within those, the
    original, all partials and the newest *keep_retries* retries. Returns what
    was removed. Never called before the migration has succeeded."""
    groups = {}
    for backup in list_backups(directory):
        if backup.kind == 'premigrate':
            groups.setdefault(backup.to_rev, []).append(backup)
    ordered = sorted(groups.values(), key=lambda g: min(b.created for b in g), reverse=True)
    removed = []
    for index, group in enumerate(ordered):
        if index >= keep_upgrades:
            removed.extend(group)
        else:
            retries = sorted((b for b in group if b.tag and b.tag.startswith('retry')),
                             key=lambda b: int(b.tag[5:]), reverse=True)
            removed.extend(retries[keep_retries:])
    for backup in removed:
        _delete(backup)
    return removed


# --- scheduled backups ---------------------------------------------------------------


def prune_scheduled(directory, settings: Settings) -> list:
    backups = list_backups(directory)
    removed = [b for b in [b for b in backups if b.kind == 'scheduled'][settings.keep:]]
    removed += [b for b in [b for b in backups if b.kind == 'media'][settings.media_keep:]]
    removed += [b for b in [b for b in backups if b.kind == 'prerestore'][5:]]
    for backup in removed:
        _delete(backup)
    return removed


def _last(directory, kind) -> Optional[datetime]:
    return next((b.created for b in list_backups(directory) if b.kind == kind), None)


def database_backup_due(directory, settings: Settings, now: datetime) -> bool:
    if settings.interval_hours <= 0:
        return False
    last = _last(directory, 'scheduled')
    return last is None or now - last >= timedelta(hours=settings.interval_hours)


def media_backup_due(directory, settings: Settings, now: datetime) -> bool:
    if settings.media_interval_days <= 0:
        return False
    last = _last(directory, 'media')
    return last is None or now - last >= timedelta(days=settings.media_interval_days)


def run_scheduled(engine: Engine, directory, media_dir, settings: Settings, now: Optional[datetime] = None) -> list:
    """Whatever is due: a database backup and/or a media archive, then
    retention. Returns the files written."""
    now = now or datetime.now(timezone.utc)
    written = []
    if database_backup_due(directory, settings, now):
        written.append(create_db_backup(engine, directory, 'scheduled', now=now))
    if media_backup_due(directory, settings, now):
        written.append(create_media_backup(media_dir, directory, now=now))
    if written:
        prune_scheduled(directory, settings)
    return written
