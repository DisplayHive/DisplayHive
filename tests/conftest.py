"""Shared pytest fixtures for the backend test suite.

`app.py` builds the default `app`/`db`/`socketio` with
`application.factory.create_app()` and — as a server — fully bootstraps the DB
(create_all + bootstrap admin + right sync + superadmin group) when it is
imported, driven by env vars. For the bulk of the suite:

  - The env vars below must be set before the very first `import app`.
  - Python imports a module once per process, so those tests share the *same*
    default app/db/engine instance.

Isolation there comes from wrapping each test in a SQLAlchemy
connection-level transaction (with a SAVEPOINT so code under test can still
call `db.session.commit()`/`rollback()` without escaping it), rolled back in
teardown. A real temp SQLite file (not `:memory:`) is used for DATABASE_URL so
every connection the engine opens sees the same database — `:memory:` is
per-connection unless the engine is explicitly configured with StaticPool,
which the app doesn't do (it's built for a real file or Postgres).

Tests that need a genuinely separate app (own database, no startup work) build
one with `create_app({...}, startup=False)` — see `tests/test_factory.py`.
"""

import atexit
import os
import tempfile
import uuid

_tmp_db_fd, _tmp_db_path = tempfile.mkstemp(prefix='displayhive_pytest_', suffix='.db')
os.close(_tmp_db_fd)
atexit.register(lambda: os.path.exists(_tmp_db_path) and os.unlink(_tmp_db_path))

# The tests' database is explicit (DATABASE_URL is required): a temp SQLite file,
# or TEST_DATABASE_URL (the CI PostgreSQL job). It always overrides DATABASE_URL,
# so a developer's own dev database is never touched by the suite.
os.environ['DATABASE_URL'] = os.environ.get('TEST_DATABASE_URL') or f'sqlite:///{_tmp_db_path}'

# Keep media/staging written by tests out of the checkout — and out of a
# developer's real legacy static/media (application/paths.py would otherwise
# fall back to it): point both DATA_DIR and the legacy lookup at temp dirs.
import shutil  # noqa: E402
_tmp_data_dir = tempfile.mkdtemp(prefix='displayhive_pytest_data_')
_tmp_app_root = tempfile.mkdtemp(prefix='displayhive_pytest_root_')
atexit.register(lambda: shutil.rmtree(_tmp_data_dir, ignore_errors=True))
atexit.register(lambda: shutil.rmtree(_tmp_app_root, ignore_errors=True))
os.environ.setdefault('DATA_DIR', _tmp_data_dir)

import application.paths  # noqa: E402
application.paths.APP_ROOT = _tmp_app_root
os.environ.setdefault('SECRET_KEY', 'test-secret-key-not-for-production')
os.environ.setdefault('ADMIN_BOOTSTRAP_USERNAME', 'testadmin')
os.environ.setdefault('ADMIN_BOOTSTRAP_PASSWORD', 'test-admin-password')
os.environ.setdefault('LOG_LEVEL', 'WARNING')

import pytest

import app as app_module  # noqa: E402 — must import after the env vars above are set


def _make_pysqlite_transactions_real():
    """Make the per-test SAVEPOINT isolation (db_session below) actually hold.

    pysqlite doesn't emit BEGIN when SQLAlchemy starts a transaction, so the
    test's outer transaction never really opened: the SAVEPOINT the code
    under test commits into was the outermost one, and SQLite turns
    RELEASE of an outermost SAVEPOINT into a real COMMIT — every committing
    test silently leaked rows into the shared test database. This is
    SQLAlchemy's documented fix ("Serializable isolation / Savepoints /
    Transactional DDL" in its SQLite dialect docs): turn off pysqlite's own
    transaction handling and emit BEGIN ourselves.
    """
    from sqlalchemy import event

    with app_module.app.app_context():
        engine = app_module.db.engine
    if engine.dialect.name != 'sqlite':
        return
    engine.dispose()  # connections opened during app startup lack the hook

    @event.listens_for(engine, 'connect')
    def _disable_pysqlite_transactions(dbapi_connection, connection_record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, 'begin')
    def _emit_begin(conn):
        conn.exec_driver_sql('BEGIN')


_make_pysqlite_transactions_real()


@pytest.fixture(scope='session')
def flask_app():
    """The already-bootstrapped `app.py` module (app/db/socketio + first-run setup)."""
    return app_module


@pytest.fixture()
def app_ctx(flask_app):
    """Push a Flask app context for tests that need `current_app.config` but no DB."""
    ctx = flask_app.app.app_context()
    ctx.push()
    try:
        yield flask_app.app
    finally:
        ctx.pop()


@pytest.fixture()
def db_session(flask_app):
    """A DB session scoped to a single test: changes made during the test are
    visible to code under test, but are rolled back afterward and never
    committed to the real (temp) database file."""
    db = flask_app.db
    ctx = flask_app.app.app_context()
    ctx.push()
    engines = db._app_engines[flask_app.app]
    engine = engines[None]
    connection = engine.connect()
    transaction = connection.begin()
    # Flask-SQLAlchemy's Session.get_bind() ignores `session.bind` and always
    # picks the app's engine — so route every session (including the ones
    # test-client requests and socket handlers open in their own app
    # context) through this connection by swapping it in as that engine.
    engines[None] = connection
    db.session.configure(join_transaction_mode='create_savepoint')
    try:
        yield db.session
    finally:
        db.session.remove()
        engines[None] = engine
        transaction.rollback()
        connection.close()
        ctx.pop()


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """`application.auth._failed_attempts` is process-global mutable state
    (an in-memory login-rate-limiter dict) — clear it before and after every
    test so failures in one test can't affect another."""
    import application.auth as auth_module
    auth_module._failed_attempts.clear()
    auth_module._last_sweep = 0.0
    yield
    auth_module._failed_attempts.clear()
    auth_module._last_sweep = 0.0


@pytest.fixture()
def make_user(db_session):
    """Factory fixture: create+commit an AdminUser with sensible defaults."""
    from application.models import AdminUser
    from application.auth import hash_password

    def _make(username=None, password='testpass123', is_active=True, token_version=0):
        if username is None:
            username = f'user-{uuid.uuid4().hex[:8]}'
        user = AdminUser(
            username=username,
            password_hash=hash_password(password),
            is_active=is_active,
            token_version=token_version,
        )
        db_session.add(user)
        db_session.commit()
        return user

    return _make


@pytest.fixture()
def make_group(db_session):
    """Factory fixture: create+commit a Group, optionally nested under *parent*."""
    from application.models import Group

    def _make(name=None, parent=None, is_superadmin=False):
        if name is None:
            name = f'group-{uuid.uuid4().hex[:8]}'
        group = Group(
            name=name,
            parent_group_id=parent.id if parent is not None else None,
            is_superadmin=is_superadmin,
        )
        db_session.add(group)
        db_session.commit()
        return group

    return _make


@pytest.fixture()
def get_right(db_session):
    """Look up a RightDefinition row by key.

    Real right keys (see application.permissions.RIGHTS) already exist —
    app.py's module-level startup runs sync_right_definitions() on import —
    so tests exercising real rights (e.g. 'media.page') just look them up
    rather than creating them.
    """
    from sqlalchemy import select
    from application.models import RightDefinition

    def _get(key):
        return db_session.execute(
            select(RightDefinition).where(RightDefinition.key == key)
        ).scalar_one_or_none()

    return _get
