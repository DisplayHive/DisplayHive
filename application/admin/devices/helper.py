import logging

logger = logging.getLogger(__name__)


def get_registered_devices_handler(app, socketio, db):
    """Return a list of all registered devices as serializable dicts.

    Each entry is produced by ``Device.to_dict()`` with an additional
    ``screen_name`` key resolved from the device's ``screen_id``.
    Falls back to manual attribute extraction if ``to_dict()`` raises.
    """
    from application.models import Device, Screen
    with app.app_context():
        screens = db.session.execute(db.select(Screen)).scalars().all()
        screen_map = {s.id: s.name for s in screens}
        devices = db.session.execute(db.select(Device)).scalars().all()
        devices_data = []
        for dev in devices:
            try:
                # Prefer model-provided serialization which formats datetimes
                entry = dev.to_dict()
            except Exception:
                # Fallback: manual extraction with ISO-formatted datetimes
                from datetime import datetime  # noqa: PLC0415
                entry = {
                    'id': getattr(dev, 'id', None),
                    'devicekey': getattr(dev, 'devicekey', None),
                    'name': getattr(dev, 'name', None),
                    'created_at': getattr(dev, 'created_at').isoformat() if getattr(dev, 'created_at', None) else None,
                    'last_connected_at': getattr(dev, 'last_connected_at').isoformat() if getattr(dev, 'last_connected_at', None) else None,
                    'is_active': getattr(dev, 'is_active', None),
                    'screen_id': getattr(dev, 'screen_id', None),
                    'find': bool(getattr(dev, 'find', False)),
                    'is_online': bool(getattr(dev, 'is_online', False))
                }
            entry['screen_name'] = screen_map.get(getattr(dev, 'screen_id'))
            
            devices_data.append(entry)
    return devices_data


def _masked(devices_data):
    """Copy of *devices_data* with devicekey stripped (for callers without device.showkey)."""
    return [{**d, 'devicekey': None} for d in devices_data]


def _devices_payload_for_sid(devices_data, sid):
    """Return the devices payload as *sid* is entitled to see it."""
    from application.socketio_handlers.auth import resolve_admin_user
    from application.models import db
    from application.security.permissions import has_right
    user = resolve_admin_user(sid)
    if has_right(db, user, 'device.showkey'):
        return devices_data
    return _masked(devices_data)


def emit_devices_update(socketio, db, room=None):
    """Emit devices list update to clients.

    devicekey is gated by the device.showkey right, and different recipients
    in the 'admins' room may resolve that right differently, so a plain
    room-wide broadcast can't share one payload — each admin socket gets its
    own masked/unmasked copy. Falls back to a single unmasked broadcast (the
    prior, pre-rights behavior) if per-socket enumeration is unavailable for
    any reason, so a masking failure never breaks the live device list.
    """
    event = 'displayhive:devices:stc:devices_upd_devicelist'
    try:
        from flask import current_app
        devices_data = get_registered_devices_handler(current_app, socketio, db)

        if room and room != 'admins':
            socketio.emit(event, {'devices': _devices_payload_for_sid(devices_data, room)}, room=room)
            return

        try:
            participants = list(socketio.server.manager.get_participants('/', 'admins'))
        except Exception:
            participants = None

        if not participants:
            socketio.emit(event, {'devices': devices_data}, room='admins')
            return

        for sid, _eio_sid in participants:
            socketio.emit(event, {'devices': _devices_payload_for_sid(devices_data, sid)}, room=sid)
    except Exception:
        logger.exception('emit_devices_update failed')
