"""Copying a whole database (application/core/dbcopy.py, `flask dh copy-database`)."""

import os
import uuid

import pytest
import sqlalchemy as sa

from application.admin.importexport.importer import import_database
from application.core.dbcopy import CopyError, copy_database
from application.core.factory import create_app
from application.models import db
from tests.admin.test_importexport_roundtrip import _example_payload


def _engine(tmp_path, name):
    return sa.create_engine(f'sqlite:///{tmp_path / name}')


@pytest.fixture()
def source(tmp_path):
    """A SQLite database holding the example content, plus a user and a group tree."""
    url = f"sqlite:///{tmp_path / 'source.db'}"
    app, _ = create_app({'SQLALCHEMY_DATABASE_URI': url, 'SQLITE_IN_USE': True, 'TESTING': True}, startup=False)
    with app.app_context():
        db.create_all()
    assert import_database(app, db, _example_payload(), mode='reset').get('success')
    with app.app_context():
        from application.models import AdminUser, Group, SystemSetting
        # The child has the smaller id, so a plain read returns it before its parent:
        # the copy must order parents first.
        db.session.add(Group(id=20, name='parent'))
        db.session.commit()
        db.session.add(Group(id=10, name='child', parent_group_id=20))
        db.session.add(AdminUser(username='alice', password_hash='x'))
        db.session.add(SystemSetting(id=900, key='seed', value='1'))   # explicit id: the sequence must continue after it
        db.session.commit()
    return sa.create_engine(url)


def _dump(engine):
    with engine.connect() as conn:
        out = {}
        for table in db.metadata.sorted_tables:
            if sa.inspect(engine).has_table(table.name):
                rows = [dict(r) for r in conn.execute(sa.select(table)).mappings()]
                out[table.name] = sorted(rows, key=lambda r: sorted((k, str(v)) for k, v in r.items()))
        return out


def test_copy_between_sqlite_files_is_exact_and_replaces_the_target(tmp_path, source):
    target = _engine(tmp_path, 'target.db')
    db.metadata.create_all(target)
    with target.begin() as conn:   # pre-existing target content must disappear
        conn.execute(db.metadata.tables['system_setting'].insert().values(key='stale', value='x'))
    counts = copy_database(source, target, db.metadata)

    assert _dump(target) == _dump(source)
    assert counts['admin_user'] == 1 and counts['group'] == 2 and counts['content_element'] > 0


def test_parents_are_inserted_before_children(tmp_path, source):
    target = _engine(tmp_path, 'fk.db')
    db.metadata.create_all(target)
    with target.connect() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys = ON')
    copy_database(source, target, db.metadata)
    with target.connect() as conn:
        child = conn.execute(sa.text("SELECT parent_group_id FROM \"group\" WHERE name = 'child'")).scalar()
    assert child == 20


def test_a_failure_leaves_the_target_untouched(tmp_path, source):
    target = _engine(tmp_path, 'keep.db')
    db.metadata.create_all(target)
    with source.begin() as conn:    # an orphan: points at a screen that does not exist
        conn.exec_driver_sql('PRAGMA foreign_keys = OFF')
        conn.execute(db.metadata.tables['device'].insert().values(devicekey='orphan', screen_id=99999, is_active=True))
    with target.begin() as conn:
        conn.execute(db.metadata.tables['system_setting'].insert().values(key='keep-me', value='x'))
    with target.connect() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys = ON')
    # SQLite only enforces foreign keys when asked to; enable it on the target for this test.
    sa.event.listen(target, 'connect', lambda c, _r: c.execute('PRAGMA foreign_keys = ON'))
    target.dispose()
    with pytest.raises(CopyError, match='point at rows that do not exist'):
        copy_database(source, target, db.metadata)
    with target.connect() as conn:
        assert conn.execute(sa.text("SELECT count(*) FROM system_setting WHERE key = 'keep-me'")).scalar() == 1


def test_upgrade_to_head_migrates_the_given_engine_not_database_url(tmp_path):
    from application.cli import _revision_of, _upgrade_to_head
    from application.web.health import _migration_heads

    old = _engine(tmp_path, 'old.db')
    assert _revision_of(old) is None
    _upgrade_to_head(old)
    assert {_revision_of(old)} == set(_migration_heads())
    assert 'admin_user' in sa.inspect(old).get_table_names()


def test_missing_tables_in_the_target_are_reported(tmp_path, source):
    with pytest.raises(CopyError, match='alembic upgrade head'):
        copy_database(source, _engine(tmp_path, 'empty.db'), db.metadata)


@pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL', '').startswith('postgresql'),
                    reason='needs PostgreSQL (TEST_DATABASE_URL)')
def test_copy_into_postgresql_keeps_ids_usable(tmp_path, source):
    admin = sa.create_engine(os.environ['TEST_DATABASE_URL'], isolation_level='AUTOCOMMIT')
    name = f'dh_copy_{uuid.uuid4().hex[:8]}'
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE {name}'))
    target = sa.create_engine(admin.url.set(database=name))
    try:
        db.metadata.create_all(target)
        copy_database(source, target, db.metadata)
        # Booleans and datetimes survived the trip, and new rows get fresh ids (no collision):
        # the sequences continue after the copied ids.
        assert _dump(target) == _dump(source)
        setting = db.metadata.tables['system_setting']
        with target.begin() as conn:
            highest = conn.execute(sa.select(sa.func.max(setting.c.id))).scalar() or 0
            new_id = conn.execute(
                setting.insert().values(key='after-copy', value='x').returning(setting.c.id)
            ).scalar()
        assert new_id == highest + 1
    finally:
        target.dispose()
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE {name} WITH (FORCE)'))


# --- The data of plugins ----------------------------------------------------------------------------

PRETALX = ('CREATE TABLE pretalx_api_url (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL, url TEXT NOT NULL, '
           'polling_enabled BOOLEAN NOT NULL DEFAULT 0, polling_interval INTEGER NOT NULL DEFAULT 300)')
PRETALX_CACHE = ('CREATE TABLE pretalx_api_cache (id INTEGER PRIMARY KEY, api_url_id INTEGER NOT NULL REFERENCES pretalx_api_url(id), '
                 'cached_json TEXT NOT NULL)')
PLG = 'CREATE TABLE plg_acme_demo_note (id INTEGER PRIMARY KEY, text VARCHAR(50))'


def _with_plugin_tables(engine, *statements):
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(sa.text(statement))


def test_the_tables_of_plugins_are_copied_too(tmp_path, source):
    _with_plugin_tables(source, PRETALX, PRETALX_CACHE, PLG,
                        "INSERT INTO pretalx_api_url (id, name, url, polling_enabled) VALUES (3, 'Main', 'https://x', 1)",
                        "INSERT INTO pretalx_api_cache (id, api_url_id, cached_json) VALUES (1, 3, '{}')",
                        "INSERT INTO plg_acme_demo_note (id, text) VALUES (1, 'hello')")
    target = _engine(tmp_path, 'target.db')
    db.metadata.create_all(target)
    _with_plugin_tables(target, PRETALX, PRETALX_CACHE, PLG,
                        "INSERT INTO plg_acme_demo_note (id, text) VALUES (9, 'stale')")
    counts = copy_database(source, target, db.metadata, plugin_tables={'pretalx_api_url', 'pretalx_api_cache'})
    assert counts['pretalx_api_url'] == 1 and counts['pretalx_api_cache'] == 1 and counts['plg_acme_demo_note'] == 1
    with target.connect() as conn:
        assert conn.execute(sa.text('SELECT name, polling_enabled FROM pretalx_api_url')).fetchall() == [('Main', 1)]
        assert conn.execute(sa.text('SELECT api_url_id FROM pretalx_api_cache')).fetchall() == [(3,)]
        assert conn.execute(sa.text('SELECT id, text FROM plg_acme_demo_note')).fetchall() == [(1, 'hello')]   # the stale row is gone


def test_a_plugin_table_the_target_lacks_stops_the_copy_before_anything_is_deleted(tmp_path, source):
    _with_plugin_tables(source, PLG, "INSERT INTO plg_acme_demo_note (id, text) VALUES (1, 'hello')")
    target = _engine(tmp_path, 'target.db')
    db.metadata.create_all(target)
    with target.begin() as conn:
        conn.execute(db.metadata.tables['system_setting'].insert().values(key='keep', value='x'))
    with pytest.raises(CopyError, match='plg_acme_demo_note.*start DisplayHive once'):
        copy_database(source, target, db.metadata)
    with target.connect() as conn:
        assert conn.execute(sa.select(db.metadata.tables['system_setting'].c.key)).scalar() == 'keep'


def test_a_table_nobody_owns_is_still_only_reported(tmp_path, source):
    _with_plugin_tables(source, 'CREATE TABLE leftover (id INTEGER PRIMARY KEY)')
    target = _engine(tmp_path, 'target.db')
    db.metadata.create_all(target)
    said = []
    copy_database(source, target, db.metadata, echo=said.append)
    assert any('leftover' in line and 'Not copied' in line for line in said)
