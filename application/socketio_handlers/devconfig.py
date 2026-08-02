"""Helper to build and emit unified `upd_deviconfig` payloads.

All fields in the `deviceconfig` object will be non-empty strings. Callers should
pass either a `device` object, a `screen` object, or both. The helper will
populate missing string fields with an empty string and normalize boolean
fields to `'yes'` / `'no'` strings.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def send_upd_deviceconfig(socketio, db, room: Optional[str] = None, to: Optional[str] = None, sid: Optional[str] = None, *, device=None, screen=None):
    """Emit a fully-populated `upd_deviceconfig` payload using authoritative DB values."""
    try:
        from application.models import Device, Screen

        device_obj = None
        screen_obj = None

        # Resolve device — fresh DB query so expired attributes are never read
        devicekey = None
        device_id = None
        if device is not None:
            try:
                devicekey = getattr(device, 'devicekey', None)
                device_id  = getattr(device, 'id', None)
            except Exception:
                logger.debug('send_upd_deviceconfig: failed to read attrs off passed-in device object', exc_info=True)
        if not devicekey and room and room.startswith('device_'):
            devicekey = room.split('device_', 1)[1]
        if not devicekey and to and isinstance(to, str) and to.startswith('device_'):
            devicekey = to.split('device_', 1)[1]

        if devicekey:
            device_obj = db.session.execute(
                db.select(Device).where(Device.devicekey == devicekey)
            ).scalar_one_or_none()
        elif device_id:
            device_obj = db.session.get(Device, device_id)

        # Resolve screen — prefer passed object, then DB via device.screen_id
        if screen is not None and hasattr(screen, 'name'):
            screen_obj = screen
        elif device_obj and getattr(device_obj, 'screen_id', None):
            screen_obj = db.session.execute(
                db.select(Screen).where(Screen.id == device_obj.screen_id)
            ).scalars().first()

        # Build payload
        key             = str(getattr(device_obj, 'devicekey', '') or '')
        name            = str(getattr(device_obj, 'name', '')      or '')
        screenname_val  = str(getattr(screen_obj,  'name', '')     or '')
        devicedebugstate = 'yes' if (screen_obj and getattr(screen_obj, 'debug', False)) else 'no'
        glow_state       = 'yes' if (device_obj  and getattr(device_obj,  'find',  False)) else 'no'

        cfg = {
            'deviceconfig': {
                'key':              key,
                'name':             name,
                'screenname':       screenname_val,
                'devicedebugstate': devicedebugstate,
                'glow':             glow_state,
            }
        }

        logger.debug("[devconfig] Emitting to room='%s' key='%s' name='%s' screenname='%s'", room, key, name, screenname_val)

        if room:
            socketio.emit('upd_deviceconfig', cfg, room=room)
        elif to:
            socketio.emit('upd_deviceconfig', cfg, to=to)
        elif sid:
            socketio.emit('upd_deviceconfig', cfg, room=sid)
        else:
            socketio.emit('upd_deviceconfig', cfg)

    except Exception:
        logger.exception("[devconfig] Error in send_upd_deviceconfig")

