"""/healthz and /readyz (application/web/health.py)."""

import pytest
from sqlalchemy import create_engine, text

from application.web import health


@pytest.fixture()
def client(flask_app):
    return flask_app.app.test_client()


def test_healthz_is_ok_and_not_cached(client):
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}
    assert response.headers['Cache-Control'] == 'no-store'


def test_healthz_does_not_touch_the_database(client, monkeypatch):
    def boom(db):
        raise AssertionError('healthz must not check readiness')
    monkeypatch.setattr(health, 'readiness', boom)
    assert client.get('/healthz').status_code == 200


def test_readyz_is_ready_on_the_test_database(client):
    response = client.get('/readyz')
    assert response.status_code == 200
    body = response.get_json()
    assert body['status'] == 'ok' and body['checks']['database'] == 'ok'
    assert body['checks']['migrations'] in ('head', 'untracked')


def test_readyz_is_503_when_not_ready(client, monkeypatch):
    monkeypatch.setattr(health, 'readiness', lambda db: (False, {'database': 'error', 'migrations': 'error'}))
    response = client.get('/readyz')
    assert response.status_code == 503
    assert response.get_json() == {'status': 'unavailable', 'checks': {'database': 'error', 'migrations': 'error'}}


def test_readiness_survives_an_unreachable_database(flask_app, monkeypatch):
    class BrokenDb:
        class engine:  # noqa: N801
            @staticmethod
            def connect():
                raise RuntimeError('database is down')
    ready, checks = health.readiness(BrokenDb)
    assert ready is False
    assert checks == {'database': 'error', 'migrations': 'error'}
    assert 'down' not in str(checks)


def test_the_code_has_exactly_one_migration_head():
    assert len(health._migration_heads()) == 1


def _sqlite_connection(version=None):
    engine = create_engine('sqlite://')
    conn = engine.connect()
    if version is not None:
        conn.execute(text('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)'))
        conn.execute(text('INSERT INTO alembic_version VALUES (:v)'), {'v': version})
    return conn


def test_migration_state_head():
    heads = health._migration_heads()
    with _sqlite_connection(next(iter(heads))) as conn:
        assert health.migration_state(conn, heads) == 'head'


def test_migration_state_behind_when_the_revision_is_old():
    with _sqlite_connection('0000000000') as conn:
        assert health.migration_state(conn, health._migration_heads()) == 'behind'


def test_migration_state_untracked_on_a_create_all_sqlite_file():
    with _sqlite_connection() as conn:
        assert health.migration_state(conn, health._migration_heads()) == 'untracked'


def test_migration_state_behind_when_a_non_sqlite_database_was_never_migrated(monkeypatch):
    class Conn:
        dialect = type('Dialect', (), {'name': 'postgresql'})

    class NoTables:
        def has_table(self, name):
            return False

    monkeypatch.setattr('sqlalchemy.inspect', lambda conn: NoTables())
    assert health.migration_state(Conn(), health._migration_heads()) == 'behind'
