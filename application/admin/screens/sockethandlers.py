import logging

from datetime import datetime, timezone
from flask import request
from application.utils import emit_screengroups_update

logger = logging.getLogger(__name__)


def register_admin_screens_handlers(socketio, app, db):
    """Register admin socket handlers related to Screens (admin UI: Monitore)."""

    from application.socketio_handlers.auth import require_right, fields, admin_handler, current_admin_user
    from application.permissions import has_right
    from application.models import Screen, Device, Screengroup
    from application.admin.screens.helper import emit_admin_screen

    # The `delete_disconnected_screens` admin action was removed from the UI.
    # If needed in future reintroduce as an explicit server-side handler.

    def _ensure_one_screen_group(screen):
        """Ensure a dedicated is_one_screen Screengroup exists for *screen* and the screen is in it."""
        sg = db.session.execute(
            db.select(Screengroup)
            .where(Screengroup.name == screen.name)
            .where(Screengroup.is_one_screen == True)
        ).scalar_one_or_none()
        if not sg:
            sg = Screengroup(name=screen.name, is_one_screen=True)
            db.session.add(sg)
            db.session.flush()
        if screen not in sg.screens:
            sg.screens.append(screen)
        return sg

    @socketio.on('displayhive:screens:cts:create_screen')
    @require_right('screens.create')
    def handle_create_screen(data):
        """Create a new screen and a dedicated is_one_screen Screengroup for it."""
        logger.debug('create_screen data=%s', data)
        name, width, height = fields(data, 'name', 'width', 'height')
        name = (name or '').strip()
        if not name:
            return {'success': False, 'error': 'name is required'}

        existing = db.session.execute(
            db.select(Screen).where(Screen.name == name)
        ).scalar_one_or_none()
        if existing:
            return {'success': False, 'error': f'Screen "{name}" already exists'}

        screen = Screen(
            name=name,
            active=True,
            lastseen=datetime.now(timezone.utc),
            resolution_width=int(width) if width else 0,
            resolution_height=int(height) if height else 0,
        )
        db.session.add(screen)
        db.session.flush()
        _ensure_one_screen_group(screen)
        db.session.commit()
        logger.info('Created screen "%s" with dedicated screengroup', name)

        emit_admin_screen(socketio, app, db, room='admins')
        emit_screengroups_update(socketio, app, db, room='admins')
        return {'success': True, 'screen_id': screen.id}

    @socketio.on('displayhive:screens:cts:delete_screen')
    @require_right('screens.delete')
    def handle_delete_screen(data):
        """Delete a screen and its dedicated is_one_screen Screengroup."""
        logger.debug('delete_screen data=%s', data)
        (screen_id,) = fields(data, 'screen_id')
        if not screen_id:
            return {'success': False, 'error': 'screen_id is required'}

        screen = db.session.get(Screen, int(screen_id))
        if not screen:
            return {'success': False, 'error': 'Screen not found'}

        screen_name = screen.name
        one_sg = db.session.execute(
            db.select(Screengroup).where(Screengroup.name == screen_name).where(Screengroup.is_one_screen == True)
        ).scalar_one_or_none()
        if one_sg:
            db.session.delete(one_sg)
        db.session.delete(screen)
        db.session.commit()
        logger.info('Deleted screen "%s" and its dedicated screengroup', screen_name)

        emit_admin_screen(socketio, app, db, room='admins')
        emit_screengroups_update(socketio, app, db, room='admins')
        return {'success': True}

    @socketio.on('displayhive:admin:cts:get_admin_screen')
    @admin_handler
    def handle_get_admin_screen(message=None):
        """Emit the current admin screen list to the requesting client.

        Either screens.page or device.page — see
        application.admin.screens.helper._screens_access.
        """
        user = current_admin_user()
        if not (has_right(db, user, 'screens.page') or has_right(db, user, 'device.page')):
            return
        emit_admin_screen(socketio, app, db, room=request.sid)

    @socketio.on('displayhive:screens:cts:toggle_monitoring')
    @require_right('screens.monitor')
    def handle_toggle_monitoring(data):
        """Toggle online monitoring for a screen."""
        (screen_id,) = fields(data, 'screen_id')
        if not screen_id:
            return {'success': False, 'error': 'screen_id is required'}

        screen = db.session.get(Screen, int(screen_id))
        if not screen:
            return {'success': False, 'error': 'Screen not found'}

        screen.monitoring_enabled = not bool(getattr(screen, 'monitoring_enabled', True))
        db.session.commit()
        logger.info('Screen "%s" monitoring_enabled=%s', screen.name, screen.monitoring_enabled)

        emit_admin_screen(socketio, app, db, room='admins')
        return {'success': True, 'monitoring_enabled': screen.monitoring_enabled}

    @socketio.on('displayhive:screens:cts:reset_screen_size')
    @require_right('screens.resize')
    def handle_reset_screen_size(data):
        """Reset a screen's resolution to the connected device's max recorded resolution."""
        (screen_id,) = fields(data, 'screen_id')
        if not screen_id:
            return {'success': False, 'error': 'screen_id is required'}

        screen = db.session.get(Screen, int(screen_id))
        if not screen:
            return {'success': False, 'error': 'Screen not found'}

        device = db.session.execute(
            db.select(Device).where(Device.screen_id == screen.id)
        ).scalars().first()
        if not device:
            return {'success': False, 'error': 'No device attached to screen'}

        max_w = getattr(device, 'max_resolution_width', None)
        max_h = getattr(device, 'max_resolution_height', None)
        if not max_w or not max_h:
            return {'success': False, 'error': 'No max resolution recorded for device'}

        screen.resolution_width = max_w
        screen.resolution_height = max_h
        db.session.commit()
        logger.info('Reset screen "%s" resolution to %sx%s', screen.name, max_w, max_h)

        emit_admin_screen(socketio, app, db, room='admins')
        return {'success': True}

    @socketio.on('displayhive:screens:cts:toggle_debug')
    @require_right('screens.debug')
    def handle_toggle_debug(data):
        """Persist the debug flag for a screen and push updated deviceconfig."""
        logger.debug('toggle_debug data=%s', data)
        screen_id, new_debug = fields(data, 'screen_id', 'debug')
        if screen_id is None or new_debug is None:
            return {'success': False, 'error': 'missing screen_id or debug'}

        screen = db.session.get(Screen, int(screen_id))
        if not screen:
            return {'success': False, 'error': 'screen not found'}

        screen.debug = bool(new_debug)
        db.session.add(screen)
        db.session.commit()
        db.session.refresh(screen)
        logger.info('Screen %s debug=%s', screen.name, screen.debug)

        try:
            device = db.session.execute(
                db.select(Device).where(Device.screen_id == screen.id)
            ).scalars().first()
            if device:
                from application.socketio_handlers.devconfig import send_upd_deviceconfig
                send_upd_deviceconfig(socketio, db, room=f'device_{device.devicekey}', device=device, screen=screen)
        except Exception:
            logger.exception('toggle_debug: failed to push deviceconfig')

        emit_admin_screen(socketio, app, db, room='admins')

        # Fire debug-mode alert
        try:
            from application.admin.alerting.sender import fire_alert
            fire_alert(db, 'screen_debug_on' if screen.debug else 'screen_debug_off', f"Screen '{screen.name}'")
        except Exception:
            logger.exception('toggle_debug: failed to fire debug alert')

        return {'success': True, 'debug': screen.debug}
