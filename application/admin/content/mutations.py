"""Mutating admin socket handlers for Content — create, update, delete, move
and preview. Split out of the former monolithic ``sockethandlers`` module.
"""

import json
import logging

from flask_socketio import emit

from application.utils import push_content_list_to_all_screens
from application.utils.template import build_field_handlers
from application.models import ContentElement, ContentContainer, Contenttype

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

        container = content_element.contentcontainer or 'maincontent'
        socketio.emit('show_single_content', {
            'id': content_element.id,
            'html': content_element.html,
            'duration': content_element.duration,
            'container': container,
        }, room='screen_preview_admin')
        logger.info("Sent content_element %s to preview_admin in container '%s'", content_element_id, container)

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

    @socketio.on('displayhive:admin:cts:move_content_element_container')
    @require_right('content.move')
    def move_content_element_container(message):
        """Move a content_element to another contentcontainer if allowed for its contenttype, or unassign if target is empty"""
        content_element_id, target = fields(message, 'content_element_id', 'target_container')
        if not content_element_id:
            emit('displayhive:admin:stc:move_content_element_result', {'success': False, 'error': 'Ungültige Parameter'})
            return

        content_element = db.session.get(ContentElement, content_element_id)
        if not content_element:
            emit('displayhive:admin:stc:move_content_element_result', {'success': False, 'error': 'Content not found'})
            return

        # If target is empty or None, unassign the content
        if not target:
            content_element.contentcontainer = None
            db.session.add(content_element)
            db.session.commit()

            push_content_list_to_all_screens(socketio, app, db)

            emit('displayhive:admin:stc:move_content_element_result', {'success': True, 'content_element_id': content_element.id, 'container': None})
            return {'success': True, 'content_element_id': content_element.id, 'container': None}

        # Otherwise, move to target container. ContentElement.contentcontainer is
        # a bare name string with no template affiliation, so a container is
        # looked up by name alone — not scoped to the default (or any single)
        # template. Any contenttype may be assigned to any container.
        containers_with_name = db.session.execute(
            db.select(ContentContainer).where(ContentContainer.name == target)
        ).scalars().all()

        if not containers_with_name:
            emit('displayhive:admin:stc:move_content_element_result', {'success': False, 'error': 'Container nicht gefunden'})
            return

        content_element.contentcontainer = target
        db.session.add(content_element)
        db.session.commit()

        push_content_list_to_all_screens(socketio, app, db)

        vars_list = []
        try:
            if content_element.serialized_input:
                parsed = json.loads(content_element.serialized_input)
                for k, v in parsed.items():
                    if k not in ('contenttype_id', 'id', 'duration', 'test', 'title'):
                        vars_list.append({'key': k, 'value': str(v)})
        except Exception:
            logger.exception('move_content_element: failed to parse serialized_input')

        socketio.emit('content_element_moved', {
            'id': content_element.id,
            'title': content_element.title,
            'container': content_element.contentcontainer,
            'type': content_element.contenttype.name if content_element.contenttype else '',
            'vars': vars_list,
            'content_text': ' '.join([v['value'].lower() if isinstance(v['value'], str) else str(v['value']) for v in vars_list]),
        })

        emit('displayhive:admin:stc:move_content_element_result', {'success': True, 'content_element_id': content_element.id, 'container': content_element.contentcontainer})
        return {'success': True, 'content_element_id': content_element.id, 'container': content_element.contentcontainer}

    @socketio.on('displayhive:admin:cts:create_content_element')
    @admin_handler
    def create_content_element(message):
        """Create or update a content_element entry via Socket.IO.

        message: dict with form-like keys. If 'id' is present, update existing entry.
        Otherwise create a new ContentElement. Emits 'create_content_element_result'
        with {'success': True, 'content_element_id': id} on success.
        """
        from application.admin.content.helper import render_content_element_html

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
        selected_content = ''
        if contenttype_id:
            try:
                contenttype_obj = db.session.get(Contenttype, int(contenttype_id))
                if contenttype_obj:
                    selected_content = contenttype_obj.html
            except Exception:
                logger.exception('Error loading contenttype in socket create')

        # Build serialized representation: only custom fields, exclude metadata
        metadata_keys = ('title', 'contenttype_id', 'duration', 'id', 'contentcontainer', 'start_time', 'end_time')
        serialized_data = {
            k: v for k, v in (message.items() if isinstance(message, dict) else [])
            if k not in metadata_keys
        }

        try:
            serialized = json.dumps(serialized_data, ensure_ascii=False)
        except Exception:
            serialized = '{}'

        field_handlers = build_field_handlers(contenttype_obj)

        rendered = render_content_element_html(selected_content, serialized, field_handlers or None, db=db) if selected_content else ''

        def _resolve_container(existing_value=None):
            """Pick the container: explicit value, else keep existing, else maincontent."""
            explicit = get_val('contentcontainer', '')
            if explicit:
                return explicit
            if existing_value:
                return existing_value
            return 'maincontent'

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
            mc.contentcontainer = _resolve_container(mc.contentcontainer)
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
            contentcontainer=_resolve_container(),
        )
        content_element.active = True
        db.session.add(content_element)
        db.session.commit()
        logger.info('Created new content_element via socket: %s', title)

        push_content_list_to_all_screens(socketio, app, db)

        emit('displayhive:admin:stc:create_content_element_result', {'success': True, 'content_element_id': content_element.id})
        return {'success': True, 'content_element_id': content_element.id}
