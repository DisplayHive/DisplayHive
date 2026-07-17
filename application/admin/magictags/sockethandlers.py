import logging

from flask import request

logger = logging.getLogger(__name__)


def register_admin_magictags_handlers(socketio, app, db):
    """Register socket handlers for the admin Magic Tags card."""

    from application.socketio_handlers.auth import require_right, fields
    from application.models import MagicTag, MagicTagValueList, MagicTagValueListEntry

    def _push_to_screens():
        """Re-push content to every screen so magic tag substitutions refresh.

        Magic tags are global and not tied to a specific screen/template, so
        there's no narrower set of "screens using this tag" to target - any
        screen could have a container referencing it.
        """
        try:
            from application.utils import push_content_list_to_all_screens
            push_content_list_to_all_screens(socketio, app, db)
        except Exception:
            logger.exception('Failed to push refreshed content after magic tag change')

    def _emit_magic_tags(room=None):
        with app.app_context():
            all_tags = db.session.execute(db.select(MagicTag)).scalars().all()
            payload = {'data': [{
                'id': v.id,
                'name': v.name,
                'value': v.value,
                'description': v.description or '',
                'type': v.type or 'text',
                'value_list_id': v.value_list_id,
            } for v in all_tags]}
        socketio.emit('displayhive:admin:stc:upd_magic_tags', payload, room=room or 'admins')

    def _emit_magic_tag_value_lists(room=None):
        with app.app_context():
            all_lists = db.session.execute(db.select(MagicTagValueList)).scalars().all()
            payload = {'data': [{
                'id': l.id,
                'name': l.name,
                'entries': [{'id': e.id, 'key': e.key, 'value': e.value} for e in l.entries],
            } for l in all_lists]}
        socketio.emit('displayhive:admin:stc:upd_magic_tag_value_lists', payload, room=room or 'admins')

    @socketio.on('displayhive:admin:cts:get_magic_tags')
    @require_right('magictags.page')
    def get_magic_tags(message=None):
        _emit_magic_tags(room=request.sid)

    @socketio.on('displayhive:admin:cts:create_magic_tag')
    @require_right('magictags.create')
    def handle_create_magic_tag(data=None):
        name, value, description, tag_type, value_list_id = fields(
            data, 'name', 'value', 'description', 'type', 'value_list_id'
        )
        tag = MagicTag(
            name=name or '',
            value=value or '',
            description=description or '',
            type=tag_type if tag_type in ('text', 'list') else 'text',
            value_list_id=int(value_list_id) if value_list_id else None,
        )
        db.session.add(tag)
        db.session.commit()
        _emit_magic_tags()
        _push_to_screens()

    @socketio.on('displayhive:admin:cts:update_magic_tag')
    @require_right('magictags.edit')
    def handle_update_magic_tag(data=None):
        (tag_id,) = fields(data, 'id')
        if not tag_id:
            return
        tag = db.session.get(MagicTag, int(tag_id))
        if not tag:
            return
        name, value, description, tag_type, value_list_id = fields(
            data, 'name', 'value', 'description', 'type', 'value_list_id'
        )
        tag.name = name if name is not None else tag.name
        tag.value = value if value is not None else tag.value
        tag.description = description if description is not None else tag.description
        if tag_type in ('text', 'list'):
            tag.type = tag_type
        tag.value_list_id = int(value_list_id) if value_list_id else None
        db.session.commit()
        _emit_magic_tags()
        _push_to_screens()

    @socketio.on('displayhive:admin:cts:delete_magic_tag')
    @require_right('magictags.delete')
    def handle_delete_magic_tag(data=None):
        (tag_id,) = fields(data, 'id')
        if not tag_id:
            return
        tag = db.session.get(MagicTag, int(tag_id))
        if not tag:
            return
        db.session.delete(tag)
        db.session.commit()
        _emit_magic_tags()
        _push_to_screens()

    # --- Magic Tag Value Lists ---

    @socketio.on('displayhive:admin:cts:get_magic_tag_value_lists')
    @require_right('magictagvaluelists.page')
    def get_magic_tag_value_lists(message=None):
        _emit_magic_tag_value_lists(room=request.sid)

    def _apply_entries(value_list, entries):
        """Replace value_list's entries wholesale with *entries* ([{key, value}])."""
        for e in list(value_list.entries):
            db.session.delete(e)
        for e in (entries or []):
            key = (e.get('key') if isinstance(e, dict) else None) or ''
            val = (e.get('value') if isinstance(e, dict) else None) or ''
            if not key:
                continue
            db.session.add(MagicTagValueListEntry(value_list=value_list, key=key, value=val))

    @socketio.on('displayhive:admin:cts:create_magic_tag_value_list')
    @require_right('magictagvaluelists.create')
    def handle_create_magic_tag_value_list(data=None):
        name, entries = fields(data, 'name', 'entries')
        value_list = MagicTagValueList(name=name or '')
        db.session.add(value_list)
        db.session.flush()
        _apply_entries(value_list, entries)
        db.session.commit()
        _emit_magic_tag_value_lists()

    @socketio.on('displayhive:admin:cts:update_magic_tag_value_list')
    @require_right('magictagvaluelists.edit')
    def handle_update_magic_tag_value_list(data=None):
        (list_id,) = fields(data, 'id')
        if not list_id:
            return
        value_list = db.session.get(MagicTagValueList, int(list_id))
        if not value_list:
            return
        name, entries = fields(data, 'name', 'entries')
        value_list.name = name if name is not None else value_list.name
        if entries is not None:
            _apply_entries(value_list, entries)
        db.session.commit()
        _emit_magic_tag_value_lists()
        _push_to_screens()

    @socketio.on('displayhive:admin:cts:delete_magic_tag_value_list')
    @require_right('magictagvaluelists.delete')
    def handle_delete_magic_tag_value_list(data=None):
        (list_id,) = fields(data, 'id')
        if not list_id:
            return
        value_list = db.session.get(MagicTagValueList, int(list_id))
        if not value_list:
            return
        # Detach any magic tags still pointing at this list before deleting it.
        tags_using_list = db.session.execute(
            db.select(MagicTag).where(MagicTag.value_list_id == value_list.id)
        ).scalars().all()
        for tag in tags_using_list:
            tag.value_list_id = None
        db.session.delete(value_list)
        db.session.commit()
        _emit_magic_tag_value_lists()
        if tags_using_list:
            _emit_magic_tags()
        _push_to_screens()
