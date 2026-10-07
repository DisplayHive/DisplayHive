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


def verify_password(password: str, password_hash: str) -> bool:
    """Return True if *password* matches *password_hash*."""
    try:
        return check_password_hash(password_hash, password)
    except Exception:
        return False


# --- JWT ---------------------------------------------------------------------


def create_token(app, user, impersonator_id=None) -> str:
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
    exempt: the admin driving one is not the person who has to pick the
    new password.
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
    if user.must_change_password and not allow_pending_password_change and 'imp' not in payload:
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
_MAX_ATTEMPTS = 5            # failures inside the window before lockout kicks in
_WINDOW_SECONDS = 900       # sliding window of failures considered (15 min)
_BASE_LOCKOUT_SECONDS = 60  # lockout after the first over-threshold failure
_MAX_LOCKOUT_SECONDS = 3600  # cap on the escalating lockout (1 h)
_failed_attempts: dict[str, list[float]] = {}


def _lockout_seconds(over_threshold: int) -> int:
    """Return the lockout length for *over_threshold* failures beyond the limit.

    Escalates exponentially (60s, 120s, 240s, …) and is capped at
    ``_MAX_LOCKOUT_SECONDS`` so sustained brute force is throttled hard rather
    than merely delayed by a fixed 60s each round.
    """
    return min(_BASE_LOCKOUT_SECONDS * (2 ** max(0, over_threshold)), _MAX_LOCKOUT_SECONDS)


def is_rate_limited(key: str) -> bool:
    """Return True if *key* (e.g. "ip:username") has failed login too many times recently."""
    now = time.time()
    attempts = [t for t in _failed_attempts.get(key, []) if now - t < _WINDOW_SECONDS]
    _failed_attempts[key] = attempts
    if len(attempts) < _MAX_ATTEMPTS:
        return False
    # Lockout window grows with each additional failure past the threshold.
    lockout = _lockout_seconds(len(attempts) - _MAX_ATTEMPTS)
    return (now - attempts[-1]) < lockout


def record_failed_attempt(key: str) -> None:
    """Record a failed login attempt for *key*."""
    _failed_attempts.setdefault(key, []).append(time.time())


def clear_failed_attempts(key: str) -> None:
    """Clear failed-attempt tracking for *key* after a successful login."""
    _failed_attempts.pop(key, None)
