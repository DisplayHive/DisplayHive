"""Shared pytest fixtures for the backend test suite.

`app.py` has no `create_app()` factory — it builds `app`/`db`/`socketio` and
fully bootstraps the DB (create_all + bootstrap admin + right sync +
superadmin group) at *module import time*, driven by env vars. So:

  - The env vars below must be set before the very first `import app`.
  - Because Python only imports a module once per process, every test in
    this whole pytest run shares the *same* app/db/engine instance — there
    is no per-test app factory to call.

Test isolation therefore comes from wrapping each test in a SQLAlchemy
connection-level transaction (with a SAVEPOINT so code under test can still
call `db.session.commit()`/`rollback()` without escaping it), rolled back in
teardown, rather than from separate app instances. A real temp SQLite file
(not `:memory:`) is used for TEST_DB_PATH so every connection the engine
opens sees the same database — `:memory:` is per-connection unless the
engine is explicitly configured with StaticPool, which app.py doesn't do
(it's built for a real file or Postgres).
"""

import atexit
import os
import tempfile
import uuid

_tmp_db_fd, _tmp_db_path = tempfile.mkstemp(prefix='displayhive_pytest_', suffix='.db')
os.close(_tmp_db_fd)
atexit.register(lambda: os.path.exists(_tmp_db_path) and os.unlink(_tmp_db_path))

os.environ.setdefault('TEST_DB_PATH', _tmp_db_path)
os.environ.setdefault('SECRET_KEY', 'test-secret-key-not-for-production')
os.environ.setdefault('ADMIN_BOOTSTRAP_USERNAME', 'testadmin')
os.environ.setdefault('ADMIN_BOOTSTRAP_PASSWORD', 'test-admin-password')
os.environ.setdefault('LOG_LEVEL', 'WARNING')

import pytest

import app as app_module  # noqa: E402 — must import after the env vars above are set


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
    connection = db.engine.connect()
    transaction = connection.begin()
    db.session.configure(bind=connection, join_transaction_mode='create_savepoint')
    try:
        yield db.session
    finally:
        db.session.remove()
        transaction.rollback()
        connection.close()
        db.session.configure(bind=db.engine)
        ctx.pop()


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """`application.auth._failed_attempts` is process-global mutable state
    (an in-memory login-rate-limiter dict) — clear it before and after every
    test so failures in one test can't affect another."""
    from application.auth import _failed_attempts
    _failed_attempts.clear()
    yield
    _failed_attempts.clear()


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
