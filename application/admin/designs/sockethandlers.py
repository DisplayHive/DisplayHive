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
    from application.models import Design, DesignContainerStyle, DesignGlobalStyle, Gradient

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
                'background_color': design.background_color or '',
                'background_image_url': design.background_image_url or '',
                'background_repeat': design.background_repeat or '',
                'background_size': design.background_size or '',
                'background_opacity': design.background_opacity if design.background_opacity is not None else 100,
                'background_effect': design.background_effect or '',
                'background_effect_settings': design.background_effect_settings or '',
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
            background_color=data.get('background_color') or None,
            background_image_url=data.get('background_image_url') or None,
            background_repeat=data.get('background_repeat') or None,
            background_size=data.get('background_size') or None,
            background_opacity=data.get('background_opacity'),
            background_effect=data.get('background_effect') or None,
            background_effect_settings=data.get('background_effect_settings') or None,
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
        if 'background_color' in data:
            design.background_color = data.get('background_color') or None
        if 'background_image_url' in data:
            design.background_image_url = data.get('background_image_url') or None
        if 'background_repeat' in data:
            design.background_repeat = data.get('background_repeat') or None
        if 'background_size' in data:
            design.background_size = data.get('background_size') or None
        if 'background_opacity' in data:
            design.background_opacity = data.get('background_opacity')
        if 'background_effect' in data:
            design.background_effect = data.get('background_effect') or None
        if 'background_effect_settings' in data:
            design.background_effect_settings = data.get('background_effect_settings') or None

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

    # --- Gradients (reusable library, applied as a Design's body background) ---

    GRADIENT_TYPES = ('linear', 'radial', 'conic')

    def _serialize_gradient(g):
        import json
        try:
            stops = json.loads(g.stops or '[]')
        except Exception:
            stops = []
        return {
            'id': g.id, 'name': g.name, 'type': g.type, 'repeating': bool(g.repeating),
            'angle': g.angle, 'shape': g.shape or '', 'size': g.size or '',
            'position_x': g.position_x, 'position_y': g.position_y, 'stops': stops,
        }

    def _emit_gradients(room=None):
        gradients = db.session.execute(db.select(Gradient).order_by(Gradient.name)).scalars().all()
        socketio.emit(
            'displayhive:admin:stc:upd_gradients',
            {'data': [_serialize_gradient(g) for g in gradients]},
            room=room or 'admins',
        )

    def _apply_gradient_fields(gradient, data):
        gradient.name = data.get('name', gradient.name)
        if data.get('type') in GRADIENT_TYPES:
            gradient.type = data['type']
        if 'repeating' in data:
            gradient.repeating = bool(data['repeating'])
        if data.get('angle') is not None:
            gradient.angle = int(data['angle'])
        if 'shape' in data:
            gradient.shape = data.get('shape') or None
        if 'size' in data:
            gradient.size = data.get('size') or None
        if data.get('position_x') is not None:
            gradient.position_x = float(data['position_x'])
        if data.get('position_y') is not None:
            gradient.position_y = float(data['position_y'])
        if data.get('stops') is not None:
            import json
            gradient.stops = json.dumps(data['stops'])

    @socketio.on('displayhive:admin:cts:get_gradients')
    @require_right('designs.page')
    def get_gradients(message=None):
        _emit_gradients(room=request.sid)

    @socketio.on('displayhive:admin:cts:create_gradient')
    @require_right('designs.create')
    def handle_create_gradient(data=None):
        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        gradient = Gradient(name=data.get('name') or 'Gradient')
        _apply_gradient_fields(gradient, data)
        db.session.add(gradient)
        db.session.commit()
        _emit_gradients()
        return {'ok': True, 'id': gradient.id}

    @socketio.on('displayhive:admin:cts:update_gradient')
    @require_right('designs.edit')
    def handle_update_gradient(data=None):
        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        gradient_id = data.get('id')
        if not gradient_id:
            return {'ok': False, 'error': 'Missing id'}
        gradient = db.session.get(Gradient, int(gradient_id))
        if not gradient:
            return {'ok': False, 'error': 'Gradient not found'}

        _apply_gradient_fields(gradient, data)
        db.session.add(gradient)
        db.session.commit()
        _emit_gradients()

        # Push to screens for every Design currently using this gradient,
        # if any of them happens to be the active one.
        from application.models import DesignGradient
        design_ids = db.session.execute(
            db.select(DesignGradient.design_id).where(DesignGradient.gradient_id == gradient.id).distinct()
        ).scalars().all()
        for design in db.session.execute(db.select(Design).where(Design.id.in_(design_ids))).scalars().all():
            _push_screens_if_active(design)
        return {'ok': True}

    @socketio.on('displayhive:admin:cts:delete_gradient')
    @require_right('designs.delete')
    def handle_delete_gradient(data=None):
        from application.models import DesignGradient

        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        gradient_id = data.get('id')
        if not gradient_id:
            return {'ok': False, 'error': 'Missing id'}
        gradient = db.session.get(Gradient, int(gradient_id))
        if not gradient:
            return {'ok': False, 'error': 'Gradient not found'}

        used_by = db.session.execute(
            db.select(db.func.count()).select_from(DesignGradient).where(DesignGradient.gradient_id == gradient.id)
        ).scalar_one()
        if used_by:
            return {'ok': False, 'error': f'Gradient is used by {used_by} design(s)'}

        db.session.delete(gradient)
        db.session.commit()
        _emit_gradients()
        return {'ok': True}

    @socketio.on('displayhive:admin:cts:get_design_gradients')
    @require_right('designs.page')
    def get_design_gradients(message=None):
        """Emit the ordered list of Gradient ids applied to one Design."""
        from application.models import DesignGradient

        if not message or not isinstance(message, dict):
            return
        design_id = message.get('design_id') or message.get('id')
        if not design_id:
            return
        design_id = int(design_id)

        gradient_ids = db.session.execute(
            db.select(DesignGradient.gradient_id)
            .where(DesignGradient.design_id == design_id)
            .order_by(DesignGradient.order, DesignGradient.id)
        ).scalars().all()

        socketio.emit(
            'displayhive:admin:stc:design_gradients',
            {'design_id': design_id, 'gradient_ids': list(gradient_ids)},
            room=request.sid,
        )

    @socketio.on('displayhive:admin:cts:set_design_gradients')
    @require_right('designs.edit')
    def handle_set_design_gradients(data=None):
        """Replace the full, ordered set of Gradients applied to one Design.

        Payload: {design_id, gradient_ids: [id, ...]} — list order becomes
        the background-image stacking order (first = frontmost layer).
        """
        from application.models import DesignGradient

        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        design_id = data.get('design_id')
        gradient_ids = data.get('gradient_ids')
        if not design_id or not isinstance(gradient_ids, list):
            return {'ok': False, 'error': 'Missing design_id or gradient_ids'}

        design = db.session.get(Design, int(design_id))
        if not design:
            return {'ok': False, 'error': 'Design not found'}

        design_id = int(design_id)
        db.session.execute(db.delete(DesignGradient).where(DesignGradient.design_id == design_id))
        for order, gradient_id in enumerate(gradient_ids):
            db.session.add(DesignGradient(design_id=design_id, gradient_id=int(gradient_id), order=order))

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
