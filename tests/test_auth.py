"""Tests for application/auth.py: password hashing, JWT issuing/verification,
first-run admin bootstrap, and the login rate limiter."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from application.auth import (
    TOKEN_ALGORITHM,
    _lockout_seconds,
    clear_failed_attempts,
    create_token,
    decode_token,
    ensure_bootstrap_admin,
    hash_password,
    is_rate_limited,
    record_failed_attempt,
    user_from_token,
    verify_password,
)


# --- Password hashing --------------------------------------------------------


def test_hash_and_verify_password_roundtrip():
    hashed = hash_password('correct horse battery staple')
    assert verify_password('correct horse battery staple', hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password('correct horse battery staple')
    assert verify_password('wrong password', hashed) is False


def test_verify_password_rejects_garbage_hash_without_raising():
    assert verify_password('anything', 'not-a-real-hash') is False


# --- Lockout backoff math -----------------------------------------------------


def test_lockout_seconds_base_case():
    assert _lockout_seconds(0) == 60


def test_lockout_seconds_escalates_exponentially():
    assert _lockout_seconds(1) == 120
    assert _lockout_seconds(2) == 240
    assert _lockout_seconds(3) == 480


def test_lockout_seconds_caps_at_max():
    assert _lockout_seconds(10) == 3600
    assert _lockout_seconds(1000) == 3600


def test_lockout_seconds_clamps_negative_input():
    assert _lockout_seconds(-5) == 60


# --- Rate limiting -------------------------------------------------------------


def test_is_rate_limited_false_under_threshold():
    key = 'ip:under-threshold'
    for _ in range(4):
        record_failed_attempt(key)
    assert is_rate_limited(key) is False


def test_is_rate_limited_true_at_threshold():
    key = 'ip:at-threshold'
    for _ in range(5):
        record_failed_attempt(key)
    assert is_rate_limited(key) is True


def test_clear_failed_attempts_resets_state():
    key = 'ip:cleared'
    for _ in range(5):
        record_failed_attempt(key)
    assert is_rate_limited(key) is True
    clear_failed_attempts(key)
    assert is_rate_limited(key) is False


def test_is_rate_limited_prunes_attempts_outside_window(monkeypatch):
    import application.auth as auth_module

    key = 'ip:stale-attempts'
    now = 1_000_000.0
    monkeypatch.setattr(auth_module.time, 'time', lambda: now)
    for _ in range(5):
        record_failed_attempt(key)

    # Jump forward past the sliding window — the old failures should no
    # longer count, so the key is not rate-limited anymore.
    monkeypatch.setattr(auth_module.time, 'time', lambda: now + auth_module._WINDOW_SECONDS + 1)
    assert is_rate_limited(key) is False


# --- JWT -----------------------------------------------------------------------


def test_create_and_decode_token_roundtrip(app_ctx, make_user):
    user = make_user(token_version=0)
    token = create_token(app_ctx, user)
    payload = decode_token(app_ctx, token)
    assert payload is not None
    assert payload['sub'] == str(user.id)
    assert payload['username'] == user.username
    assert payload['tv'] == 0
    assert 'imp' not in payload


def test_create_token_carries_impersonator_claim(app_ctx, make_user):
    admin = make_user()
    target = make_user()
    token = create_token(app_ctx, target, impersonator_id=admin.id)
    payload = decode_token(app_ctx, token)
    assert payload['imp'] == admin.id
    assert payload['sub'] == str(target.id)


def test_decode_token_returns_none_for_garbage():
    assert decode_token(None, '') is None


def test_decode_token_returns_none_for_garbage_string(app_ctx):
    assert decode_token(app_ctx, 'not-a-real-jwt') is None


def test_decode_token_returns_none_for_expired_token(app_ctx):
    now = datetime.now(timezone.utc)
    payload = {
        'sub': '1',
        'username': 'expired',
        'tv': 0,
        'iat': now - timedelta(hours=13),
        'exp': now - timedelta(hours=1),
    }
    token = jwt.encode(payload, app_ctx.config['SECRET_KEY'], algorithm=TOKEN_ALGORITHM)
    assert decode_token(app_ctx, token) is None


def test_decode_token_returns_none_for_wrong_secret(app_ctx, make_user):
    user = make_user()
    token = create_token(app_ctx, user)
    # Decoding against a different secret must fail closed, not raise.
    class _FakeApp:
        config = {'SECRET_KEY': 'a-completely-different-secret'}

    assert decode_token(_FakeApp(), token) is None


def test_user_from_token_valid(flask_app, app_ctx, db_session, make_user):
    user = make_user()
    token = create_token(app_ctx, user)
    resolved = user_from_token(app_ctx, flask_app.db, token)
    assert resolved is not None
    assert resolved.id == user.id


def test_user_from_token_rejects_deactivated_user(flask_app, app_ctx, db_session, make_user):
    user = make_user(is_active=True)
    token = create_token(app_ctx, user)
    user.is_active = False
    db_session.commit()
    assert user_from_token(app_ctx, flask_app.db, token) is None


def test_user_from_token_rejects_stale_token_version(flask_app, app_ctx, db_session, make_user):
    """The core 'password change revokes existing sessions' mechanism."""
    user = make_user(token_version=0)
    token = create_token(app_ctx, user)
    # Simulate a password change bumping the token_version.
    user.token_version = 1
    db_session.commit()
    assert user_from_token(app_ctx, flask_app.db, token) is None


def test_user_from_token_rejects_deleted_user(flask_app, app_ctx, db_session, make_user):
    user = make_user()
    token = create_token(app_ctx, user)
    db_session.delete(user)
    db_session.commit()
    assert user_from_token(app_ctx, flask_app.db, token) is None


def test_user_from_token_none_for_empty_token(flask_app, app_ctx, db_session):
    assert user_from_token(app_ctx, flask_app.db, '') is None


# --- First-run bootstrap -------------------------------------------------------


def test_ensure_bootstrap_admin_is_idempotent(flask_app, app_ctx, db_session):
    """A bootstrap admin already exists (app.py's own module-level startup
    creates one on import) — calling ensure_bootstrap_admin again must not
    create a second one."""
    from sqlalchemy import select
    from application.models import AdminUser

    before = db_session.execute(select(AdminUser)).scalars().all()
    assert len(before) >= 1

    ensure_bootstrap_admin(app_ctx, flask_app.db)

    after = db_session.execute(select(AdminUser)).scalars().all()
    assert len(after) == len(before)


def test_ensure_bootstrap_admin_creates_user_when_none_exist(flask_app, app_ctx, db_session, monkeypatch):
    from sqlalchemy import select
    from application.models import AdminUser

    # Remove every user within this test's transaction (rolled back after).
    for user in db_session.execute(select(AdminUser)).scalars().all():
        db_session.delete(user)
    db_session.commit()
    assert db_session.execute(select(AdminUser)).scalars().all() == []

    monkeypatch.setenv('ADMIN_BOOTSTRAP_USERNAME', 'fresh-admin')
    monkeypatch.setenv('ADMIN_BOOTSTRAP_PASSWORD', 'fresh-password')

    ensure_bootstrap_admin(app_ctx, flask_app.db)

    users = db_session.execute(select(AdminUser)).scalars().all()
    assert len(users) == 1
    assert users[0].username == 'fresh-admin'
