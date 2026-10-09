"""Persistent screen log: what screens report about themselves (``screen_log`` table).

Screens send their log lines over Socket.IO (``displayhive:logger:cts:log_entry``, see
application/socketio_handlers/logger.py); this module stores, reads and prunes them. Rows carry
the server's receive time in UTC (a kiosk's clock can be wrong), and the screen comes from the
connection, never from the payload.

How long rows are kept is two settings in the admin Settings page (SystemSetting):
``screen_log_max_age_hours`` and ``screen_log_max_rows`` — whichever limit is hit first prunes.
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

SEVERITIES = ('debug', 'info', 'warn', 'error')
MESSAGE_MAX = 2000
FUNCTION_MAX = 255
PAGE_DEFAULT = 200
PAGE_MAX = 500

DEFAULT_MAX_AGE_HOURS = 72
DEFAULT_MAX_ROWS = 250_000
# setting key -> (default, smallest, largest)
RETENTION_SETTINGS = {
    'screen_log_max_age_hours': (DEFAULT_MAX_AGE_HOURS, 1, 24 * 365),
    'screen_log_max_rows': (DEFAULT_MAX_ROWS, 1_000, 5_000_000),
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- retention settings ----------------------------------------------------

def validate_retention_setting(key: str, value) -> str:
    """The value as the string to store, or ValueError with a message for the admin."""
    default, low, high = RETENTION_SETTINGS[key]
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f'{key} must be a whole number') from None
    if not low <= number <= high:
        raise ValueError(f'{key} must be between {low} and {high}')
    return str(number)


def retention_limits(db) -> tuple:
    """``(max_age_hours, max_rows)`` as configured; a missing or invalid value is the default."""
    from application.models import SystemSetting
    rows = db.session.execute(
        db.select(SystemSetting).where(SystemSetting.key.in_(list(RETENTION_SETTINGS)))
    ).scalars().all()
    stored = {row.key: row.value for row in rows}
    limits = []
    for key, (default, _low, _high) in RETENTION_SETTINGS.items():
        try:
            limits.append(int(validate_retention_setting(key, stored[key])) if key in stored else default)
        except ValueError:
            limits.append(default)
    return tuple(limits)


# --- writing ---------------------------------------------------------------

def normalize_entry(payload) -> dict:
    """``{severity, message, function}`` from whatever a client sent, clipped to the column sizes."""
    payload = payload if isinstance(payload, dict) else {}
    severity = str(payload.get('severity') or 'info').lower()
    if severity == 'warning':
        severity = 'warn'
    if severity not in SEVERITIES:
        severity = 'info'
    return {
        'severity': severity,
        'message': str(payload.get('message') or payload.get('data') or '')[:MESSAGE_MAX],
        'function': str(payload.get('function') or '')[:FUNCTION_MAX],
    }


def record(db, screen_id: int, entry: dict):
    """Store one normalized entry for a screen; returns the row."""
    from application.models import ScreenLog
    row = ScreenLog(screen_id=screen_id, timestamp=_now(), **entry)
    db.session.add(row)
    db.session.commit()
    return row


def entry_dict(row, screen_name: str) -> dict:
    """The row as the admin Logger shows it (``timestamp`` is an ISO instant in UTC)."""
    return {
        'id': row.id,
        'timestamp': row.timestamp.isoformat() + 'Z',
        'severity': row.severity,
        'message': row.message,
        'screen': screen_name,
        'screen_id': row.screen_id,
        'function': row.function,
    }


# --- reading ---------------------------------------------------------------

def query(db, *, screen_id=None, severities=None, search=None, before_id=None, limit=PAGE_DEFAULT) -> tuple:
    """``(entries oldest-first, has_more)`` — one page of the newest rows matching the filters.

    ``before_id`` continues behind a previous page (rows with a smaller id).
    """
    from application.models import Screen, ScreenLog
    limit = max(1, min(int(limit or PAGE_DEFAULT), PAGE_MAX))
    stmt = db.select(ScreenLog, Screen.name).join(Screen, Screen.id == ScreenLog.screen_id)
    if screen_id is not None:
        stmt = stmt.where(ScreenLog.screen_id == int(screen_id))
    wanted = [s for s in (severities or []) if s in SEVERITIES]
    if wanted:
        stmt = stmt.where(ScreenLog.severity.in_(wanted))
    if search:
        like = '%' + str(search).replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        stmt = stmt.where(ScreenLog.message.ilike(like, escape='\\'))
    if before_id is not None:
        stmt = stmt.where(ScreenLog.id < int(before_id))
    rows = db.session.execute(stmt.order_by(ScreenLog.id.desc()).limit(limit + 1)).all()
    has_more = len(rows) > limit
    page = [entry_dict(row, name) for row, name in rows[:limit]]
    page.reverse()
    return page, has_more


# --- pruning ---------------------------------------------------------------

def prune(db) -> tuple:
    """Delete rows past the configured age, then the oldest rows beyond the configured row count.

    Returns ``(deleted_by_age, deleted_by_cap)``.
    """
    from application.models import ScreenLog
    max_age_hours, max_rows = retention_limits(db)
    cutoff = _now() - timedelta(hours=max_age_hours)
    deleted_by_age = db.session.execute(db.delete(ScreenLog).where(ScreenLog.timestamp < cutoff)).rowcount
    db.session.commit()

    total = db.session.execute(db.select(db.func.count()).select_from(ScreenLog)).scalar()
    deleted_by_cap = 0
    if total > max_rows:
        oldest = db.session.execute(
            db.select(ScreenLog.id).order_by(ScreenLog.id.asc()).limit(total - max_rows)
        ).scalars().all()
        if oldest:
            deleted_by_cap = db.session.execute(db.delete(ScreenLog).where(ScreenLog.id.in_(oldest))).rowcount
            db.session.commit()
    return deleted_by_age, deleted_by_cap
