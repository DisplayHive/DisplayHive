"""Mutating admin socket handlers for Content — create, update, delete, move
and preview. Split out of the former monolithic ``sockethandlers`` module.
"""

import json
import logging

from flask_socketio import emit

from application.utils import push_content_list_to_all_screens
from application.models import ContentElement, Contenttype

logger = logging.getLogger(__name__)


def register_content_mutation_handlers(socketio, app, db):
    """Register the mutating Content handlers (create/update/delete/move/preview)."""
    from application.socketio_handlers.auth import admin_handler, fields, require_right, current_admin_user
    from application.permissions import has_right

    def _push_upd_content(content_id):
        """Best-effort incremental push of a single content element to screens."""
        try:
            from application.socketio_handlers.upd_content import send_upd_content
            send_upd_content(socketio, db, content_ids=[content_id])
        except Exception:
            logger.exception('Failed to send upd_content for %s', content_id)

    @socketio.on('displayhive:admin:cts:update_content_element_active')
    @require_right('content.enable')
    def update_content_element_active(message):
        """Update content_element active status. Returns ack dict for emitWithAck callers."""
        content_element_id, active = fields(message, 'content_element_id', 'active')
        if not content_element_id:
            return {'success': False, 'error': 'Missing content_element_id'}

        content_element = db.session.get(ContentElement, content_element_id)
        if not content_element:
            return {'success': False, 'error': 'ContentElement not found'}
        content_element.active = bool(active)
        db.session.add(content_element)
        db.session.commit()

        _push_upd_content(content_element_id)
        logger.info('ContentElement %s active status updated to: %s', content_element_id, active)
        return {'success': True}

    @socketio.on('displayhive:admin:cts:update_content_element_duration')
    @require_right('content.edit')
    def update_content_element_duration(message):
        """Update content_element duration"""
        content_element_id, duration = fields(message, 'content_element_id', 'duration')
        if not content_element_id or duration is None:
            return

        content_element = db.session.get(ContentElement, content_element_id)
        if not content_element:
            return
        content_element.duration = int(duration)
        db.session.add(content_element)
        db.session.commit()

        _push_upd_content(content_element_id)
        logger.info('ContentElement %s duration updated to: %s', content_element_id, duration)

    @socketio.on('displayhive:admin:cts:show_content_element_in_preview')
    @admin_handler
    def show_content_element_in_preview(message):
        """Send specific content_element to the preview_admin screen"""
        (content_element_id,) = fields(message, 'content_element_id')
        if not content_element_id:
            return

        content_element = db.session.get(ContentElement, content_element_id)
        if not content_element:
            return

        socketio.emit('show_single_content', {
            'id': content_element.id,
            'html': content_element.html,
            'duration': content_element.duration,
        }, room='screen_preview_admin')
        logger.info('Sent content_element %s to preview_admin', content_element_id)

    @socketio.on('displayhive:admin:cts:delete_content_element')
    @require_right('content.delete')
    def delete_content_element(message):
        """Delete a content_element entry"""
        (content_element_id,) = fields(message, 'content_element_id')
        if not content_element_id:
            return

        content_element = db.session.get(ContentElement, content_element_id)
        if not content_element:
            return
        db.session.delete(content_element)
        db.session.commit()

        push_content_list_to_all_screens(socketio, app, db)
        logger.info('ContentElement %s deleted', content_element_id)

    @socketio.on('displayhive:admin:cts:create_content_element')
    @admin_handler
    def create_content_element(message):
        """Create or update a content_element entry via Socket.IO.

        message: dict with form-like keys. If 'id' is present, update existing entry.
        Otherwise create a new ContentElement. Emits 'create_content_element_result'
        with {'success': True, 'content_element_id': id} on success.
        """
        from application.admin.content.helper import render_content_fields

        # helper to safely get values
        def get_val(k, default=None):
            """Return message[k] when set, otherwise *default*."""
            v = message.get(k)
            return v if v is not None else default

        # This single handler covers both create and update, gated by separate
        # rights: creating a new element needs content.create, editing an
        # existing one needs content.edit.
        required_right = 'content.edit' if message.get('id') else 'content.create'
        if not has_right(db, current_admin_user(), required_right):
            return {'success': False, 'error': 'Permission denied'}

        edit_id = get_val('id')
        contenttype_id = get_val('contenttype_id')
        title = get_val('title', '')
        duration = get_val('duration', 10)

        try:
            duration = int(duration)
        except Exception:
            duration = 0

        # Parse optional ISO datetime strings for scheduling
        from datetime import datetime as _dt

        def _parse_dt(val):
            """Parse an ISO-ish datetime string to a datetime object, or return None."""
            if not val:
                return None
            for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
                try:
                    return _dt.strptime(str(val).strip(), fmt)
                except ValueError:
                    continue
            return None

        start_time = _parse_dt(get_val('start_time'))
        end_time = _parse_dt(get_val('end_time'))

        # Load contenttype if provided
        contenttype_obj = None
        if contenttype_id:
            try:
                contenttype_obj = db.session.get(Contenttype, int(contenttype_id))
            except Exception:
                logger.exception('Error loading contenttype in socket create')

        # Build serialized representation: only custom fields, exclude metadata
        metadata_keys = ('title', 'contenttype_id', 'duration', 'id', 'start_time', 'end_time')
        serialized_data = {
            k: v for k, v in (message.items() if isinstance(message, dict) else [])
            if k not in metadata_keys
        }

        try:
            serialized = json.dumps(serialized_data, ensure_ascii=False)
        except Exception:
            serialized = '{}'

        # Each field (TagConfig) on the contenttype targets one container;
        # its transformed value directly becomes that container's rendered
        # content — keyed by contentcontainer_id for the rendering pipeline.
        tagconfigs = getattr(contenttype_obj, 'tagconfigs', None) or []
        rendered_by_container = render_content_fields(tagconfigs, serialized, db=db)
        rendered = json.dumps(rendered_by_container, ensure_ascii=False)

        if edit_id:
            mc = db.session.get(ContentElement, int(edit_id))
            if not mc:
                return {'success': False, 'error': 'Content not found'}
            mc.title = title
            mc.html = rendered
            mc.duration = duration
            mc.start_time = start_time
            mc.end_time = end_time
            mc.serialized_input = serialized
            mc.contenttype_id = contenttype_obj.id if contenttype_obj else None
            db.session.add(mc)
            db.session.commit()

            push_content_list_to_all_screens(socketio, app, db)

            emit('displayhive:admin:stc:create_content_element_result', {'success': True, 'content_element_id': mc.id})
            return {'success': True, 'content_element_id': mc.id}

        content_element = ContentElement(
            title=title,
            html=rendered,
            duration=duration,
            start_time=start_time,
            end_time=end_time,
            serialized_input=serialized,
            contenttype_id=contenttype_obj.id if contenttype_obj else None,
        )
        content_element.active = True
        db.session.add(content_element)
        db.session.commit()
        logger.info('Created new content_element via socket: %s', title)

        push_content_list_to_all_screens(socketio, app, db)

        emit('displayhive:admin:stc:create_content_element_result', {'success': True, 'content_element_id': content_element.id})
        return {'success': True, 'content_element_id': content_element.id}
