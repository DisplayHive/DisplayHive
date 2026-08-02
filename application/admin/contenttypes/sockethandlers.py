import logging

from flask import request

logger = logging.getLogger(__name__)


def register_admin_contenttypes_handlers(socketio, app, db):
    """Register socket handlers for the admin Contenttypes page.

    A Contenttype is bound to exactly one Layout. Each ContentContainer it
    uses is itself one field (TagConfig) with an assigned field_handler —
    there is no separate render template; a field's transformed value
    directly becomes its target container's rendered content.
    """
    from application.admin.contenttypes.helper import emit_contenttypes_update
    from application.admin.content.helper import rerender_content_element_for_contenttype
    from application.socketio_handlers.auth import require_right, admin_handler, current_admin_user
    from application.permissions import has_right
    from application.utils import push_content_list_to_all_screens
    from application.models import Contenttype, TagConfig

    def _emit_contenttypes(room=None):
        emit_contenttypes_update(socketio, app, db, room=room)

    def _allowed_container_ids(ct):
        return {c.id for c in (getattr(ct.layout, 'contentcontainers', None) or [])} if ct.layout else set()

    def _apply_tagconfigs(ct, tagcfgs):
        """Synchronise TagConfig rows on *ct*: upsert provided entries and delete any no longer present.

        Each entry's `contentcontainer_id` (the field's target container) must
        belong to `ct.layout`, if provided.
        """
        allowed_container_ids = _allowed_container_ids(ct)
        tc_by_id = {t.id: t for t in (ct.tagconfigs or []) if t.id is not None}
        tc_by_name = {t.field_name: t for t in (ct.tagconfigs or [])}

        provided_names: set[str] = set()

        for item in (tagcfgs or []):
            try:
                item_id = item.get('id')
                name = item.get('name') or item.get('field_name') or ''
                title = item.get('title') or item.get('field_label')
                order = item.get('order')
                field_handler = item.get('field_handler', 'textklein')

                contentcontainer_id = item.get('contentcontainer_id')
                try:
                    contentcontainer_id = int(contentcontainer_id) if contentcontainer_id is not None else None
                except (ValueError, TypeError):
                    contentcontainer_id = None
                if contentcontainer_id is not None and contentcontainer_id not in allowed_container_ids:
                    # Container doesn't belong to this Contenttype's Layout — drop the link, keep the field.
                    contentcontainer_id = None

                try:
                    item_id_int = int(item_id) if item_id is not None else None
                except (ValueError, TypeError):
                    item_id_int = None

                if name:
                    provided_names.add(name)

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
                    target_tc.contentcontainer_id = contentcontainer_id
                    db.session.add(target_tc)
                else:
                    db.session.add(TagConfig(
                        contenttype_id=ct.id,
                        contentcontainer_id=contentcontainer_id,
                        field_name=name,
                        field_label=title or name,
                        field_handler=field_handler,
                        order=int(order) if order is not None else 0,
                    ))
            except Exception:
                continue

        for tc in list(tc_by_name.values()):
            if tc.field_name not in provided_names:
                db.session.delete(tc)

    @socketio.on('displayhive:admin:cts:get_contenttypes')
    @admin_handler
    def get_admin_contenttypes(message=None):
        # Shared by the Content Types page (contenttypes.page) and the Content
        # editor, which needs the full contenttype list to create/edit content
        # elements (content.page) — either right is sufficient for this read.
        user = current_admin_user()
        if not (has_right(db, user, 'contenttypes.page') or has_right(db, user, 'content.page')):
            return
        _emit_contenttypes(room=request.sid)

    def _serialize_contenttype_detail(ct):
        """Build the full contenttype detail payload (used by both get and update)."""
        tagconfigs = ct.tagconfigs or []
        return {
            'id': ct.id,
            'name': ct.name,
            'description': ct.description or '',
            'layout_id': ct.layout_id,
            'tagconfigs': [
                {
                    'id': t.id,
                    'field_name': t.field_name,
                    'field_label': t.field_label,
                    'field_handler': t.field_handler,
                    'contentcontainer_id': t.contentcontainer_id,
                    'order': t.order,
                }
                for t in tagconfigs
            ],
        }

    @socketio.on('displayhive:admin:cts:get_contenttype')
    @admin_handler
    def get_contenttype(message=None):
        # Same either-right rule as get_contenttypes above.
        user = current_admin_user()
        if not (has_right(db, user, 'contenttypes.page') or has_right(db, user, 'content.page')):
            return
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
    @require_right('contenttypes.edit')
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
        if data.get('layout_id') is not None:
            ct.layout_id = int(data['layout_id'])
        db.session.add(ct)
        db.session.flush()

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
    @require_right('contenttypes.create')
    def handle_create_contenttype(data=None):
        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        name = data.get('name')
        if not name:
            return {'ok': False, 'error': 'Name is required'}
        layout_id = data.get('layout_id')
        if not layout_id:
            return {'ok': False, 'error': 'Layout is required'}

        ct = Contenttype(
            name=name,
            description=data.get('description') or '',
            layout_id=int(layout_id),
        )
        db.session.add(ct)
        db.session.flush()  # get ct.id within the same transaction

        _apply_tagconfigs(ct, data.get('tagconfigs') or [])

        db.session.commit()
        _emit_contenttypes()
        return {'ok': True, 'id': ct.id}

    @socketio.on('displayhive:admin:cts:delete_contenttype')
    @require_right('contenttypes.delete')
    def handle_delete_contenttype(data=None):
        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        ct_id = data.get('id')
        if not ct_id:
            return {'ok': False, 'error': 'Missing id'}
        ct = db.session.get(Contenttype, int(ct_id))
        if not ct:
            return {'ok': False, 'error': 'Content type not found'}

        from application.models import ContentElement
        used_by = db.session.execute(
            db.select(db.func.count()).select_from(ContentElement).where(ContentElement.contenttype_id == ct.id)
        ).scalar_one()
        if used_by:
            return {'ok': False, 'error': f'Content type is used by {used_by} content item(s)'}

        db.session.delete(ct)
        db.session.commit()
        _emit_contenttypes()
        return {'ok': True}
