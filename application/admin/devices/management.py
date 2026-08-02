"""Admin device-management socket handlers — device listing, ping presence,
updates, screen assignment, find mode, deletion, registration approval and
viewport reporting. Split out of the devices ``sockethandlers`` module.
"""

import logging

logger = logging.getLogger(__name__)


def register_device_management_handlers(socketio, app, db):
    """Register the admin device-management socket handlers."""
    from application.models import Screen
    from application.admin.devices.helper import emit_devices_update
    from flask import request
    from datetime import datetime, timezone
    from application.socketio_handlers.auth import admin_handler, require_right, current_admin_user
    from application.permissions import has_right

    def _assign_screen_to_device(device, screen):
        """Assign *screen* to *device*, un-assigning any other device currently on that screen.

        If *screen* is None, the device's screen assignment is cleared.
        """
        from application.models import Device as DeviceModel
        if not screen:
            device.screen_id = None
            return
        other = db.session.execute(
            db.select(DeviceModel).where(
                DeviceModel.screen_id == screen.id,
                DeviceModel.id != device.id
            )
        ).scalar_one_or_none()
        if other:
            other.screen_id = None
        device.screen_id = screen.id

    def _resolve_devicekey_for_sid(sid):
        """Resolve a devicekey from the in-memory connection map or handshake args."""
        try:
            from application.socketio_handlers.lifecycle import connected_devices
            for k, v in list(connected_devices.items()):
                if v.get('sid') == sid:
                    return k
        except Exception:
            logger.debug('Failed to resolve devicekey for sid=%s from connected_devices', sid, exc_info=True)
        if getattr(request, 'args', None):
            try:
                return request.args.get('devicekey')
            except Exception:
                return None
        return None

    def _is_impersonation():
        """Return True if the current connection is an impersonation session."""
        try:
            if getattr(request, 'args', None):
                imp = request.args.get('impersonate')
                return bool(imp and str(imp).lower() in ('1', 'true', 'yes', 'on'))
        except Exception:
            logger.debug('Failed to read impersonate flag from request args', exc_info=True)
        return False

    def _emit_admin_screen_safe(room=None):
        """Best-effort emit of the admin screen list."""
        try:
            from application.admin.screens.helper import emit_admin_screen
            emit_admin_screen(socketio, app, db, room=room) if room else emit_admin_screen(socketio, app, db)
        except Exception:
            logger.exception('Error emitting screen list')

    @socketio.on('displayhive:devices:cts:get_devices')
    @require_right('device.page')
    def handle_get_devices(data=None):
        """Get all registered devices"""
        emit_devices_update(socketio, db, room=request.sid)

    @socketio.on('displayhive:devices:cts:ping')
    def handle_device_ping(data=None):
        """Handle periodic device ping from clients. If the device is not
        marked online in the database, mark it online and notify admins.

        Device-facing (not admin-gated): resolves the devicekey from the
        connected_devices mapping or the handshake args.
        """
        sid = getattr(request, 'sid', None)
        try:
            devicekey = _resolve_devicekey_for_sid(sid)
            if not devicekey:
                # Nothing we can do without a devicekey
                return

            # Impersonation mode must not alter authoritative online state.
            if _is_impersonation():
                logger.debug('Ignoring ping from impersonation session (devicekey=%s, sid=%s)', devicekey, sid)
                return

            from application.models import Device
            dev = db.session.execute(
                db.select(Device).where(Device.devicekey == devicekey)
            ).scalar_one_or_none()

            if not dev:
                return

            notify_admins = False
            if not getattr(dev, 'is_online', False):
                dev.is_online = True
                notify_admins = True

            try:
                dev.last_connected_at = datetime.now(timezone.utc)
            except Exception:
                logger.debug('Ping: failed to set last_connected_at for devicekey=%s', devicekey, exc_info=True)

            db.session.commit()

            if notify_admins:
                try:
                    from application.admin.devices.helper import get_registered_devices_handler
                    devices_data = get_registered_devices_handler(app, socketio, db)
                    socketio.emit('displayhive:devices:stc:devices_upd_devicelist', {'devices': devices_data}, room='admins')
                except Exception:
                    logger.exception('Ping: error notifying admins')

                try:
                    from application.admin.alerting.sender import fire_alert
                    from application.models import Screen as _Screen
                    device_label = dev.name or devicekey[:8]
                    if getattr(dev, 'screen_id', None):
                        _s = db.session.get(_Screen, dev.screen_id)
                        if _s:
                            fire_alert(db, 'screen_online', f"Screen '{_s.name}'")
                    fire_alert(db, 'device_online', f"Device '{device_label}'")
                except Exception:
                    logger.exception('Ping: error firing online alerts')

        except Exception:
            logger.exception('Ping: error handling device ping')
            try:
                db.session.rollback()
            except Exception:
                pass

    @socketio.on('displayhive:devices:cts:update_device')
    @admin_handler
    def handle_update_device(data):
        """Update device information.

        'name' and 'is_active' are gated by separate rights (device.rename /
        device.enable), so each requested field is checked independently and
        silently dropped if the caller lacks the right for that field.
        """
        from application.models import Device

        device_id = data.get('device_id')
        user = current_admin_user()
        name = data.get('name')
        if name is not None and not has_right(db, user, 'device.rename'):
            name = None
        allow_enable_change = has_right(db, user, 'device.enable')

        if not device_id:
            return {'success': False, 'error': 'No device_id provided'}

        device = db.session.execute(
            db.select(Device).where(Device.id == device_id)
        ).scalar_one_or_none()

        if not device:
            return {'success': False, 'error': 'Device not found'}

        was_active = bool(getattr(device, 'is_active', True))
        if name is not None:
            device.name = name
        if 'is_active' in data and allow_enable_change:
            try:
                device.is_active = bool(data.get('is_active'))
            except Exception:
                logger.debug('update_device: failed to set is_active for device_id=%s', device_id, exc_info=True)
        deactivated = was_active and not bool(getattr(device, 'is_active', True))
        if deactivated:
            try:
                device.is_online = False
            except Exception:
                logger.debug('update_device: failed to set is_online for device_id=%s', device_id, exc_info=True)
        db.session.commit()

        if deactivated:
            # Snapshot the specific sid to kick *before* emitting anything. The
            # 'device_<devicekey>' room is keyed by devicekey, not by session —
            # if this handler runs with any delay, a session that has since
            # reconnected (e.g. a quick deactivate/reactivate) may already have
            # joined that same room. Broadcasting to the room would incorrectly
            # tell that newer, legitimately-active session it was deactivated.
            # Targeting the captured sid directly keeps the rejection scoped to
            # the exact stale connection being kicked.
            try:
                from application.socketio_handlers.lifecycle import connected_devices, connected_screens
                entry = connected_devices.pop(device.devicekey, None)
                sid_to_disconnect = entry.get('sid') if entry else None
                for screen_name, info in list(connected_screens.items()):
                    if info and info.get('devicekey') == device.devicekey:
                        del connected_screens[screen_name]
            except Exception:
                logger.exception('Error looking up connected device session')
                sid_to_disconnect = None

            if sid_to_disconnect:
                try:
                    socketio.emit(
                        'displayhive:devices:stc:connection_rejected',
                        {'reason': 'device_inactive', 'message': 'Device is deactivated by administrator'},
                        room=sid_to_disconnect
                    )
                except Exception:
                    logger.exception('Error emitting connection_rejected to deactivated device')

                try:
                    socketio.emit(
                        'command',
                        {'CMD': 'DEVICE_DEACTIVATED', 'reason': 'deactivated_by_admin'},
                        room=sid_to_disconnect
                    )
                except Exception:
                    logger.exception('Error emitting DEVICE_DEACTIVATED command')

                try:
                    from flask_socketio import disconnect
                    disconnect(sid=sid_to_disconnect)
                    logger.info('Disconnected SID %s for deactivated device', sid_to_disconnect)
                except Exception:
                    logger.exception('Error disconnecting deactivated device')

        emit_devices_update(socketio, db, room='admins')
        _emit_admin_screen_safe()
        return {'success': True}

    @socketio.on('displayhive:devices:cts:assign_device_screen')
    @require_right('device.assign')
    def handle_assign_device_screen(data):
        """Assign or unassign a screen from a device"""
        from application.models import Device, Screen
        from sqlalchemy.orm import joinedload

        device_id = data.get('device_id')
        screen_id = data.get('screen_id')
        screen_name = data.get('screen_name')
        screen_name = screen_name.strip() if isinstance(screen_name, str) else screen_name

        device = db.session.get(Device, device_id)
        if not device:
            return {'success': False, 'error': 'Device not found'}

        target_screen = None
        if screen_id is not None:
            try:
                target_screen = db.session.execute(
                    db.select(Screen).options(joinedload(Screen.screengroups)).where(Screen.id == int(screen_id))
                ).unique().scalar_one_or_none()
                if not target_screen:
                    return {'success': False, 'error': 'Screen not found'}
            except (ValueError, TypeError):
                return {'success': False, 'error': 'Invalid screen_id'}
        elif screen_name:
            target_screen = db.session.execute(
                db.select(Screen).options(joinedload(Screen.screengroups))
                .where(Screen.name == screen_name).order_by(Screen.lastseen.desc())
            ).unique().scalars().first()
            if not target_screen:
                return {'success': False, 'error': 'Screen not found'}

        _assign_screen_to_device(device, target_screen)
        db.session.commit()
        db.session.refresh(device)

        try:
            from application.socketio_handlers.devconfig import send_upd_deviceconfig
            send_upd_deviceconfig(socketio, db, room=f'device_{device.devicekey}', device=device, screen=target_screen)
        except Exception:
            logger.exception('Error pushing deviceconfig after assign')

        try:
            from application.socketio_handlers.upd_content import send_upd_content
            send_upd_content(socketio, db, screens=[target_screen])
        except Exception:
            logger.exception('Error pushing content after assign')

        emit_devices_update(socketio, db, room='admins')
        _emit_admin_screen_safe()

        return {'success': True}

    @socketio.on('displayhive:devices:cts:find_device')
    @admin_handler
    def handle_find_device(data):
        """Toggle the 'find' flag on a device and notify the device via upd_deviceconfig.

        Expected data: {'device_id': <id>} or {'devicekey': <key>, 'active': True|False}
        If 'active' is omitted, the flag will be toggled.
        """
        from application.models import Device, Screen
        device_id = data.get('device_id') if isinstance(data, dict) else None
        devicekey = data.get('devicekey') if isinstance(data, dict) else None
        active = data.get('active') if isinstance(data, dict) else None

        device = None
        if device_id:
            device = db.session.get(Device, device_id)
        elif devicekey:
            device = db.session.execute(db.select(Device).where(Device.devicekey == devicekey)).scalar_one_or_none()

        if not device:
            return {'success': False, 'error': 'Device not found'}

        new_state = not bool(device.find) if active is None else bool(active)
        device.find = new_state
        db.session.add(device)
        db.session.commit()
        try:
            db.session.refresh(device)
        except Exception:
            logger.debug('find_device: failed to refresh device id=%s after commit', device.id, exc_info=True)
        logger.info('find_device: device id=%s find=%s', device.id, device.find)

        try:
            from application.socketio_handlers.devconfig import send_upd_deviceconfig
            screen_obj = db.session.get(Screen, device.screen_id) if getattr(device, 'screen_id', None) else None
            send_upd_deviceconfig(socketio, db, room=f'device_{device.devicekey}', device=device, screen=screen_obj)
        except Exception:
            logger.exception('Error pushing deviceconfig after find_device')

        emit_devices_update(socketio, db, room='admins')

        # Fire find-mode alerts
        try:
            from application.admin.alerting.sender import fire_alert
            screen_obj = db.session.get(Screen, device.screen_id) if getattr(device, 'screen_id', None) else None
            subject_name = screen_obj.name if screen_obj else (device.name or str(device.id))
            fire_alert(db, 'screen_find_on' if new_state else 'screen_find_off', f"Screen '{subject_name}'")
        except Exception:
            logger.exception('find_device: error firing find alert')

        return {'success': True, 'find': new_state}

    @socketio.on("displayhive:devices:cts:delete_device")
    @require_right('device.delete')
    def admin_handle_delete_device(data):
        """Handle admin-initiated device deletion.

        Expects data: {'device_id': <id>} and returns an acknowledgement.
        """
        from application.models import Device

        device_id = data.get("device_id") if isinstance(data, dict) else None
        if not device_id:
            return

        device = db.session.execute(
            db.select(Device).where(Device.id == device_id)
        ).scalar_one_or_none()

        if device and getattr(device, "devicekey", None):
            try:
                socketio.emit(
                    "command",
                    {"CMD": "DEVICE_REVOKED", "reason": "deleted_by_admin"},
                    room=f"device_{device.devicekey}",
                )
            except Exception:
                logger.exception('Error notifying device of revocation')

        if device:
            db.session.delete(device)
        db.session.commit()

        emit_devices_update(socketio, db, room='admins')
        return {"success": True}

    @socketio.on("displayhive:devices:cts:approve_registration")
    @require_right('device.adopt')
    def admin_handle_approve_registration(data):
        """Approve a registration token and create a device (admin action).

        Expects data: {'token': <token>, 'device_name': <optional>, 'screen_name': <optional>}.
        Emits `registration_approved` to the requesting admin and `device_registered` to admins.
        """
        from application.models import Device, Screen
        import uuid

        token = data.get("token") if isinstance(data, dict) else None
        device_name = data.get("device_name") if isinstance(data, dict) else None
        sid_info = getattr(request, "sid", None)

        if not token:
            socketio.emit(
                "displayhive:devices:stc:registration_approved",
                {"success": False, "error": "No token provided"},
                room=sid_info,
            )
            return

        existing = db.session.execute(
            db.select(Device).where(Device.registration_token == token)
        ).scalar_one_or_none()

        if existing:
            socketio.emit(
                "displayhive:devices:stc:registration_approved",
                {"success": True, "devicekey": existing.devicekey},
                room=sid_info,
            )
            return {"success": True, "devicekey": existing.devicekey}

        devicekey = str(uuid.uuid4())
        device = Device(
            devicekey=devicekey,
            name=device_name or None,
            registration_token=token,
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )
        db.session.add(device)
        db.session.flush()

        screen_name = data.get("screen_name") if isinstance(data, dict) else None
        if screen_name:
            try:
                screen = db.session.execute(
                    db.select(Screen).where(Screen.name == screen_name).order_by(Screen.lastseen.desc())
                ).scalars().first()
                if screen:
                    device.screen_id = screen.id
            except Exception:
                logger.exception("Error assigning screen '%s' to device", screen_name)

        db.session.commit()
        db.session.refresh(device)

        emit_devices_update(socketio, db, room='admins')
        socketio.emit(
            "displayhive:devices:stc:registration_approved",
            {"success": True, "devicekey": devicekey},
            room=sid_info,
        )
        return {"success": True, "devicekey": devicekey}

    @socketio.on("displayhive:devices:cts:upd_viewport")
    def handle_upd_viewport(data=None):
        """Receive visible viewport dimensions from a screen device and persist to resolution fields.

        Device-facing (not admin-gated).
        """
        sid = getattr(request, "sid", None)

        # Skip impersonation sessions
        if _is_impersonation():
            return

        devicekey = _resolve_devicekey_for_sid(sid)
        if not devicekey:
            return

        width = data.get("width") if isinstance(data, dict) else None
        height = data.get("height") if isinstance(data, dict) else None
        if width is None or height is None:
            return

        try:
            from application.models import Device as _Device
            dev = db.session.execute(
                db.select(_Device).where(_Device.devicekey == devicekey)
            ).scalar_one_or_none()

            if not dev or not getattr(dev, "screen_id", None):
                return

            screen = db.session.get(Screen, dev.screen_id)
            if not screen:
                return

            # Capture pre-change state for maximized alert detection
            old_w = screen.resolution_width or 0
            old_h = screen.resolution_height or 0
            old_max_w = getattr(dev, "max_resolution_width", None) or 0
            old_max_h = getattr(dev, "max_resolution_height", None) or 0

            screen.resolution_width = int(width)
            screen.resolution_height = int(height)

            # Track max resolution seen by this device
            cur_max_w = getattr(dev, "max_resolution_width", None) or 0
            cur_max_h = getattr(dev, "max_resolution_height", None) or 0
            if int(width) > cur_max_w or int(height) > cur_max_h:
                dev.max_resolution_width = max(int(width), cur_max_w)
                dev.max_resolution_height = max(int(height), cur_max_h)

            db.session.commit()
            logger.info("Viewport: screen '%s' viewport updated: %sx%s", screen.name, width, height)

            # Fire maximized/not-maximized alert when fullscreen state changes
            try:
                from application.admin.alerting.sender import fire_alert
                new_max_w = getattr(dev, "max_resolution_width", None) or 0
                new_max_h = getattr(dev, "max_resolution_height", None) or 0
                old_is_max = old_max_w > 0 and old_w == old_max_w and old_h == old_max_h
                new_is_max = new_max_w > 0 and int(width) == new_max_w and int(height) == new_max_h
                if old_is_max != new_is_max:
                    alert_type = "screen_maximized" if new_is_max else "screen_not_maximized"
                    fire_alert(db, alert_type, f"Screen '{screen.name}'")
            except Exception:
                logger.exception('Viewport: error firing maximized alert')

            from application.admin.screens.helper import emit_admin_screen
            emit_admin_screen(socketio, app, db, room="admins")
        except Exception:
            logger.exception('Viewport: error persisting viewport')
            try:
                db.session.rollback()
            except Exception:
                pass

    @socketio.on("displayhive:devices:cts:get_available_screens")
    @admin_handler
    def get_available_screens_namespaced(message=None):
        """Return screens that are not already assigned to another device."""
        from application.models import Device

        screens = db.session.execute(
            db.select(Screen).where(Screen.name != 'preview_admin')
        ).scalars().all()

        assigned_screen_ids = {
            screen_id
            for screen_id in db.session.execute(
                db.select(Device.screen_id).where(Device.screen_id.is_not(None))
            ).scalars().all()
            if screen_id is not None
        }

        available = [
            {'id': s.id, 'name': s.name}
            for s in screens
            if s.id not in assigned_screen_ids
        ]

        result = {'screens': available}
        socketio.emit('displayhive:devices:stc:available_screens', result, room=request.sid)
        return result
