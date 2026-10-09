"""application/migration.py and `flask dh migrate|backup|backups|restore`:
back up first, protect the original, stop clearly on failure."""

import hashlib
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from application import backup, migration
from application.backup import Settings
from application.factory import create_app
from application.migration import MigrationFailed

ROOT = Path(__file__).resolve().parents[1]
OLD_REVISION = '9c5e1f3a7b42'


def _upgrade(engine, revision):
    config = Config(str(ROOT / 'alembic.ini'))
    config.set_main_option('script_location', str(ROOT / 'migrations'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, revision)


@pytest.fixture(scope='module')
def old_database(tmp_path_factory):
    """A SQLite file migrated up to an older revision, holding one row."""
    path = tmp_path_factory.mktemp('old') / 'old.db'
    engine = sa.create_engine(f'sqlite:///{path}')
    _upgrade(engine, OLD_REVISION)
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO system_setting (key, value) VALUES ('kept', 'yes')"))
    engine.dispose()
    return path


@pytest.fixture()
def engine(tmp_path, old_database):
    copy = tmp_path / 'live.db'
    shutil.copy(old_database, copy)
    engine = sa.create_engine(f'sqlite:///{copy}')
    yield engine
    engine.dispose()


def _revision(engine):
    return migration.current_revisions(engine)


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _failing_upgrade(engine):
    raise RuntimeError('column already exists')


SETTINGS = Settings()


# --- migrate() ----------------------------------------------------------------------------


def test_a_new_database_is_created_without_a_backup(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'new.db'}")
    result = migration.migrate(engine, tmp_path / 'backups', SETTINGS, echo=lambda _m: None)
    assert result.status == 'initialized' and result.backup_path is None
    assert _revision(engine) == migration.heads()
    assert backup.list_backups(tmp_path / 'backups') == []


def test_an_old_database_is_backed_up_then_migrated(tmp_path, engine):
    directory = tmp_path / 'backups'
    result = migration.migrate(engine, directory, SETTINGS, echo=lambda _m: None)

    assert result.status == 'upgraded' and _revision(engine) == migration.heads()
    assert result.backup_path.name.endswith(f'-from-{OLD_REVISION}-to-{next(iter(migration.heads()))}-original.sqlite')
    saved = sqlite3.connect(result.backup_path)                       # the backup is the OLD state, with the data
    assert saved.execute('SELECT version_num FROM alembic_version').fetchall() == [(OLD_REVISION,)]
    assert saved.execute("SELECT value FROM system_setting WHERE key = 'kept'").fetchall() == [('yes',)]


def test_an_up_to_date_database_is_left_alone(tmp_path, engine):
    migration.migrate(engine, tmp_path / 'backups', SETTINGS, echo=lambda _m: None)
    before = backup.list_backups(tmp_path / 'backups')
    assert migration.migrate(engine, tmp_path / 'backups', SETTINGS, echo=lambda _m: None).status == 'uptodate'
    assert backup.list_backups(tmp_path / 'backups') == before


def test_no_migration_happens_when_the_backup_fails(tmp_path, engine, monkeypatch):
    def broken(*_a, **_k):
        raise backup.BackupError('disk full')
    monkeypatch.setattr(backup, 'create_premigrate_backup', broken)
    with pytest.raises(MigrationFailed, match='nothing was migrated: disk full'):
        migration.migrate(engine, tmp_path / 'backups', SETTINGS, echo=lambda _m: None)
    assert _revision(engine) == {OLD_REVISION}


def test_a_failed_migration_names_the_backup(tmp_path, engine):
    with pytest.raises(MigrationFailed, match='column already exists') as error:
        migration.migrate(engine, tmp_path / 'backups', SETTINGS, echo=lambda _m: None, upgrade=_failing_upgrade)
    assert error.value.backup_path.exists() and error.value.backup_path.name.endswith('-original.sqlite')


def test_the_original_survives_retries_and_a_partial_state(tmp_path, engine):
    directory = tmp_path / 'backups'
    run = lambda **kw: migration.migrate(engine, directory, SETTINGS, echo=lambda _m: None, **kw)  # noqa: E731

    with pytest.raises(MigrationFailed) as first:
        run(upgrade=_failing_upgrade)
    original = first.value.backup_path
    digest = _digest(original)

    with pytest.raises(MigrationFailed) as second:                    # same state again: a retry
        run(upgrade=_failing_upgrade)
    assert second.value.backup_path.name.endswith('-retry1.sqlite')

    with engine.begin() as conn:                                      # a half-applied migration moved the revision on
        conn.execute(sa.text("UPDATE alembic_version SET version_num = 'a7d2c4e8f1b3'"))
    with pytest.raises(MigrationFailed) as third:
        run(upgrade=_failing_upgrade)
    assert third.value.backup_path.name.endswith('-partial.sqlite')

    assert original.exists() and _digest(original) == digest           # never replaced
    assert sqlite3.connect(original).execute('SELECT version_num FROM alembic_version').fetchall() == [(OLD_REVISION,)]


def test_old_upgrade_backups_are_only_pruned_after_a_success(tmp_path, engine):
    directory = tmp_path / 'backups'
    for _ in range(4):                                                # four failed attempts: original + retry1..3
        with pytest.raises(MigrationFailed):
            migration.migrate(engine, directory, SETTINGS, echo=lambda _m: None, upgrade=_failing_upgrade)
    assert len(backup.list_backups(directory)) == 4                   # nothing pruned while failing

    migration.migrate(engine, directory, SETTINGS, echo=lambda _m: None)   # backs up once more (retry4), succeeds
    tags = sorted(b.tag for b in backup.list_backups(directory))
    assert tags == ['original', 'retry3', 'retry4']                   # the original, and the newest two retries


def test_the_backup_can_be_switched_off(tmp_path, engine):
    off = Settings.from_env({'MIGRATION_BACKUP': 'off'})
    result = migration.migrate(engine, tmp_path / 'backups', off, echo=lambda _m: None)
    assert result.status == 'upgraded' and result.backup_path is None
    assert backup.list_backups(tmp_path / 'backups') == []


def test_an_unreachable_database_is_a_migration_failure(tmp_path):
    engine = sa.create_engine('sqlite:////nonexistent-directory/x.db')
    with pytest.raises(MigrationFailed, match='not reachable'):
        migration.migrate(engine, tmp_path, SETTINGS, echo=lambda _m: None)


# --- the commands ------------------------------------------------------------------------------


@pytest.fixture()
def cli(tmp_path, old_database):
    """A factory app on its own copy of the old database, and a CLI runner for it."""
    database = tmp_path / 'cli.db'
    shutil.copy(old_database, database)
    app, _ = create_app({
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{database}', 'SQLITE_IN_USE': True, 'TESTING': True,
        'BACKUP_DIR': str(tmp_path / 'backups'), 'MEDIA_FOLDER': str(tmp_path / 'media'),
    }, startup=False)
    return app, app.test_cli_runner(), database


def test_migrate_command_succeeds_and_reports(cli):
    app, runner, database = cli
    result = runner.invoke(args=['dh', 'migrate'])
    assert result.exit_code == 0, result.output
    assert 'Backup written' in result.output and 'up to date' in result.output


def test_migrate_command_exits_78_and_names_the_backup_when_it_fails(cli, monkeypatch):
    app, runner, database = cli
    monkeypatch.setattr(migration, 'upgrade_to_head', _failing_upgrade)
    result = runner.invoke(args=['dh', 'migrate'])
    assert result.exit_code == migration.EXIT_FAILED == 78
    assert 'MIGRATION FAILED' in result.output and 'dh restore premigrate-' in result.output


def test_migrate_command_logs_instead_of_printing_in_json_mode(cli, monkeypatch, caplog):
    import logging
    app, runner, database = cli
    monkeypatch.setenv('LOG_FORMAT', 'json')
    monkeypatch.setattr(migration, 'upgrade_to_head', _failing_upgrade)
    with caplog.at_level(logging.INFO, logger='application.migration'):
        result = runner.invoke(args=['dh', 'migrate'])
    assert result.exit_code == 78 and result.output == ''                      # nothing printed outside the log
    messages = [(r.levelname, r.getMessage()) for r in caplog.records if r.name == 'application.migration']
    assert ('INFO', 'Backing up the database before migrating...') in messages
    assert any(level == 'ERROR' and 'Migration failed' in m for level, m in messages)
    assert any(level == 'ERROR' and 'flask dh restore premigrate-' in m for level, m in messages)


def test_backup_backups_and_restore_commands(cli):
    app, runner, database = cli
    made = runner.invoke(args=['dh', 'backup'])
    assert made.exit_code == 0 and 'Written:' in made.output
    name = backup.list_backups(app.config['BACKUP_DIR'])[0].path.name
    assert name in runner.invoke(args=['dh', 'backups']).output

    with sqlite3.connect(database) as conn:
        conn.execute("DELETE FROM system_setting")
    restored = runner.invoke(args=['dh', 'restore', name, '--yes'])
    assert restored.exit_code == 0, restored.output
    assert sqlite3.connect(database).execute("SELECT value FROM system_setting WHERE key = 'kept'").fetchall() == [('yes',)]
    assert any(b.kind == 'prerestore' for b in backup.list_backups(app.config['BACKUP_DIR']))


def test_restore_command_reports_a_bad_file(cli):
    app, runner, database = cli
    result = runner.invoke(args=['dh', 'restore', 'nope.sqlite', '--yes'])
    assert result.exit_code != 0 and 'not a DisplayHive database backup' in result.output


# --- the Docker entrypoint -----------------------------------------------------------------------


def _entrypoint(tmp_path, flask_exit, env=None):
    """Run docker-entrypoint.sh with a fake `flask` and `gunicorn` on the PATH."""
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir(exist_ok=True)
    log = tmp_path / 'calls.log'
    log.write_text('')
    (bin_dir / 'flask').write_text(f'#!/bin/sh\necho "flask $@" >> {log}\nexit {flask_exit}\n')
    (bin_dir / 'gunicorn').write_text(f'#!/bin/sh\necho "gunicorn $@" >> {log}\n')
    for tool in bin_dir.iterdir():
        tool.chmod(0o755)
    result = subprocess.run(['sh', str(ROOT / 'docker-entrypoint.sh'), *(env or {}).pop('args', [])],
                            env={'PATH': f'{bin_dir}:/usr/bin:/bin', **(env or {})}, capture_output=True, text=True)
    return result, log.read_text().splitlines()


def test_entrypoint_starts_the_app_after_a_successful_migration(tmp_path):
    result, calls = _entrypoint(tmp_path, 0)
    assert result.returncode == 0 and calls[0] == 'flask dh migrate' and calls[1].startswith('gunicorn ')
    assert '--log-config-json' not in calls[1]


def test_entrypoint_does_not_start_the_app_when_the_migration_fails(tmp_path):
    result, calls = _entrypoint(tmp_path, 78)
    assert result.returncode == 78 and calls == ['flask dh migrate']     # no gunicorn
    assert 'Not starting' in result.stderr


def test_entrypoint_can_skip_the_migration_for_a_separate_migrate_service(tmp_path):
    result, calls = _entrypoint(tmp_path, 78, {'MIGRATE_ON_START': '0'})
    assert result.returncode == 0 and len(calls) == 1 and calls[0].startswith('gunicorn ')


def test_entrypoint_migrate_mode_only_migrates(tmp_path):
    result, calls = _entrypoint(tmp_path, 0, {'args': ['migrate']})
    assert result.returncode == 0 and calls == ['flask dh migrate']


def test_entrypoint_json_logging_covers_gunicorn_and_its_own_lines(tmp_path):
    import json
    result, calls = _entrypoint(tmp_path, 0, {'LOG_FORMAT': 'json'})
    assert '--log-config-json /app/gunicorn-logging.json' in calls[1]
    lines = [json.loads(line) for line in result.stdout.strip().splitlines()]
    assert [l['logger'] for l in lines] == ['entrypoint', 'entrypoint'] and lines[0]['level'] == 'INFO'


def test_entrypoint_failure_line_is_json_too(tmp_path):
    import json
    result, _calls = _entrypoint(tmp_path, 78, {'LOG_FORMAT': 'json'})
    error = json.loads(result.stderr.strip().splitlines()[-1])
    assert error['level'] == 'ERROR' and 'Not starting' in error['message'] and '78' in error['message']
