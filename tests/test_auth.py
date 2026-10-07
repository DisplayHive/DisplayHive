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
    begin_login_attempt,
    finish_login_attempt,
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


@pytest.fixture()
def clock(monkeypatch):
    """A controllable time.time() for the rate limiter: `clock.now += 60`."""
    import application.auth as auth_module

    class _Clock:
        now = 1_000_000.0

    c = _Clock()
    monkeypatch.setattr(auth_module.time, 'time', lambda: c.now)
    return c


def test_is_rate_limited_does_not_create_entries():
    import application.auth as auth_module
    assert is_rate_limited('ip:never-failed') is False
    assert 'ip:never-failed' not in auth_module._failed_attempts


def test_lockout_escalates_past_the_window_up_to_the_cap(clock):
    """Each failure after the threshold doubles the lock, and that escalation
    survives locks longer than the 15-minute window (up to the 1 h cap)."""
    import application.auth as auth_module

    key = 'ip:escalating'
    for _ in range(5):
        record_failed_attempt(key)
    expected = [60, 120, 240, 480, 960, 1920, 3600, 3600]
    for lock in expected:
        clock.now += lock - 1
        assert is_rate_limited(key) is True
        clock.now += 1
        assert is_rate_limited(key) is False
        record_failed_attempt(key)
    assert auth_module._failed_attempts[key].locked_until - clock.now == 3600


def test_escalation_is_forgiven_after_a_quiet_window(clock):
    import application.auth as auth_module

    key = 'ip:forgiven'
    for _ in range(5):
        record_failed_attempt(key)
    clock.now += 60 + auth_module._WINDOW_SECONDS
    assert is_rate_limited(key) is False
    assert key not in auth_module._failed_attempts
    # A fresh start: four more failures are below the threshold again.
    for _ in range(4):
        record_failed_attempt(key)
    assert is_rate_limited(key) is False


def test_sweep_removes_expired_keys_nobody_asks_about_again(clock):
    import application.auth as auth_module

    for i in range(10):
        record_failed_attempt(f'user:1.2.3.4:typo-{i}')
    assert len(auth_module._failed_attempts) == 10
    clock.now += auth_module._WINDOW_SECONDS + 1
    is_rate_limited('user:5.6.7.8:someone-else')
    assert auth_module._failed_attempts == {}


def test_key_cap_evicts_unlocked_keys_but_never_locked_ones(clock, monkeypatch):
    import application.auth as auth_module

    monkeypatch.setattr(auth_module, '_MAX_TRACKED_KEYS', 3)
    for _ in range(5):
        record_failed_attempt('locked')
    for i in range(5):
        clock.now += 1
        record_failed_attempt(f'single-{i}')
    assert 'locked' in auth_module._failed_attempts
    assert is_rate_limited('locked') is True
    assert len(auth_module._failed_attempts) <= 4


# --- Login rate limiting (per IP + username, and per IP) ------------------------


def test_per_ip_limit_stops_spraying_across_usernames():
    import application.auth as auth_module

    for i in range(auth_module._IP_MAX_ATTEMPTS):
        assert begin_login_attempt('1.2.3.4', f'victim-{i}') is not None  # counted as a failure
    # Every single username is still below its own threshold, but the IP is out.
    assert begin_login_attempt('1.2.3.4', 'yet-another-user') is None
    assert begin_login_attempt('5.6.7.8', 'yet-another-user') is not None


def test_per_account_limit_still_applies_below_the_ip_threshold():
    for _ in range(5):
        begin_login_attempt('1.2.3.4', 'Admin')
    assert begin_login_attempt('1.2.3.4', 'admin') is None
    assert begin_login_attempt('1.2.3.4', 'someone-else') is not None


def test_successful_login_keeps_the_ip_counter_but_is_not_counted_itself():
    """A valid account of the attacker's own must not reset the IP counter."""
    import application.auth as auth_module

    for i in range(auth_module._IP_MAX_ATTEMPTS - 1):
        begin_login_attempt('1.2.3.4', f'victim-{i}')
    own = begin_login_attempt('1.2.3.4', 'attackers-own-account')
    finish_login_attempt(own, success=True)
    # The success took only its own count back: one more failure locks the IP.
    assert begin_login_attempt('1.2.3.4', 'victim-last') is not None
    assert begin_login_attempt('1.2.3.4', 'anyone') is None


def test_successful_login_resets_its_account_counter():
    for _ in range(4):
        begin_login_attempt('1.2.3.4', 'alice')
    finish_login_attempt(begin_login_attempt('1.2.3.4', 'alice'), success=True)
    for _ in range(4):
        assert begin_login_attempt('1.2.3.4', 'alice') is not None


