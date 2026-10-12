"""application/backup.py: naming, never overwriting, retention, SQLite round trip
(and PostgreSQL where pg_dump/pg_restore and a server are available)."""

import hashlib
import os
import shutil
import sqlite3
import stat
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa

from application import backup
from application.backup import Backup, BackupError, Settings

NOW = datetime(2026, 10, 8, 4, 0, 0, tzinfo=timezone.utc)


def _sqlite(tmp_path, name='live.db', rows=('alpha',)):
    engine = sa.create_engine(f'sqlite:///{tmp_path / name}')
    with engine.begin() as conn:
        conn.execute(sa.text('CREATE TABLE note (id INTEGER PRIMARY KEY, text TEXT)'))
        for text in rows:
            conn.execute(sa.text('INSERT INTO note (text) VALUES (:t)'), {'t': text})
    return engine


def _notes(engine):
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(sa.text('SELECT text FROM note ORDER BY id'))]


def _touch(directory, name, when=None):
    path = directory / name
    path.write_bytes(name.encode())
    if when:
        os.utime(path, (when.timestamp(), when.timestamp()))
    return path


def _at(days_ago=0, hours_ago=0):
    return NOW - timedelta(days=days_ago, hours=hours_ago)


def _stamp(moment):
    return moment.strftime(backup.TIMESTAMP)


# --- names ------------------------------------------------------------------------------


@pytest.mark.parametrize('name, kind, fmt, from_rev, to_rev, tag', [
    ('scheduled-20261008T040000Z.dump', 'scheduled', 'dump', None, None, None),
    ('manual-20261008T040000Z-2.sqlite', 'manual', 'sqlite', None, None, None),
    ('premigrate-20261008T040000Z-from-a1b2c3d4e5f6-to-b8e3d5f9a2c4-original.dump', 'premigrate', 'dump', 'a1b2c3d4e5f6', 'b8e3d5f9a2c4', 'original'),
    ('premigrate-20261008T040000Z-from-none-to-abc123-retry12.dump', 'premigrate', 'dump', 'none', 'abc123', 'retry12'),
    ('premigrate-20261008T040000Z-from-aaa-to-bbb-partial.sqlite', 'premigrate', 'sqlite', 'aaa', 'bbb', 'partial'),
    ('prerestore-20261008T040000Z.dump', 'prerestore', 'dump', None, None, None),
    ('media-20261008T040000Z.tar', 'media', 'tar', None, None, None),
])
def test_names_are_parsed(name, kind, fmt, from_rev, to_rev, tag):
    parsed = backup.parse_name(Path(name))
    assert (parsed.kind, parsed.fmt, parsed.from_rev, parsed.to_rev, parsed.tag) == (kind, fmt, from_rev, to_rev, tag)
    assert parsed.created.year == 2026


@pytest.mark.parametrize('name', ['notes.txt', '.scheduled-20261008T040000Z.partial', 'scheduled-2026.dump',
                                  'premigrate-20261008T040000Z.dump', 'other-20261008T040000Z.dump'])
def test_other_files_are_not_backups(name):
    assert backup.parse_name(Path(name)) is None


def test_list_backups_is_newest_first_and_ignores_strangers(tmp_path):
    _touch(tmp_path, f'scheduled-{_stamp(_at(2))}.dump')
    _touch(tmp_path, f'scheduled-{_stamp(_at(0))}.dump')
    _touch(tmp_path, 'README.txt')
    assert [b.created for b in backup.list_backups(tmp_path)] == [_at(0), _at(2)]
    assert backup.list_backups(tmp_path / 'missing') == []


# --- settings -----------------------------------------------------------------------------


def test_settings_defaults_and_overrides():
    defaults = Settings.from_env({})
    assert (defaults.interval_hours, defaults.keep, defaults.media_interval_days) == (24, 7, 0)
    assert defaults.migration_backup is True and defaults.migration_keep == 3
    custom = Settings.from_env({'BACKUP_INTERVAL_HOURS': '6', 'BACKUP_KEEP': '3', 'MIGRATION_BACKUP': 'off',
                                'BACKUP_MEDIA_INTERVAL_DAYS': '7', 'MIGRATION_BACKUPS_KEEP': '5'})
    assert (custom.interval_hours, custom.keep, custom.migration_backup, custom.media_interval_days, custom.migration_keep) \
        == (6, 3, False, 7, 5)
    assert Settings.from_env({'BACKUP_INTERVAL_HOURS': 'soon', 'BACKUP_KEEP': '0'}).keep == 1   # nonsense -> safe values


# --- writing: never overwrite, tight permissions --------------------------------------------


