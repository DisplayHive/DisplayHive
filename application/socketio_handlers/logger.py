"""Socket.IO handlers for the screen log: screens report, the admin Logger page reads.

A screen sends ``displayhive:logger:cts:log_entry``. The server stores the line (see
application/screen_logs.py) under the screen of that connection — the payload's own idea of the
screen is not trusted — and pushes it live to every admin watching the Logger page. The page loads
older entries, filtered, with ``displayhive:logger:cts:query``.
"""

import logging
import time

from flask import request
from flask_socketio import emit, join_room, leave_room

from application import screen_logs

log = logging.getLogger(__name__)

# Sockets of the admins currently watching the Logger page. While there are any, screens also send
# their debug/info lines (they are told with `logger_active`; a screen that connects meanwhile is
# told by the connect handler, see application/admin/devices/connection.py).
_watchers: set = set()
_socketio = None

# A screen may send this many lines per window; the rest is dropped (a screen stuck in a loop must
# not fill the database). Counted per socket.
RATE_LIMIT = 100
RATE_WINDOW_SECONDS = 10.0
_rate: dict = {}


def _within_rate_limit(sid: str, now: float | None = None) -> bool:
    now = time.monotonic() if now is None else now
    if len(_rate) > 1000:
        for stale in [s for s, (start, _n) in _rate.items() if now - start > RATE_WINDOW_SECONDS]:
            del _rate[stale]
    start, count = _rate.get(sid, (now, 0))
    if now - start > RATE_WINDOW_SECONDS:
        start, count = now, 0
    _rate[sid] = (start, count + 1)
    return count < RATE_LIMIT


def register_logger_handlers(socketio, app, db):
    """Register all logger-related socket.io event handlers."""
    from application.models import Device, Screen
    from application.socketio_handlers.actions import admin_action, ok
    from application.socketio_handlers.auth import require_admin
    from application.socketio_handlers.lifecycle import connected_devices, registry_lock

    global _socketio
    _socketio = socketio
    logger_room = app.config.get('LOGGER_ROOM', 'logger_room')

    def _screen_of_connection():
        """``(screen_id, name)`` of the screen on the current socket, or None if it is no screen."""
        sid = request.sid
        with registry_lock:
            devicekey = next((k for k, info in connected_devices.items() if info.get('sid') == sid), None)
        if not devicekey:
            return None
        device = db.session.execute(db.select(Device).where(Device.devicekey == devicekey)).scalar_one_or_none()
        screen = db.session.get(Screen, device.screen_id) if device and device.screen_id else None
        return (screen.id, screen.name) if screen else None

    @socketio.on('displayhive:logger:cts:subscribe')
    @admin_action('logger.page')
    def handle_logger_subscribe(data=None):
        """Join the live feed of the Logger page and tell the screens to send everything."""
        join_room(logger_room, sid=request.sid)
        first = not _watchers
        _watchers.add(request.sid)
        if first:
            emit('logger_active', {}, broadcast=True)
            log.info('Logger now active, notified screens')
        return ok()

    @socketio.on('displayhive:logger:cts:unsubscribe')
    @admin_action('logger.page')
    def handle_logger_unsubscribe(data=None):
        """Leave the live feed (admin only)."""
        leave_room(logger_room, sid=request.sid)
        forget_watcher(request.sid)
        return ok()

    @socketio.on('displayhive:logger:cts:query')
    @admin_action('logger.page')
    def handle_query(data=None):
        """One page of stored entries, newest page first, oldest line first within it.

        data: ``screen_id``, ``severities`` (list), ``search``, ``before_id`` (continue behind
        an earlier page), ``limit``. Answers ``{success, logs, has_more}``.
        """
        data = data if isinstance(data, dict) else {}
        severities = data.get('severities')
        logs, has_more = screen_logs.query(
            db,
            screen_id=data.get('screen_id'),
            severities=severities if isinstance(severities, list) else None,
            search=(str(data['search']).strip() or None) if data.get('search') else None,
            before_id=data.get('before_id'),
            limit=data.get('limit') or screen_logs.PAGE_DEFAULT,
        )
        return ok(logs=logs, has_more=has_more)

    @socketio.on('displayhive:logger:cts:log_entry')
    def handle_log_entry(data):
        """A line from a screen: store it, push it live. An admin's test line is only pushed."""
        try:
            entry = screen_logs.normalize_entry(data)
            screen = _screen_of_connection()
            if screen:
                if not _within_rate_limit(request.sid):
                    return
                row = screen_logs.record(db, screen[0], entry)
                payload = screen_logs.entry_dict(row, screen[1])
            elif require_admin():
                # The Logger page's "send test line" button: shown live, never stored.
                payload = {**entry, 'id': None, 'screen': 'admin', 'screen_id': None,
                           'timestamp': screen_logs._now().isoformat() + 'Z'}
            else:
                return
            emit('displayhive:logger:stc:log_entry', payload, room=logger_room)
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            log.exception('Error handling log entry')


def forget_watcher(sid: str) -> None:
    """An admin left the Logger page (or its socket dropped); the last one leaving tells the screens."""
    if sid in _watchers:
        _watchers.discard(sid)
        if not _watchers and _socketio is not None:
            _socketio.emit('logger_inactive', {})
            log.info('Logger no longer watched, notified screens')


def get_logger_status():
    """Return whether an admin currently watches the Logger page."""
    return bool(_watchers)