def test_parallel_guesses_cannot_slip_past_the_limit():
    """Many threads trying the same account at once: only 5 get to check a password."""
    import threading
    import time as _time

    allowed = []
    start = threading.Barrier(40)

    def guess():
        start.wait()
        attempt = begin_login_attempt('9.9.9.9', 'victim')
        if attempt is not None:
            allowed.append(attempt)
            _time.sleep(0.05)  # "hashing the password", with the GIL released

    threads = [threading.Thread(target=guess) for _ in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(allowed) == 5


def test_limiter_survives_concurrent_sweeps(monkeypatch):
    """_sweep() iterates the whole dict; other threads insert meanwhile."""
    import threading
    import application.auth as auth_module

    monkeypatch.setattr(auth_module, '_SWEEP_INTERVAL_SECONDS', 0)  # sweep on every call
    errors = []

    def hammer(n):
        try:
            for i in range(300):
                auth_module.record_failed_attempt(f'user:{n}:{i}')
                auth_module.is_rate_limited(f'user:{n}:{i // 2}')
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=hammer, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


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


def test_user_from_token_rejects_pending_password_change(flask_app, app_ctx, db_session, make_user):
    user = make_user()
    token = create_token(app_ctx, user)
    user.must_change_password = True
    db_session.commit()
    assert user_from_token(app_ctx, flask_app.db, token) is None
    resolved = user_from_token(app_ctx, flask_app.db, token, allow_pending_password_change=True)
    assert resolved is not None and resolved.id == user.id


def test_user_from_token_impersonation_ignores_pending_password_change(flask_app, app_ctx, db_session, make_user):
    """The admin driving an impersonation isn't the one who has to pick the password."""
    admin = make_user()
    target = make_user()
    target.must_change_password = True
    db_session.commit()
    token = create_token(app_ctx, target, impersonator_id=admin.id)
    assert user_from_token(app_ctx, flask_app.db, token) is not None


# --- Forced password change (HTTP) -------------------------------------------------


def _login(client, username, password='testpass123'):
    return client.post('/admin/api/auth/login', json={'username': username, 'password': password})


def test_login_reports_pending_password_change_and_locks_session(flask_app, db_session, make_user):
    user = make_user()
    user.must_change_password = True
    db_session.commit()
    client = flask_app.app.test_client()

    result = _login(client, user.username).get_json()
    assert result['success'] is True
    assert result['must_change_password'] is True
    headers = {'Authorization': f"Bearer {result['token']}"}

    me = client.get('/admin/api/auth/me', headers=headers)
    assert me.status_code == 200
    assert me.get_json()['must_change_password'] is True
    # Anything other than the password-change routes is refused.
    prefs = client.patch('/admin/api/auth/me/preferences', headers=headers, json={'preferences': {'theme': 'dark'}})
    assert prefs.status_code == 401


def test_change_password_clears_flag_and_issues_new_token(flask_app, db_session, make_user):
    user = make_user()
    user.must_change_password = True
    db_session.commit()
    client = flask_app.app.test_client()
    old_token = _login(client, user.username).get_json()['token']

    response = client.post(
        '/admin/api/auth/me/password',
        headers={'Authorization': f'Bearer {old_token}'},
        json={'current_password': 'testpass123', 'new_password': 'brand-new-pass'},
    )
    result = response.get_json()
    assert response.status_code == 200 and result['success'] is True

    db_session.refresh(user)
    assert user.must_change_password is False
    assert verify_password('brand-new-pass', user.password_hash)
    # The old token is revoked; the returned one works everywhere.
    assert user_from_token(flask_app.app, flask_app.db, old_token, allow_pending_password_change=True) is None
    me = client.get('/admin/api/auth/me', headers={'Authorization': f"Bearer {result['token']}"})
    assert me.get_json()['must_change_password'] is False


@pytest.mark.parametrize('current, new, error', [
    ('wrong-password', 'brand-new-pass', 'Current password is incorrect'),
    ('testpass123', 'short', 'Password must be at least 8 characters'),
    ('testpass123', 'testpass123', 'New password must differ from the current one'),
])
def test_change_password_rejects_invalid_input(flask_app, db_session, make_user, current, new, error):
    user = make_user()
    user.must_change_password = True
    db_session.commit()
    client = flask_app.app.test_client()
    token = _login(client, user.username).get_json()['token']

    response = client.post(
        '/admin/api/auth/me/password',
        headers={'Authorization': f'Bearer {token}'},
        json={'current_password': current, 'new_password': new},
    )
    assert response.status_code == 400
    assert response.get_json()['error'] == error
    db_session.refresh(user)
    assert user.must_change_password is True


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
