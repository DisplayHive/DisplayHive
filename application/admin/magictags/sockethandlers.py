from flask import request


def register_admin_magictags_handlers(socketio, app, db):
    """Register socket handlers for the admin Magic Tags card."""

    from application.socketio_handlers.auth import require_right, fields
    from application.models import MagicTag

    def _emit_magic_tags(room=None):
        with app.app_context():
            all_tags = db.session.execute(db.select(MagicTag)).scalars().all()
            payload = {'data': [{'id': v.id, 'name': v.name, 'value': v.value, 'description': v.description or ''} for v in all_tags]}
        socketio.emit('displayhive:admin:stc:upd_magic_tags', payload, room=room or 'admins')

    @socketio.on('displayhive:admin:cts:get_magic_tags')
    @require_right('magictags.page')
    def get_magic_tags(message=None):
        _emit_magic_tags(room=request.sid)

    @socketio.on('displayhive:admin:cts:create_magic_tag')
    @require_right('magictags.create')
    def handle_create_magic_tag(data=None):
        name, value, description = fields(data, 'name', 'value', 'description')
        tag = MagicTag(name=name or '', value=value or '', description=description or '')
        db.session.add(tag)
        db.session.commit()
        _emit_magic_tags()

    @socketio.on('displayhive:admin:cts:update_magic_tag')
    @require_right('magictags.edit')
    def handle_update_magic_tag(data=None):
        (tag_id,) = fields(data, 'id')
        if not tag_id:
            return
        tag = db.session.get(MagicTag, int(tag_id))
        if not tag:
            return
        name, value, description = fields(data, 'name', 'value', 'description')
        tag.name = name if name is not None else tag.name
        tag.value = value if value is not None else tag.value
        tag.description = description if description is not None else tag.description
        db.session.commit()
        _emit_magic_tags()

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