def test_sqlite_backup_roundtrip_with_a_safety_backup(tmp_path):
    engine = _sqlite(tmp_path, rows=('before',))
    directory = tmp_path / 'backups'
    saved = backup.create_db_backup(engine, directory, 'manual', now=NOW)
    assert saved.name == f'manual-{_stamp(NOW)}.sqlite'
    assert stat.S_IMODE(saved.stat().st_mode) == 0o400 and stat.S_IMODE(directory.stat().st_mode) == 0o700

    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO note (text) VALUES ('after')"))
    safety = backup.restore_with_safety_backup(engine, saved, directory)

    assert _notes(engine) == ['before']
    assert safety.name.startswith('prerestore-') and sqlite3.connect(safety).execute('SELECT text FROM note').fetchall() \
        == [('before',), ('after',)]


def test_a_backup_never_replaces_an_existing_file(tmp_path):
    engine = _sqlite(tmp_path)
    directory = tmp_path / 'backups'
    directory.mkdir()
    name = f'manual-{_stamp(NOW)}.sqlite'
    precious = directory / name
    precious.write_bytes(b'precious')
    digest = hashlib.sha256(b'precious').hexdigest()

    written = backup.create_db_backup(engine, directory, 'manual', now=NOW)

    assert written.name == f'manual-{_stamp(NOW)}-1.sqlite'
    assert hashlib.sha256(precious.read_bytes()).hexdigest() == digest
    again = backup.create_db_backup(engine, directory, 'manual', now=NOW)
    assert again.name.endswith('-2.sqlite')
    assert not list(directory.glob('.*.partial'))


def test_a_failed_backup_leaves_no_partial_file(tmp_path, monkeypatch):
    engine = _sqlite(tmp_path)
    directory = tmp_path / 'backups'
    monkeypatch.setattr(backup, '_publish', lambda *a, **k: (_ for _ in ()).throw(BackupError('boom')))
    with pytest.raises(BackupError, match='boom'):
        backup.create_db_backup(engine, directory, 'manual', now=NOW)
    assert list(directory.iterdir()) == []


def test_not_enough_disk_space_stops_before_writing(tmp_path, monkeypatch):
    engine = _sqlite(tmp_path)
    directory = tmp_path / 'backups'
    monkeypatch.setattr(shutil, 'disk_usage', lambda _p: shutil._ntuple_diskusage(100, 100, 10))
    with pytest.raises(BackupError, match='Not enough free space'):
        backup.create_db_backup(engine, directory, 'manual', now=NOW)
    assert list(directory.iterdir()) == []


def test_restore_refuses_files_that_do_not_fit(tmp_path):
    engine = _sqlite(tmp_path)
    junk = tmp_path / 'notes.txt'
    junk.write_text('x')
    with pytest.raises(BackupError, match='not a DisplayHive database backup'):
        backup.restore_db_backup(engine, junk)
    dump = _touch(tmp_path, f'manual-{_stamp(NOW)}.dump')
    with pytest.raises(BackupError, match='cannot be restored into sqlite'):
        backup.restore_db_backup(engine, dump)


def test_postgres_tools_are_required_for_postgres(monkeypatch):
    monkeypatch.setattr(shutil, 'which', lambda _name: None)
    monkeypatch.setattr(Path, 'exists', lambda self: False)
    with pytest.raises(BackupError, match='pg_dump was not found. Install postgresql-client-16'):
        backup._tool('pg_dump', 16)


def test_a_client_of_another_major_version_is_refused(monkeypatch):
    # pg_dump 17 against a version 16 server writes archives that server cannot restore.
    monkeypatch.setattr(Path, 'exists', lambda self: False)
    monkeypatch.setattr(shutil, 'which', lambda _name: '/usr/bin/pg_dump')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a, 0, 'pg_dump (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1)\n', ''))
    with pytest.raises(BackupError, match='is version 17 but the database server is version 16'):
        backup._tool('pg_dump', 16)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a, 0, 'pg_dump (PostgreSQL) 16.15\n', ''))
    assert backup._tool('pg_dump', 16) == '/usr/bin/pg_dump'


def test_the_versioned_debian_directory_is_preferred(monkeypatch):
    monkeypatch.setattr(Path, 'exists', lambda self: str(self) == '/usr/lib/postgresql/16/bin/pg_dump')
    assert backup._tool('pg_dump', 16) == '/usr/lib/postgresql/16/bin/pg_dump'


def test_pg_environment_carries_the_password_not_the_command_line():
    url = sa.engine.make_url('postgresql+psycopg2://dh:s3cret@db.example:5433/displayhive')
    env = backup._pg_env(url)
    assert (env['PGHOST'], env['PGPORT'], env['PGUSER'], env['PGPASSWORD'], env['PGDATABASE']) == \
        ('db.example', '5433', 'dh', 's3cret', 'displayhive')
    socket = backup._pg_env(sa.engine.make_url('postgresql:///displayhive-main?host=/run/postgresql'))
    assert socket['PGHOST'] == '/run/postgresql' and socket['PGDATABASE'] == 'displayhive-main'


