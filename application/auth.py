"""Core authentication primitives: password hashing, JWT issuing/verification,
first-run admin bootstrap, and a lightweight login rate limiter.

Used by both the HTTP login route (application/admin/auth/routes.py) and the
Socket.IO connect handler (application/admin/devices/connection.py) so admin
sessions are backed by a single shared token format.
"""

import os
import secrets
import time
from datetime import datetime, timedelta, timezone

import jwt
from werkzeug.security import generate_password_hash, check_password_hash

TOKEN_ALGORITHM = 'HS256'
TOKEN_TTL = timedelta(hours=12)

# --- Password hashing -------------------------------------------------------


def hash_password(password: str) -> str:
    """Return a salted hash of *password* suitable for storage."""
    return generate_password_hash(password)


MIN_PASSWORD_LENGTH = 8


def password_problem(password: str) -> str | None:
    """Why *password* isn't acceptable as a new password, or None if it is.

    The one place the password rules live — the Users page, the forced
    password change and the `flask dh` CLI all go through it.
    """
    if len(password or '') < MIN_PASSWORD_LENGTH:
        return f'Password must be at least {MIN_PASSWORD_LENGTH} characters'
    return None


def verify_password(password: str, password_hash: str) -> bool:
    """Return True if *password* matches *password_hash*."""
    try:
        return check_password_hash(password_hash, password)
    except Exception:
        return False


# --- JWT ---------------------------------------------------------------------


def create_token(app, user, impersonator_id=None, auth_method='password') -> str:
    """Issue a signed JWT for *user* (an AdminUser instance).

    If *impersonator_id* is given, the token is an impersonation session:
    it authenticates as *user* (so they get exactly *user*'s rights) but
    carries an 'imp' claim recording who is really driving it. Since the
    token is signed, a client cannot forge or strip this claim — it is what
    lets the server refuse to let an impersonation session start another
    impersonation (see application.socketio_handlers.auth.is_impersonating).
    """
    now = datetime.now(timezone.utc)
    payload = {
        # 'sub' must be a string per RFC 7519 — PyJWT rejects a bare int on decode.
        'sub': str(user.id),
        'username': user.username,
        # Token version at issue time; a later bump (e.g. password change)
        # invalidates this token. See user_from_token().
        'tv': int(getattr(user, 'token_version', 0) or 0),
        'iat': now,
        'exp': now + TOKEN_TTL,
    }
    if impersonator_id is not None:
        payload['imp'] = int(impersonator_id)
    if auth_method == 'oidc':
        # Signed, so a client can't add it: lets user_from_token() skip the
        # password-only must_change_password lock for SSO sessions.
        payload['am'] = 'oidc'
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm=TOKEN_ALGORITHM)


def decode_token(app, token: str):
    """Return the decoded payload dict for *token*, or None if invalid/expired."""
    if not token:
        return None
    try:
        return jwt.decode(token, app.config['SECRET_KEY'], algorithms=[TOKEN_ALGORITHM])
    except jwt.PyJWTError:
        return None


def user_from_token(app, db, token: str, allow_pending_password_change: bool = False):
    """Resolve *token* to a currently-valid AdminUser, or return None.

    Rejects the token if it is missing/expired/invalid, the user no longer
    exists or is deactivated, or it was issued before the user's current
    ``token_version`` (e.g. the password has since been changed). This is the
    single authorization gate shared by the HTTP routes and the Socket.IO
    connect handler so a revoked session cannot linger until its TTL expires.

    An account flagged ``must_change_password`` is also rejected unless
    *allow_pending_password_change* is set — only the self-service session
    check and password-change routes pass it, so such a session can do
    nothing else until a new password is chosen. Impersonation tokens are
    exempt (the admin driving one is not the person who has to pick the
    new password), and so are SSO sessions (the flag is about the account's
    password, which an SSO login didn't use).
    """
    payload = decode_token(app, token)
    if not payload:
        return None
    from application.models import AdminUser
    try:
        user = db.session.get(AdminUser, int(payload.get('sub')))
    except (TypeError, ValueError):
        return None
    if not user or not user.is_active:
        return None
    if int(payload.get('tv', 0) or 0) != int(getattr(user, 'token_version', 0) or 0):
        return None
    if (user.must_change_password and not allow_pending_password_change
            and 'imp' not in payload and payload.get('am') != 'oidc'):
        return None
    return user


