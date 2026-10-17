"""Mutating admin socket handlers for Content — create, update, delete, and
move. Split out of the former monolithic ``sockethandlers`` module.
"""

import json
import logging

from flask_socketio import emit

from application.utils import push_content_list_to_all_screens
from application.admin.content.recurrence import dump_recurrence, normalize_recurrence
from application.models import ContentElement, Contenttype

logger = logging.getLogger(__name__)


def register_content_mutation_handlers(socketio, app, db):
    """Register the mutating Content handlers (create/update/delete/move)."""
    from application.socketio_handlers.auth import fields, current_admin_user
    from application.socketio_handlers.actions import admin_action, get_or_fail, Fail, ok
    from application.security.permissions import has_right

    def _push_upd_content(content_id):
        """Best-effort incremental push of a single content element to screens."""
        try:
            from application.socketio_handlers.upd_content import send_upd_content
            send_upd_content(socketio, db, content_ids=[content_id])
        except Exception:
            logger.exception('Failed to send upd_content for %s', content_id)

    @socketio.on('displayhive:admin:cts:update_content_element_active')
    @admin_action('content.enable')
    def update_content_element_active(message):
        """Update content_element active status. Returns ack dict for emitWithAck callers."""
        content_element_id, active = fields(message, 'content_element_id', 'active')
        content_element = get_or_fail(db, ContentElement, content_element_id, 'ContentElement')
        content_element.active = bool(active)
        db.session.add(content_element)
        db.session.commit()

        _push_upd_content(content_element_id)
        logger.info('ContentElement %s active status updated to: %s', content_element_id, active)
        return ok()

    @socketio.on('displayhive:admin:cts:update_content_element_duration')
    @admin_action('content.edit')
    def update_content_element_duration(message):
        """Update content_element duration"""
        content_element_id, duration = fields(message, 'content_element_id', 'duration')
        if duration is None:
            raise Fail('Missing duration')
        content_element = get_or_fail(db, ContentElement, content_element_id, 'ContentElement')
        try:
            content_element.duration = int(duration)
        except (TypeError, ValueError):
            raise Fail('Invalid duration')
        db.session.add(content_element)
        db.session.commit()

        _push_upd_content(content_element_id)
        logger.info('ContentElement %s duration updated to: %s', content_element_id, duration)
        return ok()

    @socketio.on('displayhive:admin:cts:delete_content_element')
    @admin_action('content.delete')
    def delete_content_element(message):
        """Delete a content_element entry"""
        (content_element_id,) = fields(message, 'content_element_id')
        content_element = get_or_fail(db, ContentElement, content_element_id, 'ContentElement')
        db.session.delete(content_element)
        db.session.commit()

        push_content_list_to_all_screens(socketio, app, db)
        logger.info('ContentElement %s deleted', content_element_id)
        return ok()

    @socketio.on('displayhive:admin:cts:update_content_fields')
    @admin_action('content.edit')
    def update_content_fields(message):
        """Change some field values of a content element and leave everything else as it is.

        message: ``{content_element_id, fields: {field key: value}}``. The values are merged into the
        element's ``serialized_input`` (keys are a content type's field names and their ``__suffix``
        sub-values) and the element is rendered again; what a content type locks or hides is enforced by
        that rendering, as for every other save. Used by editing in the previews of the content list.
        """
        from application.admin.content.helper import render_content_fields

        content_element_id, values = fields(message, 'content_element_id', 'fields')
        element = get_or_fail(db, ContentElement, content_element_id, 'Content')
        if not isinstance(values, dict) or not values:
            raise Fail('Nothing to change')
        try:
            stored = json.loads(element.serialized_input or '{}')
        except (ValueError, TypeError):
            stored = {}
        if not isinstance(stored, dict):
            stored = {}
        tagconfigs = element.contenttype.tagconfigs if element.contenttype else []
        allowed = {t.field_name for t in tagconfigs if t.field_name}
        locked = set()      # what the content type locks or hides: not changeable per content
        for t in tagconfigs:
            try:
                flags = json.loads(t.option_flags) if t.option_flags else {}
            except (ValueError, TypeError):
                flags = {}
            for flag_key, flag in (flags.items() if isinstance(flags, dict) else []):
                if isinstance(flag, dict) and (flag.get('locked') or flag.get('hidden')):
                    locked.add(flag_key)
        for key, value in values.items():
            if not any(key == name or str(key).startswith(name + '_') for name in allowed):
                raise Fail(f'"{key}" is not a field of this content type')
            if key in locked:
                raise Fail(f'"{key}" is locked by the content type')
            stored[key] = value
        element.serialized_input = json.dumps(stored, ensure_ascii=False)
        element.html = json.dumps(render_content_fields(tagconfigs, element.serialized_input, db=db), ensure_ascii=False)
        db.session.commit()
        push_content_list_to_all_screens(socketio, app, db)
        return ok()

    @socketio.on('displayhive:admin:cts:update_content_delivery')
    @admin_action('content.edit')
    def update_content_delivery(message):
        """Change when a content element is shown (start, end, weekly windows) and nothing else.

        message: ``{content_element_id, start_time, end_time, recurrence}`` — the formats
        ``create_content_element`` takes. Used by the delivery settings of the content list.
        """
        from datetime import datetime as _dt

        content_element_id, start_raw, end_raw, windows = fields(message, 'content_element_id', 'start_time', 'end_time', 'recurrence')
        element = get_or_fail(db, ContentElement, content_element_id, 'Content')

        def parse(value):
            if not value:
                return None
            for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
                try:
                    return _dt.strptime(str(value).strip(), fmt)
                except ValueError:
                    continue
            raise Fail(f'"{value}" is not a date and time')

        try:
            recurrence = dump_recurrence(normalize_recurrence(windows))
        except ValueError as problem:
            raise Fail(str(problem)) from None
        start, end = parse(start_raw), parse(end_raw)
        if start and end and end <= start:
            end = None
        element.start_time, element.end_time, element.recurrence = start, end, recurrence
        db.session.commit()
        push_content_list_to_all_screens(socketio, app, db)
        return ok()

    @socketio.on('displayhive:admin:cts:create_content_element')
    @admin_action()
    def create_content_element(message):
        """Create or update a content_element entry via Socket.IO.

        message: dict with form-like keys. If 'id' is present, update existing entry.
        Otherwise create a new ContentElement. Emits 'create_content_element_result'
        with {'success': True, 'content_element_id': id} on success.
        """
        from application.admin.content.helper import render_content_fields

        message = message if isinstance(message, dict) else {}

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
            raise Fail('Permission denied')

        edit_id = get_val('id')
        contenttype_id = get_val('contenttype_id')
        title = get_val('title', '')
        duration = get_val('duration', 10)

        try:
            duration = int(duration)
        except (ValueError, TypeError):
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
        try:
            recurrence = dump_recurrence(normalize_recurrence(get_val('recurrence')))
        except ValueError as problem:
            raise Fail(str(problem)) from None

        # Load contenttype if provided
        contenttype_obj = None
        if contenttype_id:
            try:
                contenttype_obj = db.session.get(Contenttype, int(contenttype_id))
            except Exception:
                logger.exception('Error loading contenttype in socket create')

        # Build serialized representation: only custom fields, exclude metadata
        metadata_keys = ('title', 'contenttype_id', 'duration', 'id', 'start_time', 'end_time', 'recurrence')
        serialized_data = {
            k: v for k, v in (message.items() if isinstance(message, dict) else [])
            if k not in metadata_keys
        }

        try:
            serialized = json.dumps(serialized_data, ensure_ascii=False)
        except (ValueError, TypeError):
            serialized = '{}'

        # Each field (TagConfig) on the contenttype targets one container;
        # its transformed value directly becomes that container's rendered
        # content — keyed by contentcontainer_id for the rendering pipeline.
        tagconfigs = getattr(contenttype_obj, 'tagconfigs', None) or []
        rendered_by_container = render_content_fields(tagconfigs, serialized, db=db)
        rendered = json.dumps(rendered_by_container, ensure_ascii=False)

        if edit_id:
            mc = get_or_fail(db, ContentElement, edit_id, 'Content')
            mc.title = title
            mc.html = rendered
            mc.duration = duration
            mc.start_time = start_time
            mc.end_time = end_time
            mc.recurrence = recurrence
            mc.serialized_input = serialized
            mc.contenttype_id = contenttype_obj.id if contenttype_obj else None
            db.session.add(mc)
            db.session.commit()

            push_content_list_to_all_screens(socketio, app, db)

            emit('displayhive:admin:stc:create_content_element_result', {'success': True, 'content_element_id': mc.id})
            return ok(content_element_id=mc.id)

        content_element = ContentElement(
            title=title,
            html=rendered,
            duration=duration,
            start_time=start_time,
            end_time=end_time,
            recurrence=recurrence,
            serialized_input=serialized,
            contenttype_id=contenttype_obj.id if contenttype_obj else None,
        )
        content_element.active = True
        db.session.add(content_element)
        db.session.commit()
        logger.info('Created new content_element via socket: %s', title)

        push_content_list_to_all_screens(socketio, app, db)

        emit('displayhive:admin:stc:create_content_element_result', {'success': True, 'content_element_id': content_element.id})
        return ok(content_element_id=content_element.id)
