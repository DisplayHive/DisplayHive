import logging

from flask import request

logger = logging.getLogger(__name__)


def register_admin_designs_handlers(socketio, app, db):
    """Register socket handlers for the admin Designs page.

    A Design is a single global skin (html/css); exactly one is marked
    active/default at a time (flipped via the Settings page, see
    application/admin/settings/sockethandlers.py). Containers/layout are
    a separate concern — see application/admin/layouts.
    """
    from application.admin.designs.helper import emit_designs_update
    from application.socketio_handlers.auth import require_right
    from application.models import Design

    def _emit_designs(room=None):
        """Broadcast the current designs list."""
        emit_designs_update(socketio, app, db, room=room)

    @socketio.on('displayhive:admin:cts:get_designs')
    @require_right('designs.page')
    def get_admin_designs(message=None):
        """Emit the current designs list to the requesting client."""
        _emit_designs(room=request.sid)

    @socketio.on('displayhive:admin:cts:get_design')
    @require_right('designs.page')
    def get_design(message=None):
        """Emit full design detail (including html and css) for a single design id."""
        if not message or not isinstance(message, dict):
            return
        design_id = message.get('id') or message.get('design_id')
        if not design_id:
            return
        design = db.session.get(Design, int(design_id))
        if not design:
            return
        payload = {
            'design': {
                'id': design.id,
                'name': design.name,
                'description': design.description or '',
                'html': design.html or '',
                'css': design.css or '',
                'is_default': bool(getattr(design, 'isDefault', False)),
            }
        }
        socketio.emit('displayhive:admin:stc:design_detail', payload, room=request.sid)

    @socketio.on('displayhive:admin:cts:create_design')
    @require_right('designs.create')
    def handle_create_design(data=None):
        """Create a design from socket payload."""
        if not data or not isinstance(data, dict):
            return

        design = Design(
            name=data.get('name', ''),
            description=data.get('description', ''),
            html=data.get('html', ''),
            css=data.get('css', ''),
        )
        db.session.add(design)
        db.session.commit()
        _emit_designs()

    @socketio.on('displayhive:admin:cts:update_design')
    @require_right('designs.edit')
    def handle_update_design(data=None):
        """Update a design from socket payload."""
        if not data or not isinstance(data, dict):
            return
        design_id = data.get('id')
        if not design_id:
            return

        design = db.session.get(Design, int(design_id))
        if not design:
            return

        design.name = data.get('name', design.name)
        design.description = data.get('description', design.description)
        design.html = data.get('html', design.html)
        design.css = data.get('css', design.css)

        db.session.add(design)
        db.session.commit()
        _emit_designs()

        if design.isDefault:
            try:
                from application.utils import reload_devices_on_all_screens
                reload_devices_on_all_screens(socketio, db)
            except Exception:
                logger.exception('update_design: failed to reload screens')

    @socketio.on('displayhive:admin:cts:delete_design')
    @require_right('designs.delete')
    def handle_delete_design(data=None):
        """Delete a design by id (socket)."""
        if not data or not isinstance(data, dict):
            return
        design_id = data.get('id') or data.get('design_id')
        if not design_id:
            return

        design = db.session.get(Design, int(design_id))
        if not design:
            return

        db.session.delete(design)
        db.session.commit()
        _emit_designs()
