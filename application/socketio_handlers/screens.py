"""Socket.IO handlers for screen-related events."""

import logging

from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)


def register_screen_handlers(socketio, app, db):
    """Register all screen-related socket.io event handlers."""

    from application.models import Screen, Screengroup, Device
    from application.utils import emit_zuweisungen_matrix_update, reload_devices_on_screen
    from application.socketio_handlers.auth import admin_handler, require_right, current_admin_user
    from application.permissions import has_right
    from flask import request

    def _reload_devices_on_screen(screen):
        reload_devices_on_screen(socketio, db, screen)

    @socketio.on('displayhive:screens:cts:reload_screen')
    @require_right('screens.reload')
    def reload_screen(message):
        """Send a RELOAD command to all devices attached to the named screen."""
        screen_name = message.get('name', '').replace('?', '')
        if not screen_name:
            return
        screen_obj = db.session.execute(
            db.select(Screen).where(Screen.name == screen_name).order_by(Screen.lastseen.desc())
        ).scalars().first()
        if screen_obj:
            _reload_devices_on_screen(screen_obj)

    @socketio.on('displayhive:screens:cts:reload_all_screens')
    @require_right('screens.reload_all')
    def reload_all_screens(message):
        """Send a RELOAD command to devices on every screen."""
        screens = db.session.execute(db.select(Screen)).scalars().all()
        for screen in screens:
            _reload_devices_on_screen(screen)
        logger.info('Reload command sent to all %s screens', len(screens))

    @socketio.on('displayhive:screens:cts:get_screen_screengroups')
    @admin_handler
    def get_screen_screengroups(message):
        """Fetch all screengroups and the current screen's assignments.

        Feeds the screen edit dialog, so either screens.page or screens.edit
        is sufficient (a plain read, not itself a mutation).
        """
        user = current_admin_user()
        if not (has_right(db, user, 'screens.page') or has_right(db, user, 'screens.edit')):
            return
        screen_id = message.get('screen_id')

        all_screengroups = db.session.execute(
            db.select(Screengroup).where(Screengroup.is_one_screen == False)
        ).scalars().all()
        screengroups_data = [{'id': sg.id, 'name': sg.name} for sg in all_screengroups]

        screen = db.session.get(Screen, screen_id)
        if not screen:
            socketio.emit('displayhive:screens:stc:screen_screengroups', {'error': 'Screen not found'}, room=request.sid)
            return
        current_screengroup_ids = [sg.id for sg in screen.screengroups]

        socketio.emit('displayhive:screens:stc:screen_screengroups', {
            'all_screengroups': screengroups_data,
            'current_screengroups': current_screengroup_ids
        }, room=request.sid)

    @socketio.on('displayhive:screens:cts:rename_screen')
    @require_right('screens.edit')
    def rename_screen(message):
        """Rename a screen and update its screengroups"""
        screen_id = message.get('id')
        old_name = message.get('old_name', '')
        new_name = message.get('new_name', '').strip()
        screengroup_ids = message.get('screengroup_ids', [])
        template_id = message.get('template_id', None)

        if old_name.startswith('preview_'):
            logger.warning('Blocked attempt to rename preview screen: %s', old_name)
            return

        if not new_name:
            return

        screen = db.session.get(Screen, screen_id)
        if not screen:
            logger.warning('rename_screen: screen %s not found', screen_id)
            return

        screen.name = new_name
        screen.template_id = int(template_id) if template_id else None

        if screengroup_ids:
            groups = db.session.execute(
                db.select(Screengroup).where(Screengroup.id.in_(screengroup_ids))
            ).scalars().all()
            screen.screengroups = groups
        else:
            screen.screengroups = []

        one_sg = db.session.execute(
            db.select(Screengroup)
            .where(Screengroup.name == old_name)
            .where(Screengroup.is_one_screen == True)
        ).scalar_one_or_none()
        if one_sg:
            one_sg.name = new_name

        db.session.add(screen)
        db.session.commit()

        try:
            from application.admin.screens.helper import emit_admin_screen
            emit_admin_screen(socketio, app, db)
        except Exception:
            logger.exception('rename_screen: failed to emit admin screen list')

        emit_zuweisungen_matrix_update(socketio, db)

        try:
            from .devconfig import send_upd_deviceconfig
            from application.socketio_handlers.upd_content import send_upd_content
            fresh_screen = db.session.execute(
                db.select(Screen)
                .options(joinedload(Screen.screengroups))
                .where(Screen.id == screen.id)
            ).unique().scalar_one_or_none() or screen
            devices = db.session.execute(db.select(Device).where(Device.screen_id == screen.id)).scalars().all()
            for device in devices:
                if getattr(device, 'devicekey', None):
                    send_upd_deviceconfig(socketio, db, room=f'device_{device.devicekey}', device=device, screen=fresh_screen)
            send_upd_content(socketio, db, screens=[fresh_screen])
        except Exception:
            logger.exception('rename_screen: failed to push config/content')

        logger.info("Screen renamed from '%s' to '%s' with %s screengroups", old_name, new_name, len(screengroup_ids))
