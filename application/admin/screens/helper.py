"""Helpers for admin screens page: building and emitting admin screen lists."""
import logging
from datetime import datetime as _dt, timezone as _tz

logger = logging.getLogger(__name__)

_EVENT = 'displayhive:admin:stc:upd_admin_screen'


def _screens_access(db, sid):
    """Return (may_see_list, may_see_devicekeys) for the socket at *sid*.

    The screen list itself is either-right: screens.page is the obvious
    owner, but the Devices page (device.page) also needs it to populate the
    "assign to screen" pickers — withholding it there would leave those
    dropdowns permanently empty for a device-only account. devicekey
    (embedded per-screen as attached_device.devicekey) is independently
    gated by device.showkey, same as the Devices page list.
    """
    from application.socketio_handlers.auth import resolve_admin_user
    from application.permissions import has_right
    user = resolve_admin_user(sid)
    may_see_list = has_right(db, user, 'screens.page') or has_right(db, user, 'device.page')
    may_see_devicekeys = has_right(db, user, 'device.showkey')
    return may_see_list, may_see_devicekeys


def _masked_screens(screens_data, may_see_devicekeys):
    if may_see_devicekeys:
        return screens_data
    masked = []
    for s in screens_data:
        s = dict(s)
        if s.get('attached_device'):
            s['attached_device'] = {**s['attached_device'], 'devicekey': None}
        masked.append(s)
    return masked


def emit_admin_screen(socketio, app, db, room=None):
    """Build and emit the `upd_admin_screen` payload.

    Like emit_devices_update / emit_screengroups_update, this is a proactive
    server push (on connect, and after most screen/device mutations) rather
    than only a response to an explicit request, so it needs its own access
    check per recipient instead of relying on the read handler's
    @require_right to have gated it. Falls back to the previous unconditional
    behavior if per-socket enumeration is ever unavailable.
    """
    # Use the Device DB `is_online` flag as the single source of truth for
    # whether a screen is considered online. Avoid relying on in-memory
    # connection state so the admin UI is authoritative and consistent.
    with app.app_context():
        from application.models import Screen, Device

        screens = db.session.execute(db.select(Screen).where(Screen.name != 'preview_admin')).scalars().all()
        screens_data = []

        for entry in screens:
            # Determine attached device (if any)
            device_info = None
            try:
                device_obj = db.session.execute(db.select(Device).where(Device.screen_id == entry.id)).scalars().first()
                if device_obj:
                    device_info = {
                        'id': device_obj.id,
                        'devicekey': getattr(device_obj, 'devicekey', None),
                        'find': bool(getattr(device_obj, 'find', False)),
                        'is_online': bool(getattr(device_obj, 'is_online', False)),
                        'max_resolution_width': getattr(device_obj, 'max_resolution_width', None),
                        'max_resolution_height': getattr(device_obj, 'max_resolution_height', None),
                    }
                else:
                    device_obj = None
            except Exception:
                device_obj = None
                device_info = None

            # is_online is derived from the authoritative DB flag on the device
            is_online = bool(device_obj and getattr(device_obj, 'is_online', False))

            if is_online:
                timestr = 'online'
            else:
                if entry.lastseen:
                    lastseen = entry.lastseen.replace(tzinfo=_tz.utc) if entry.lastseen.tzinfo is None else entry.lastseen
                    td = _dt.now(_tz.utc) - lastseen
                    total = int(td.total_seconds())
                    days, rem = divmod(total, 86400)
                    hours, rem = divmod(rem, 3600)
                    minutes, seconds = divmod(rem, 60)
                    if days:
                        timestr = f"{days}d {hours:02}:{minutes:02}:{seconds:02}"
                    else:
                        timestr = f"{hours:02}:{minutes:02}:{seconds:02}"
                else:
                    timestr = 'n/a'

            # Use persisted screen resolution; runtime resolution (connected client)
            # is no longer sourced from in-memory stores.
            resolution_str = f"{entry.resolution_width}x{entry.resolution_height}" if entry.resolution_width and entry.resolution_height else 'n/a'

            screens_data.append({
                'id': entry.id,
                'name': entry.name,
                'resolution': resolution_str,
                'timestr': timestr,
                'debug': bool(entry.debug) if entry.debug is not None else False,
                'monitoring_enabled': bool(entry.monitoring_enabled) if entry.monitoring_enabled is not None else True,
                'attached_device': device_info,
            })

        logger.debug("Emitting upd_admin_screen with %s screens to %s", len(screens_data), room or 'admins')

        if room and room != 'admins':
            may_see_list, may_see_devicekeys = _screens_access(db, room)
            if may_see_list:
                socketio.emit(_EVENT, {'data': _masked_screens(screens_data, may_see_devicekeys)}, room=room)
            return

        try:
            participants = list(socketio.server.manager.get_participants('/', 'admins'))
        except Exception:
            participants = None

        if not participants:
            socketio.emit(_EVENT, {'data': screens_data}, room='admins')
            return

        for sid, _eio_sid in participants:
            may_see_list, may_see_devicekeys = _screens_access(db, sid)
            if may_see_list:
                socketio.emit(_EVENT, {'data': _masked_screens(screens_data, may_see_devicekeys)}, room=sid)
