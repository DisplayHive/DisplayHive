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
    from application.models import Design, DesignContainerStyle, DesignGlobalStyle

    def _emit_designs(room=None):
        """Broadcast the current designs list."""
        emit_designs_update(socketio, app, db, room=room)

    def _push_screens_if_active(design):
        # Per-container style edits only matter to screens if this Design is
        # the one currently shown — mirrors handle_update_design's own
        # isDefault-gated reload below.
        if not design.isDefault:
            return
        try:
            from application.utils import reload_devices_on_all_screens
            reload_devices_on_all_screens(socketio, db)
        except Exception:
            logger.exception('Failed to reload screens after container style change')

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

        was_default = bool(design.isDefault)
        db.session.execute(db.delete(DesignContainerStyle).where(DesignContainerStyle.design_id == design.id))
        db.session.execute(db.delete(DesignGlobalStyle).where(DesignGlobalStyle.design_id == design.id))
        db.session.delete(design)
        db.session.commit()
        _emit_designs()

        if was_default:
            try:
                from application.utils import reload_devices_on_all_screens
                reload_devices_on_all_screens(socketio, db)
            except Exception:
                logger.exception('delete_design: failed to reload screens')

    # --- Per-container style overrides (scoped key/value store) ----------

    @socketio.on('displayhive:admin:cts:get_design_container_styles')
    @require_right('designs.page')
    def get_design_container_styles(message=None):
        """Emit this Design's stored per-container style overrides.

        Payload shape: {design_id, data: {contentcontainer_id: {property: value}}}
        """
        if not message or not isinstance(message, dict):
            return
        design_id = message.get('design_id') or message.get('id')
        if not design_id:
            return
        design_id = int(design_id)

        rows = db.session.execute(
            db.select(DesignContainerStyle).where(DesignContainerStyle.design_id == design_id)
        ).scalars().all()

        by_container: dict = {}
        for row in rows:
            by_container.setdefault(str(row.contentcontainer_id), {})[row.property] = row.value or ''

        socketio.emit(
            'displayhive:admin:stc:design_container_styles',
            {'design_id': design_id, 'data': by_container},
            room=request.sid,
        )

    @socketio.on('displayhive:admin:cts:save_design_container_styles')
    @require_right('designs.edit')
    def save_design_container_styles(data=None):
        """Upsert every (property, value) pair for one container on one Design.

        Payload: {design_id, contentcontainer_id, styles: {property: value}}.
        An empty/blank value deletes that property's row (equivalent to the
        UI's "not set" option) instead of storing a blank string.
        """
        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        design_id = data.get('design_id')
        contentcontainer_id = data.get('contentcontainer_id')
        styles = data.get('styles')
        if not design_id or not contentcontainer_id or not isinstance(styles, dict):
            return {'ok': False, 'error': 'Missing design_id, contentcontainer_id or styles'}

        design = db.session.get(Design, int(design_id))
        if not design:
            return {'ok': False, 'error': 'Design not found'}

        design_id = int(design_id)
        contentcontainer_id = int(contentcontainer_id)

        existing = {
            row.property: row
            for row in db.session.execute(
                db.select(DesignContainerStyle).where(
                    DesignContainerStyle.design_id == design_id,
                    DesignContainerStyle.contentcontainer_id == contentcontainer_id,
                )
            ).scalars().all()
        }

        for prop, value in styles.items():
            value = (value or '').strip()
            row = existing.get(prop)
            if not value:
                if row:
                    db.session.delete(row)
                continue
            if row:
                row.value = value
                db.session.add(row)
            else:
                db.session.add(DesignContainerStyle(
                    design_id=design_id, contentcontainer_id=contentcontainer_id,
                    property=prop, value=value,
                ))

        db.session.commit()
        _push_screens_if_active(design)
        return {'ok': True}

    # --- Global style overrides (applies to every container) --------------

    @socketio.on('displayhive:admin:cts:get_design_global_styles')
    @require_right('designs.page')
    def get_design_global_styles(message=None):
        """Emit this Design's stored global style overrides.

        Payload shape: {design_id, data: {property: value}}
        """
        if not message or not isinstance(message, dict):
            return
        design_id = message.get('design_id') or message.get('id')
        if not design_id:
            return
        design_id = int(design_id)

        rows = db.session.execute(
            db.select(DesignGlobalStyle).where(DesignGlobalStyle.design_id == design_id)
        ).scalars().all()

        data = {row.property: row.value or '' for row in rows}

        socketio.emit(
            'displayhive:admin:stc:design_global_styles',
            {'design_id': design_id, 'data': data},
            room=request.sid,
        )

    @socketio.on('displayhive:admin:cts:save_design_global_styles')
    @require_right('designs.edit')
    def save_design_global_styles(data=None):
        """Upsert every (property, value) pair for a Design's global styles.

        Payload: {design_id, styles: {property: value}}. An empty/blank
        value deletes that property's row (the UI's "not set" option).
        """
        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        design_id = data.get('design_id')
        styles = data.get('styles')
        if not design_id or not isinstance(styles, dict):
            return {'ok': False, 'error': 'Missing design_id or styles'}

        design = db.session.get(Design, int(design_id))
        if not design:
            return {'ok': False, 'error': 'Design not found'}

        design_id = int(design_id)

        existing = {
            row.property: row
            for row in db.session.execute(
                db.select(DesignGlobalStyle).where(DesignGlobalStyle.design_id == design_id)
            ).scalars().all()
        }

        for prop, value in styles.items():
            value = (value or '').strip()
            row = existing.get(prop)
            if not value:
                if row:
                    db.session.delete(row)
                continue
            if row:
                row.value = value
                db.session.add(row)
            else:
                db.session.add(DesignGlobalStyle(design_id=design_id, property=prop, value=value))

        db.session.commit()
        _push_screens_if_active(design)
        return {'ok': True}
