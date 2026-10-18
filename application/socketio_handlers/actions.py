"""Building blocks for admin Socket.IO handlers that answer with an acknowledgement.

A handler that changes something used to repeat the same few lines: load the row, answer
``{'success': False, 'error': '… not found'}`` if it is missing, do the work, and
``rollback()`` before every early ``return`` that follows a half-done change. With
``admin_action`` and ``Fail`` that becomes::

    @socketio.on('displayhive:admin:users:cts:delete_user')
    @admin_action('users.delete')
    def handle_delete_user(data):
        user = get_or_fail(db, AdminUser, fields(data, 'id')[0], 'User')
        if count_users() <= 1:
            raise Fail('Cannot delete the last remaining admin user')
        db.session.delete(user)
        db.session.commit()
        return ok()

* ``raise Fail('message')`` — the caller gets ``{'success': False, 'error': 'message'}`` and the
  session is rolled back, so nothing written before the check survives.
* Two admins changing the same rows at once (``StaleDataError``) get a plain "changed by someone
  else, reload" answer instead of an unexpected-error one.
* An unexpected exception is logged with its traceback and a short reference, the session is rolled
  back and the caller gets ``{'success': False, 'error': 'Unexpected server error (reference …) …',
  'error_ref': '…'}`` — the reference is also in the log line, so a report from a user can be found
  (``require_right`` answered ``None``, which a page cannot tell from "no answer yet").
* A socket that is not a valid admin gets no answer at all (as before). An admin who lacks the
  right gets ``{'success': False, 'error': 'Permission denied'}``.

Whatever the handler returns is passed on unchanged, so handlers that answer by emitting an event
(or return nothing) keep working.
"""

import logging
import uuid
from functools import wraps

from sqlalchemy.orm.exc import ObjectDeletedError, StaleDataError

from application.socketio_handlers.auth import current_admin_user, require_admin

logger = logging.getLogger(__name__)

PERMISSION_DENIED = 'Permission denied'


def new_error_reference() -> str:
    """A short id that goes into both the log line and the answer, to find one from the other."""
    return uuid.uuid4().hex[:8]


def unexpected_error_message(reference: str) -> str:
    return f'Unexpected server error (reference {reference}) — the details are in the server log.'
CONCURRENT_CHANGE = 'This was changed or deleted by someone else at the same moment — reload and try again'


class Fail(Exception):
    """Stop the handler and answer the caller with this error message."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def ok(**extra) -> dict:
    """The success acknowledgement: ``{'success': True, **extra}``."""
    return {'success': True, **extra}


def failure(message: str) -> dict:
    """The failure acknowledgement, for code that returns instead of raising."""
    return {'success': False, 'error': message}


def internal_failure(reference: str) -> dict:
    """The answer for an exception nobody expected: what to tell, and which log line to look for."""
    return {'success': False, 'error': unexpected_error_message(reference), 'error_ref': reference}


def _as_primary_key(model, ident):
    """*ident* in the type of the model's primary key, or raise ValueError/TypeError.

    PostgreSQL refuses a non-number for an integer column with a database error (SQLite
    just finds nothing), so a made-up id is turned away before it gets to the database.
    """
    from sqlalchemy import inspect
    columns = inspect(model).primary_key
    if len(columns) == 1 and getattr(columns[0].type, 'python_type', None) is int:
        if isinstance(ident, bool) or isinstance(ident, float):
            raise TypeError('not an id')
        return int(ident)
    return ident


def get_or_fail(db, model, ident, label: str = 'Item'):
    """``db.session.get(model, ident)``, or ``Fail`` when no id was sent or the row is gone.

    ``ident`` may arrive as a string from the client; a value that is not an id is "not found".
    """
    if ident is None or ident == '':
        raise Fail('Missing id')
    try:
        row = db.session.get(model, _as_primary_key(model, ident))
    except (TypeError, ValueError):
        row = None
    if row is None:
        raise Fail(f'{label} not found')
    return row


def _rollback():
    try:
        from application.models import db
        db.session.rollback()
    except Exception:
        pass


def admin_action(*rights: str):
    """Decorator for an admin handler that answers with an acknowledgement.

    Without arguments it only requires a valid admin (use it when the handler checks several
    rights itself, field by field). With rights, the caller needs **any** of them.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not require_admin():
                return None
            try:
                if rights:
                    from application.models import db
                    from application.security.permissions import has_right
                    user = current_admin_user()
                    if not any(has_right(db, user, key) for key in rights):
                        return failure(PERMISSION_DENIED)
                return fn(*args, **kwargs)
            except Fail as problem:
                _rollback()
                return failure(problem.message)
            except (StaleDataError, ObjectDeletedError):
                # Two admins (or tabs) changing the same rows at the same moment: the second one
                # finds its rows gone. Not a bug to log with a traceback — tell the person.
                logger.warning('Concurrent change in admin handler %s', fn.__name__)
                _rollback()
                return failure(CONCURRENT_CHANGE)
            except Exception:
                reference = new_error_reference()
                logger.exception('Unhandled error in admin handler %s (reference %s)', fn.__name__, reference)
                _rollback()
                return internal_failure(reference)
        # Read by tests/admin/test_admin_rights.py, which checks every handler really refuses a caller without them.
        wrapper.required_rights = rights
        return wrapper
    return decorator