def test_media_backup_is_a_tar_of_the_uploads(tmp_path):
    media = tmp_path / 'media'
    (media / 'sub').mkdir(parents=True)
    (media / 'logo.png').write_bytes(b'png')
    (media / 'sub' / 'a.jpg').write_bytes(b'jpg')
    written = backup.create_media_backup(media, tmp_path / 'backups', now=NOW)
    assert written.name == f'media-{_stamp(NOW)}.tar'
    import tarfile
    with tarfile.open(written) as archive:
        assert sorted(archive.getnames()) == ['media', 'media/logo.png', 'media/sub', 'media/sub/a.jpg']


# --- the upgrade backup: original / retry / partial --------------------------------------------


def _pre(tag, from_rev='old', to_rev='new', days_ago=0):
    return Backup(Path(f'premigrate-x-{tag}'), 'premigrate', _at(days_ago), 'dump', from_rev, to_rev, tag)


def test_the_first_backup_of_an_upgrade_is_the_original_and_repeats_are_retries():
    assert backup.plan_premigrate_tag([], 'old', 'new') == 'original'
    existing = [_pre('original')]
    assert backup.plan_premigrate_tag(existing, 'old', 'new') == 'retry1'
    existing.append(_pre('retry1'))
    assert backup.plan_premigrate_tag(existing, 'old', 'new') == 'retry2'


def test_a_database_that_moved_on_is_partial_never_a_new_original():
    existing = [_pre('original'), _pre('retry1')]
    assert backup.plan_premigrate_tag(existing, 'half-way', 'new') == 'partial'
    # a different target is a different upgrade
    assert backup.plan_premigrate_tag(existing, 'new', 'newer') == 'original'


def _make_upgrade(directory, to_rev, days_ago, retries=0, partial=False):
    stamp = lambda extra: _stamp(_at(days_ago, hours_ago=extra))  # noqa: E731
    base = f'premigrate-{stamp(0)}-from-old-to-{to_rev}-'
    _touch(directory, base + 'original.dump')
    for n in range(1, retries + 1):
        _touch(directory, f'premigrate-{stamp(-n)}-from-old-to-{to_rev}-retry{n}.dump')
    if partial:
        _touch(directory, f'premigrate-{stamp(-9)}-from-mid-to-{to_rev}-partial.dump')


def test_pruning_keeps_the_newest_upgrades_and_never_the_original_of_a_kept_one(tmp_path):
    for index, rev in enumerate(['r1', 'r2', 'r3', 'r4', 'r5']):
        _make_upgrade(tmp_path, rev, days_ago=50 - index * 10, retries=3 if rev == 'r5' else 0, partial=(rev == 'r5'))
    removed = backup.prune_premigrate(tmp_path, keep_upgrades=3)

    left = backup.list_backups(tmp_path)
    assert {b.to_rev for b in left} == {'r3', 'r4', 'r5'}          # the three newest upgrades
    assert {b.to_rev for b in removed if b.tag == 'original'} == {'r1', 'r2'}
    assert [b.tag for b in removed if b.to_rev == 'r5'] == ['retry1']       # only the oldest retry of a kept upgrade
    r5 = [b for b in left if b.to_rev == 'r5']
    assert sum(b.tag == 'original' for b in r5) == 1 and sum(b.tag == 'partial' for b in r5) == 1
    assert sorted(b.tag for b in r5 if b.tag.startswith('retry')) == ['retry2', 'retry3']   # newest two


def test_pruning_does_nothing_to_other_kinds(tmp_path):
    _touch(tmp_path, f'scheduled-{_stamp(_at(90))}.dump')
    _touch(tmp_path, f'manual-{_stamp(_at(90))}.dump')
    _make_upgrade(tmp_path, 'r1', 5)
    assert backup.prune_premigrate(tmp_path, keep_upgrades=1) == []
    assert len(backup.list_backups(tmp_path)) == 3


# --- scheduled backups ---------------------------------------------------------------------


def test_scheduled_retention_by_kind(tmp_path):
    for days in range(10):
        _touch(tmp_path, f'scheduled-{_stamp(_at(days))}.dump')
    for days in range(4):
        _touch(tmp_path, f'media-{_stamp(_at(days))}.tar')
    _touch(tmp_path, f'manual-{_stamp(_at(99))}.dump')
    _make_upgrade(tmp_path, 'r1', 99)
    backup.prune_scheduled(tmp_path, Settings(keep=7, media_keep=2))
    kinds = [b.kind for b in backup.list_backups(tmp_path)]
    assert kinds.count('scheduled') == 7 and kinds.count('media') == 2
    assert kinds.count('manual') == 1 and kinds.count('premigrate') == 1      # never touched


