import logging

from flask import request

logger = logging.getLogger(__name__)


def register_admin_contenttypes_handlers(socketio, app, db):
    """Register socket handlers for the admin Contenttypes page."""
    from application.admin.contenttypes.helper import emit_contenttypes_update
    from application.admin.content.helper import rerender_content_element_for_contenttype
    from application.socketio_handlers.auth import admin_handler
    from application.utils import push_content_list_to_all_screens
    from application.models import Contenttype, ContentContainer, TagConfig

    def _emit_contenttypes(room=None):
        emit_contenttypes_update(socketio, app, db, room=room)

    def _resolve_container_ids(container_ids):
        """Return ContentContainer objects for the given list of ids."""
        ids = list(dict.fromkeys(
            int(cid) for cid in container_ids
            if str(cid).isdigit() or isinstance(cid, int)
        ))
        if not ids:
            return []
        return db.session.execute(
            db.select(ContentContainer).where(ContentContainer.id.in_(ids))
        ).scalars().all()

    def _apply_tagconfigs(ct, tagcfgs):
        """Synchronise TagConfig rows: upsert provided entries and delete any that are no longer present."""
        container_by_id = {c.id: c for c in getattr(ct, 'contentcontainers', []) if c.id is not None}
        container_by_name = {c.name: c for c in getattr(ct, 'contentcontainers', [])}
        tc_by_id = {t.id: t for t in getattr(ct, 'tagconfigs', []) if t.id is not None}
        tc_by_name = {t.field_name: t for t in getattr(ct, 'tagconfigs', [])}

        provided_names: set[str] = set()

        for item in (tagcfgs or []):
            try:
                item_id = item.get('id')
                name = item.get('name') or ''
                title = item.get('title')
                order = item.get('order')
                field_handler = item.get('field_handler', 'textklein')

                try:
                    item_id_int = int(item_id) if item_id is not None else None
                except (ValueError, TypeError):
                    item_id_int = None

                if name:
                    provided_names.add(name)

                # Update linked ContentContainer metadata
                target_container = (
                    container_by_id.get(item_id_int) if item_id_int else None
                ) or container_by_name.get(name)
                if target_container:
                    if title is not None:
                        target_container.title = title
                    if order is not None:
                        try:
                            target_container.order = int(order)
                        except (ValueError, TypeError):
                            pass
                    db.session.add(target_container)

                # Upsert TagConfig
                target_tc = (
                    tc_by_id.get(item_id_int) if item_id_int else None
                ) or tc_by_name.get(name)
                if target_tc:
                    if title is not None:
                        target_tc.field_label = title
                    if order is not None:
                        try:
                            target_tc.order = int(order)
                        except (ValueError, TypeError):
                            pass
                    if field_handler is not None:
                        target_tc.field_handler = field_handler
                    db.session.add(target_tc)
                else:
                    db.session.add(TagConfig(
                        contenttype_id=ct.id,
                        field_name=name,
                        field_label=title or name,
                        field_handler=field_handler,
                        order=int(order) if order is not None else 0,
                    ))
            except Exception:
                continue

        # Delete TagConfig rows that are no longer in the provided list
        for tc in list(tc_by_name.values()):
            if tc.field_name not in provided_names:
                db.session.delete(tc)

    @socketio.on('displayhive:admin:cts:get_contenttypes')
    @admin_handler
    def get_admin_contenttypes(message=None):
        _emit_contenttypes(room=request.sid)

    def _serialize_contenttype_detail(ct):
        """Build the full contenttype detail payload (used by both get and update)."""
        containers = getattr(ct, 'contentcontainers', []) or []
        tagconfigs = getattr(ct, 'tagconfigs', []) or []
        return {
            'id': ct.id,
            'name': ct.name,
            'description': ct.description or '',
            'html': ct.html or '',
            'css': getattr(ct, 'css', None) or '',
            'container_ids': [c.id for c in containers],
            'containers': [
                {
                    'id': c.id,
                    'name': c.name,
                    'title': c.title or c.name,
                    'order': c.order,
                    'template_name': getattr(getattr(c, 'template', None), 'name', None),
                }
                for c in containers
            ],
            'tagconfigs': [
                {
                    'id': t.id,
                    'field_name': t.field_name,
                    'field_label': t.field_label,
                    'field_handler': t.field_handler,
                    'order': t.order,
                }
                for t in tagconfigs
            ],
        }

    @socketio.on('displayhive:admin:cts:get_contenttype')
    @admin_handler
    def get_contenttype(message=None):
        if not message or not isinstance(message, dict):
            return
        ct_id = message.get('id') or message.get('contenttype_id')
        if not ct_id:
            return
        ct = db.session.get(Contenttype, int(ct_id))
        if not ct:
            return
        payload = {'contenttype': _serialize_contenttype_detail(ct)}
        socketio.emit('displayhive:admin:stc:contenttype_detail', payload, room=request.sid)

    @socketio.on('displayhive:admin:cts:update_contenttype')
    @admin_handler
    def handle_update_contenttype(data=None):
        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        ct_id = data.get('id')
        if not ct_id:
            return {'ok': False, 'error': 'Missing id'}
        ct = db.session.get(Contenttype, int(ct_id))
        if not ct:
            return {'ok': False, 'error': 'Contenttype not found'}

        ct.name = data.get('name', ct.name)
        ct.description = data.get('description', ct.description)
        ct.html = data.get('html', ct.html)
        ct.css = data.get('css', getattr(ct, 'css', None) or '')

        container_ids = data.get('container_ids')
        if container_ids is not None:
            try:
                ct.contentcontainers = _resolve_container_ids(container_ids)
            except Exception:
                logger.exception('update_contenttype: failed to resolve container ids')

        _apply_tagconfigs(ct, data.get('tagconfigs') or [])

        db.session.commit()

        payload = {'contenttype': _serialize_contenttype_detail(ct)}
        socketio.emit('displayhive:admin:stc:contenttype_detail', payload, room=request.sid)
        _emit_contenttypes()

        try:
            updated_ids = rerender_content_element_for_contenttype(db, ct.id)
            if updated_ids:
                push_content_list_to_all_screens(socketio, app, db)
                logger.info('Pushed re-rendered content to screens for %s items', len(updated_ids))
        except Exception:
            logger.exception('update_contenttype: failed to re-render content')

        return {'ok': True}

    @socketio.on('displayhive:admin:cts:create_contenttype')
    @admin_handler
    def handle_create_contenttype(data=None):
        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        name = data.get('name')
        if not name:
            return {'ok': False, 'error': 'Name is required'}

        ct = Contenttype(
            name=name,
            description=data.get('description') or '',
            html=data.get('html') or '',
            css=data.get('css') or '',
        )
        db.session.add(ct)
        db.session.flush()  # get ct.id within the same transaction

        container_ids = data.get('container_ids')
        if container_ids is not None:
            try:
                ct.contentcontainers = _resolve_container_ids(container_ids)
            except Exception:
                logger.exception('create_contenttype: failed to resolve container ids')

        _apply_tagconfigs(ct, data.get('tagconfigs') or [])

        db.session.commit()
        _emit_contenttypes()
        return {'ok': True}

    @socketio.on('displayhive:admin:cts:delete_contenttype')
    @admin_handler
    def handle_delete_contenttype(data=None):
        if not data or not isinstance(data, dict):
            return
        ct_id = data.get('id')
        if not ct_id:
            return
        ct = db.session.get(Contenttype, int(ct_id))
        if not ct:
            return
        db.session.delete(ct)
        db.session.commit()
        _emit_contenttypes()
