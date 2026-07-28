import logging

from flask import request

logger = logging.getLogger(__name__)


def register_admin_layouts_handlers(socketio, app, db):
    """Register socket handlers for the admin Layouts page.

    A Layout is a named, reusable group of ContentContainers (standalone
    entities with an explicit vh/vw position+size). Layout is purely an
    admin-side organizational concept — it scopes which containers a
    Contenttype's handlers may target; it has no runtime "screen uses this
    Layout" meaning.
    """
    from application.admin.layouts.helper import emit_layouts_update, emit_containers_update
    from application.socketio_handlers.auth import require_right
    from application.models import Layout, ContentContainer

    def _emit_layouts(room=None):
        emit_layouts_update(socketio, app, db, room=room)

    def _emit_containers(room=None):
        emit_containers_update(socketio, app, db, room=room)

    def _resolve_container_ids(container_ids):
        ids = list(dict.fromkeys(
            int(cid) for cid in (container_ids or [])
            if str(cid).isdigit() or isinstance(cid, int)
        ))
        if not ids:
            return []
        return db.session.execute(
            db.select(ContentContainer).where(ContentContainer.id.in_(ids))
        ).scalars().all()

    # --- Layouts ---------------------------------------------------------

    @socketio.on('displayhive:admin:cts:get_layouts')
    @require_right('layouts.page')
    def get_admin_layouts(message=None):
        _emit_layouts(room=request.sid)

    @socketio.on('displayhive:admin:cts:create_layout')
    @require_right('layouts.create')
    def handle_create_layout(data=None):
        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        layout = Layout(name=data.get('name', ''), description=data.get('description', ''))
        db.session.add(layout)
        db.session.flush()
        layout.contentcontainers = _resolve_container_ids(data.get('container_ids'))
        db.session.commit()
        _emit_layouts()
        return {'ok': True, 'id': layout.id}

    @socketio.on('displayhive:admin:cts:update_layout')
    @require_right('layouts.edit')
    def handle_update_layout(data=None):
        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        layout_id = data.get('id')
        if not layout_id:
            return {'ok': False, 'error': 'Missing id'}
        layout = db.session.get(Layout, int(layout_id))
        if not layout:
            return {'ok': False, 'error': 'Layout not found'}

        layout.name = data.get('name', layout.name)
        layout.description = data.get('description', layout.description)
        container_ids = data.get('container_ids')
        if container_ids is not None:
            layout.contentcontainers = _resolve_container_ids(container_ids)

        db.session.add(layout)
        db.session.commit()
        _emit_layouts()
        return {'ok': True}

    @socketio.on('displayhive:admin:cts:delete_layout')
    @require_right('layouts.delete')
    def handle_delete_layout(data=None):
        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        layout_id = data.get('id')
        if not layout_id:
            return {'ok': False, 'error': 'Missing id'}
        layout = db.session.get(Layout, int(layout_id))
        if not layout:
            return {'ok': False, 'error': 'Layout not found'}
        if layout.contenttypes:
            return {'ok': False, 'error': f'Layout is used by {len(layout.contenttypes)} content type(s)'}
        db.session.delete(layout)
        db.session.commit()
        _emit_layouts()
        return {'ok': True}

    # --- Content Containers (standalone entities) -------------------------

    @socketio.on('displayhive:admin:cts:get_containers')
    @require_right('layouts.page')
    def get_admin_containers(message=None):
        _emit_containers(room=request.sid)

    @socketio.on('displayhive:admin:cts:create_container')
    @require_right('layouts.create')
    def handle_create_container(data=None):
        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        container = ContentContainer(
            name=data.get('name', ''),
            title=data.get('title', ''),
            order=int(data.get('order') or 0),
            top=float(data.get('top') or 0),
            left=float(data.get('left') or 0),
            width=float(data.get('width') or 100),
            height=float(data.get('height') or 100),
        )
        db.session.add(container)
        db.session.commit()
        _emit_containers()
        return {'ok': True, 'id': container.id}

    @socketio.on('displayhive:admin:cts:update_container')
    @require_right('layouts.edit')
    def handle_update_container(data=None):
        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        container_id = data.get('id')
        if not container_id:
            return {'ok': False, 'error': 'Missing id'}
        container = db.session.get(ContentContainer, int(container_id))
        if not container:
            return {'ok': False, 'error': 'Container not found'}

        container.name = data.get('name', container.name)
        container.title = data.get('title', container.title)
        for field in ('order',):
            if data.get(field) is not None:
                setattr(container, field, int(data[field]))
        for field in ('top', 'left', 'width', 'height'):
            if data.get(field) is not None:
                setattr(container, field, float(data[field]))

        db.session.add(container)
        db.session.commit()
        _emit_containers()
        return {'ok': True}

    @socketio.on('displayhive:admin:cts:delete_container')
    @require_right('layouts.delete')
    def handle_delete_container(data=None):
        from application.models import TagConfig

        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        container_id = data.get('id')
        if not container_id:
            return {'ok': False, 'error': 'Missing id'}
        container = db.session.get(ContentContainer, int(container_id))
        if not container:
            return {'ok': False, 'error': 'Container not found'}
        used_by = db.session.execute(
            db.select(db.func.count()).select_from(TagConfig).where(TagConfig.contentcontainer_id == container.id)
        ).scalar_one()
        if used_by:
            return {'ok': False, 'error': f'Container is used by {used_by} field(s)'}
        db.session.delete(container)
        db.session.commit()
        _emit_containers()
        return {'ok': True}