def test_backups_are_due_by_interval(tmp_path):
    settings = Settings(interval_hours=24, media_interval_days=7)
    assert backup.database_backup_due(tmp_path, settings, NOW)                # none yet
    _touch(tmp_path, f'scheduled-{_stamp(_at(hours_ago=23))}.dump')
    assert not backup.database_backup_due(tmp_path, settings, NOW)
    _touch(tmp_path, f'scheduled-{_stamp(_at(hours_ago=25) - timedelta(days=1))}.dump')
    assert not backup.database_backup_due(tmp_path, settings, NOW)            # newest counts
    assert backup.media_backup_due(tmp_path, settings, NOW)
    assert not backup.database_backup_due(tmp_path, Settings(interval_hours=0), NOW)
    assert not backup.media_backup_due(tmp_path, Settings(media_interval_days=0), NOW)


def test_run_scheduled_writes_what_is_due_and_prunes(tmp_path):
    engine = _sqlite(tmp_path)
    media = tmp_path / 'media'
    media.mkdir()
    (media / 'a.png').write_bytes(b'x')
    directory = tmp_path / 'backups'
    settings = Settings(keep=2, media_interval_days=1, media_keep=1)
    for hours in (72, 48, 24):
        backup.run_scheduled(engine, directory, media, settings, now=NOW - timedelta(hours=hours))
    kinds = [b.kind for b in backup.list_backups(directory)]
    assert kinds.count('scheduled') == 2 and kinds.count('media') == 1
    assert backup.run_scheduled(engine, directory, media, settings, now=NOW - timedelta(hours=23)) == []   # nothing due


# --- PostgreSQL (CI and anyone with a server and the client tools) ----------------------------

POSTGRES = os.environ.get('TEST_DATABASE_URL', '').startswith('postgresql')


@pytest.mark.skipif(not (POSTGRES and shutil.which('pg_dump') and shutil.which('pg_restore')),
                    reason='needs PostgreSQL (TEST_DATABASE_URL) and pg_dump/pg_restore')
def test_postgres_backup_restore_drops_what_the_backup_does_not_have(tmp_path):
    admin = sa.create_engine(os.environ['TEST_DATABASE_URL'], isolation_level='AUTOCOMMIT')
    name = f'dh_backup_{uuid.uuid4().hex[:8]}'
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE {name}'))
    engine = sa.create_engine(admin.url.set(database=name))
    try:
        with engine.begin() as conn:
            conn.execute(sa.text('CREATE TABLE note (id SERIAL PRIMARY KEY, text TEXT)'))
            conn.execute(sa.text("INSERT INTO note (text) VALUES ('before')"))
        saved = backup.create_db_backup(engine, tmp_path / 'backups', 'manual')
        assert saved.suffix == '.dump' and stat.S_IMODE(saved.stat().st_mode) == 0o400
        with engine.begin() as conn:
            conn.execute(sa.text("INSERT INTO note (text) VALUES ('after')"))
            conn.execute(sa.text('CREATE TABLE added_later (id INT)'))
        backup.restore_with_safety_backup(engine, saved, tmp_path / 'backups')
        assert _notes(engine) == ['before']
        assert 'added_later' not in sa.inspect(engine).get_table_names()
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE {name} WITH (FORCE)'))


@pytest.mark.skipif(not (POSTGRES and shutil.which('pg_dump') and shutil.which('pg_restore') and shutil.which('psql')),
                    reason='needs PostgreSQL (TEST_DATABASE_URL) and its client tools')
def test_a_failing_postgres_restore_changes_nothing(tmp_path):
    admin = sa.create_engine(os.environ['TEST_DATABASE_URL'], isolation_level='AUTOCOMMIT')
    name = f'dh_atomic_{uuid.uuid4().hex[:8]}'
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE {name}'))
    engine = sa.create_engine(admin.url.set(database=name))
    try:
        with engine.begin() as conn:
            conn.execute(sa.text('CREATE TABLE note (id SERIAL PRIMARY KEY, text TEXT)'))
            conn.execute(sa.text("INSERT INTO note (text) VALUES ('precious')"))
        broken = tmp_path / 'backups' / f'manual-{_stamp(NOW)}.dump'
        broken.parent.mkdir()
        broken.write_bytes(b'PGDMP not really a dump')
        with pytest.raises(BackupError):
            backup.restore_db_backup(engine, broken)
        assert _notes(engine) == ['precious']                  # not even the schema was touched
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE {name} WITH (FORCE)'))