# --- First-run bootstrap -----------------------------------------------------


def ensure_bootstrap_admin(app, db):
    """Create a default admin user on first run if no AdminUser rows exist.

    Username/password can be pinned via ADMIN_BOOTSTRAP_USERNAME /
    ADMIN_BOOTSTRAP_PASSWORD (useful for tests and scripted deployments).
    Otherwise a random password is generated and printed once so the
    operator can log in and change it via the Users page.
    """
    from application.models import AdminUser

    if db.session.execute(db.select(AdminUser)).first() is not None:
        return

    username = os.environ.get('ADMIN_BOOTSTRAP_USERNAME', 'admin')
    password = os.environ.get('ADMIN_BOOTSTRAP_PASSWORD')
    generated = password is None
    if generated:
        password = secrets.token_urlsafe(12)

    user = AdminUser(username=username, password_hash=hash_password(password), is_active=True)
    db.session.add(user)
    db.session.commit()

    if generated:
        banner = '*' * 70
        print(banner)
        print('[auth] No admin users found — created a bootstrap account:')
        print(f'[auth]   username: {username}')
        print(f'[auth]   password: {password}')
        print('[auth] Log in and change this password from the Users page.')
        print(banner)
    else:
        print(f"[auth] Created bootstrap admin user '{username}' from ADMIN_BOOTSTRAP_PASSWORD")


# --- Login rate limiting ------------------------------------------------------

# In-memory only. This matches the rest of the app, which keeps its Socket.IO
# presence/room state (connected_devices, connected_screens, log history) in
# process-local dicts and is therefore designed to run as a single worker.
# State resets on restart.
#
# Two counters are kept per failed login (see record_failed_login): one per
# IP+username, and one per IP across all usernames. The per-IP one has a
# higher threshold and stops a single client from trying one password against
# many accounts, which the per-account counter alone can't see.
#
# Once a counter reaches its threshold it is locked for _lockout_seconds(n),
# and every further failure re-locks it for twice as long (up to the cap).
# That escalation is only forgiven after a full quiet _WINDOW_SECONDS following
# the last lockout, so locks longer than the window still escalate.


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


_MAX_ATTEMPTS = 5            # failures per IP+username inside the window before lockout
_IP_MAX_ATTEMPTS = _env_int('LOGIN_RATE_LIMIT_PER_IP', 20)  # failures per IP, any username
_WINDOW_SECONDS = 900       # sliding window of failures considered (15 min)
_BASE_LOCKOUT_SECONDS = 60  # lockout after the first over-threshold failure
_MAX_LOCKOUT_SECONDS = 3600  # cap on the escalating lockout (1 h)
_SWEEP_INTERVAL_SECONDS = 60  # how often expired keys are swept out, at most
_MAX_TRACKED_KEYS = 50_000   # memory bound against floods from many sources


class _Attempts:
    """Rate-limiter state for one key."""
    __slots__ = ('failures', 'strikes', 'locked_until')

    def __init__(self):
        self.failures: list[float] = []  # failure timestamps inside the window
        self.strikes = 0                 # lockouts so far; drives the escalation
        self.locked_until = 0.0


_failed_attempts: dict[str, _Attempts] = {}
_last_sweep = 0.0


def _lockout_seconds(over_threshold: int) -> int:
    """Return the lockout length for *over_threshold* failures beyond the limit.

    Escalates exponentially (60s, 120s, 240s, …) and is capped at
    ``_MAX_LOCKOUT_SECONDS`` so sustained brute force is throttled hard rather
    than merely delayed by a fixed 60s each round.
    """
    return min(_BASE_LOCKOUT_SECONDS * (2 ** max(0, over_threshold)), _MAX_LOCKOUT_SECONDS)


