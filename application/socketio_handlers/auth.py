"""Shared authorization helpers for Socket.IO handlers."""

import logging
from functools import wraps

logger = logging.getLogger(__name__)


# Per-connection registry of the JWT each admin socket authenticated with,
# keyed by session id (sid). Populated by the connect handler when an admin
# token is accepted and cleared on disconnect. This lets require_admin()
# re-validate the token on every event instead of trusting 'admins' room
# membership for the whole life of the socket — so an admin who is deleted,
# deactivated, or whose password changed (token_version bump) loses access on
# their *next* action rather than lingering until the socket happens to drop.
_admin_sessions: dict[str, str] = {}


def register_admin_session(sid: str, token: str) -> None:
    """Record the JWT an admin socket authenticated with, keyed by session id."""
    if sid and token:
        _admin_sessions[sid] = token


def clear_admin_session(sid: str) -> None:
    """Forget an admin socket's token. Called from the disconnect handler."""
    if sid:
        _admin_sessions.pop(sid, None)


def require_admin() -> bool:
    """Return True only if the current socket is a still-valid authenticated admin.

    Two conditions must hold:
      1. the socket joined the 'admins' room at connect (server-side state a
         client cannot forge), and
      2. the token it presented at connect is *still* valid right now — the
         account has not since been deleted, deactivated, or had its password
         changed (see application.auth.user_from_token).

    Fails closed: any error resolving the token denies the action.

    Prefer the @admin_handler decorator over calling this directly.
    """
    try:
        from flask import request, current_app
        from flask_socketio import rooms

        if 'admins' not in rooms():
            return False

        sid = getattr(request, 'sid', None)
        token = _admin_sessions.get(sid)
        if not token:
            return False

        from application.models import db
        from application.auth import user_from_token
        return user_from_token(current_app._get_current_object(), db, token) is not None
    except Exception:
        return False


def resolve_admin_user(sid: str):
    """Return the still-valid AdminUser authenticated on socket *sid*, or None.

    Unlike require_admin()/current_admin_user(), this takes an explicit sid
    rather than reading it off the current request context, so it can be used
    to resolve *other* connected admin sockets (e.g. when masking a broadcast
    payload per-recipient — see application/admin/devices/helper.py).
    """
    token = _admin_sessions.get(sid)
    if not token:
        return None
    try:
        from flask import current_app
        from application.models import db
        from application.auth import user_from_token
        return user_from_token(current_app._get_current_object(), db, token)
    except Exception:
        return None


def current_admin_user():
    """Return the AdminUser authenticated on the *current* request's socket, or None."""
    try:
        from flask import request
        return resolve_admin_user(getattr(request, 'sid', None))
    except Exception:
        return None


def is_impersonating() -> bool:
    """True if the current socket authenticated with an impersonation token.

    An impersonation token authenticates as the target user but carries a
    signed 'imp' claim (see application.auth.create_token) recording who
    actually started the session. Used to refuse chaining — an impersonated
    session can't itself start another impersonation, even if the target
    user happens to also hold special.impersonate.
    """
    try:
        from flask import request, current_app
        sid = getattr(request, 'sid', None)
        token = _admin_sessions.get(sid)
        if not token:
            return False
        from application.auth import decode_token
        payload = decode_token(current_app._get_current_object(), token)
        return bool(payload and payload.get('imp') is not None)
    except Exception:
        return False


def require_right(right_key: str):
    """Decorator factory: admin-only Socket.IO handler that also requires *right_key*.

    Combines admin_handler's authentication + exception-safety with a
    permission check (application.permissions.has_right). Denies (silently,
    matching admin_handler's convention) if the caller is not a valid admin
    or lacks the right — this is the actual security boundary; any
    frontend-side hiding of buttons/pages is UX only and must not be relied on.

    Usage:
        @socketio.on('displayhive:media:cts:upload')
        @require_right('media.upload')
        def handle_upload(data): ...

    Note this replaces @admin_handler (do not stack both).
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not require_admin():
                return None
            try:
                from application.models import db
                from application.permissions import has_right
                user = current_admin_user()
                if not has_right(db, user, right_key):
                    return None
                return fn(*args, **kwargs)
            except Exception:
                logger.exception("Unhandled error in admin handler %s", fn.__name__)
                try:
                    from application.models import db
                    db.session.rollback()
                except Exception:
                    pass
                return None
        return wrapper
    return decorator


def require_any_right(*right_keys: str):
    """Like require_right, but grants access if the caller holds *any* of the
    given rights (e.g. a feature reachable via either of two roles' rights).
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not require_admin():
                return None
            try:
                from application.models import db
                from application.permissions import has_right
                user = current_admin_user()
                if not any(has_right(db, user, k) for k in right_keys):
                    return None
                return fn(*args, **kwargs)
            except Exception:
                logger.exception("Unhandled error in admin handler %s", fn.__name__)
                try:
                    from application.models import db
                    db.session.rollback()
                except Exception:
                    pass
                return None
        return wrapper
    return decorator


def admin_handler(fn):
    """Decorator for admin-only Socket.IO handlers.

    Wraps a handler so it:
      1. runs only for a still-valid authenticated admin (see require_admin),
         silently ignoring the event otherwise, and
      2. never lets an unhandled exception escape into the Socket.IO server —
         it is logged (with traceback) and the DB session is rolled back so a
         failed transaction cannot poison the next event on the shared session.

    Replaces the `if not require_admin(): return` + broad `try/except:
    traceback.print_exc()` boilerplate that every admin handler used to repeat.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not require_admin():
            return None
        try:
            return fn(*args, **kwargs)
        except Exception:
            logger.exception("Unhandled error in admin handler %s", fn.__name__)
            try:
                from application.models import db
                db.session.rollback()
            except Exception:
                pass
            return None
    return wrapper


def fields(message, *names):
    """Extract named fields from a Socket.IO message payload.

    Returns a tuple of `message[name]` for each name (or None when the payload
    is not a dict / a key is missing). Collapses the repeated
    `x = message.get('x') if isinstance(message, dict) else None` idiom:

        screengroup_id, screen_id = fields(message, 'screengroup_id', 'screen_id')

    A single requested field still returns a 1-tuple, so unpack accordingly:
        (name,) = fields(message, 'name')
    """
    data = message if isinstance(message, dict) else {}
    return tuple(data.get(name) for name in names)