def _prune(entry: _Attempts, now: float) -> bool:
    """Drop *entry*'s failures outside the window; return True once it has
    fully expired (nothing in the window, no lockout, quiet period over)."""
    entry.failures = [t for t in entry.failures if now - t < _WINDOW_SECONDS]
    return not entry.failures and now >= entry.locked_until + _WINDOW_SECONDS


def _sweep(now: float) -> None:
    """Remove expired keys from every entry, not just the one being looked at.

    Without this, a key nobody asks about again (a mistyped or made-up
    username) would stay in memory until restart. Runs at most once per
    _SWEEP_INTERVAL_SECONDS, unless the hard key cap is exceeded.
    """
    global _last_sweep
    if now - _last_sweep < _SWEEP_INTERVAL_SECONDS and len(_failed_attempts) <= _MAX_TRACKED_KEYS:
        return
    _last_sweep = now
    for key in [k for k, entry in _failed_attempts.items() if _prune(entry, now)]:
        del _failed_attempts[key]
    excess = len(_failed_attempts) - _MAX_TRACKED_KEYS
    if excess > 0:
        # Still over the cap (failures from very many sources): evict the
        # least recently failed keys that aren't locked. Locked keys are never
        # evicted, so a flood can't be used to lift someone's lockout.
        unlocked = sorted(
            (entry.failures[-1] if entry.failures else 0.0, key)
            for key, entry in _failed_attempts.items()
            if now >= entry.locked_until
        )
        for _, key in unlocked[:excess]:
            del _failed_attempts[key]


def is_rate_limited(key: str) -> bool:
    """Return True if *key* is currently locked out after too many failures."""
    now = time.time()
    _sweep(now)
    entry = _failed_attempts.get(key)
    if entry is None:
        return False
    if _prune(entry, now):
        del _failed_attempts[key]
        return False
    return now < entry.locked_until


def record_failed_attempt(key: str, max_attempts: int = _MAX_ATTEMPTS) -> None:
    """Record a failed attempt for *key*, locking it once *max_attempts*
    failures fall inside the window (and again, longer, on every failure after)."""
    now = time.time()
    _sweep(now)
    entry = _failed_attempts.get(key)
    if entry is None or _prune(entry, now):
        entry = _failed_attempts[key] = _Attempts()
    entry.failures.append(now)
    if entry.strikes or len(entry.failures) >= max_attempts:
        entry.locked_until = now + _lockout_seconds(entry.strikes)
        entry.strikes += 1


def clear_failed_attempts(key: str) -> None:
    """Clear failed-attempt tracking for *key* after a successful login."""
    _failed_attempts.pop(key, None)


def _login_keys(ip: str | None, username: str) -> tuple[str, str]:
    return f'user:{ip}:{(username or "").lower()}', f'ip:{ip}'


def is_login_rate_limited(ip: str | None, username: str) -> bool:
    """True if either this IP+username or this IP as a whole is locked out."""
    account_key, ip_key = _login_keys(ip, username)
    return is_rate_limited(account_key) or is_rate_limited(ip_key)


def record_failed_login(ip: str | None, username: str) -> None:
    """Count a failed login (or current-password check) against both counters."""
    account_key, ip_key = _login_keys(ip, username)
    record_failed_attempt(account_key)
    record_failed_attempt(ip_key, max_attempts=_IP_MAX_ATTEMPTS)


def clear_failed_login(ip: str | None, username: str) -> None:
    """Reset the IP+username counter after a successful login.

    The per-IP counter is deliberately left alone: otherwise an attacker with
    one valid account of their own could reset it between guesses at others.
    """
    account_key, _ = _login_keys(ip, username)
    clear_failed_attempts(account_key)
