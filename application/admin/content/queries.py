"""Read-only admin socket handlers for Content — media pickers and
content listings. Split out of the former monolithic ``sockethandlers`` module.

Container listing/CRUD lives in the Layouts admin domain
(``application/admin/layouts``) now that containers are standalone entities
scoped to a Layout rather than owned by a Design.
"""

import json
import logging

from flask import request
from sqlalchemy.orm import joinedload, selectinload

from application.admin.content.serializers import (
    resolve_preview_css,
    build_content_dict,
    fmt_dt,
)
from application.models import ContentElement
from application.models.content import Media
from application.utils.design import media_file_urls

logger = logging.getLogger(__name__)


def register_content_query_handlers(socketio, app, db):
    """Register the read-only Content handlers (pickers, listings, detail)."""
    from application.socketio_handlers.auth import admin_handler, require_right, current_admin_user

    def _media_entry(m, *, include_filename=False, include_mimetype=False):
        """Build a media picker dict for a Media row."""
        url, preview_url = media_file_urls(m)
        entry = {
            'id': m.id,
            'title': m.title or m.filename,
            'url': url,
            'preview_url': preview_url,
            'tags': [t.strip() for t in (m.tags or '').split(',') if t.strip()],
        }
        if include_filename:
            entry['filename'] = m.filename
        if include_mimetype:
            entry['mimetype'] = m.mime_type or ''
        return entry

    @socketio.on('displayhive:admin:cts:get_media_for_picker')
    @admin_handler
    def handle_get_media_for_picker(data=None):
        """Return a lightweight media list so the content editor can pick an image."""
        all_media = db.session.execute(
            db.select(Media).order_by(Media.created_at.desc())
        ).scalars().all()
        media_list = [_media_entry(m, include_filename=True, include_mimetype=True) for m in all_media]
        socketio.emit('displayhive:admin:stc:media_for_picker', {'media': media_list}, room=request.sid)

    @socketio.on('displayhive:admin:cts:get_image_tags')
    @admin_handler
    def handle_get_image_tags(data=None):
        """Return all unique tags that appear on any image in the media library."""
        all_media = db.session.execute(db.select(Media)).scalars().all()
        tag_set = {t.strip() for m in all_media for t in (m.tags or '').split(',') if t.strip()}
        socketio.emit('displayhive:admin:stc:image_tags', {'tags': sorted(tag_set)}, room=request.sid)

    def _emit_content_list(event, extra, content_items):
        """Serialize content items with preview CSS and emit them under *event*."""
        preview_css = resolve_preview_css(db)
        content_list = [build_content_dict(c, preview_css) for c in content_items]
        socketio.emit(event, {**extra, 'content': content_list}, room=request.sid)
        return content_list

    @socketio.on('displayhive:admin:cts:get_all_content_detailed')
    @require_right('content.page')
    def handle_get_all_content_detailed(data=None):
        """Get full detail for every ContentElement (fields, html preview, screengroups).

        Used by the Content page to group items by Contenttype client-side —
        content is no longer organized by container.
        """
        content_items = db.session.execute(
            db.select(ContentElement)
            .options(joinedload(ContentElement.contenttype), selectinload(ContentElement.screengroups))
            .order_by(ContentElement.title)
        ).scalars().all()

        content_list = _emit_content_list(
            'displayhive:admin:stc:all_content_detailed', {}, content_items)
        logger.debug('Sent %s detailed content items', len(content_list))

    @socketio.on('displayhive:admin:cts:get_content_by_screengroup')
    @require_right('content.page')
    def handle_get_content_by_screengroup(data):
        """Get all content_element assigned to a specific screengroup (by screengroup id)."""
        raw_id = data.get('screengroup_id') if data else None
        if isinstance(raw_id, dict):
            raw_id = raw_id.get('id')
        if raw_id is None:
            return
        screengroup_id = int(raw_id)

        from application.models import Screengroup

        content_items = db.session.execute(
            db.select(ContentElement)
            .join(ContentElement.screengroups)
            .where(Screengroup.id == screengroup_id)
            .options(joinedload(ContentElement.contenttype), selectinload(ContentElement.screengroups))
            .order_by(ContentElement.title)
        ).unique().scalars().all()

        content_list = _emit_content_list(
            'displayhive:admin:stc:content_by_screengroup', {'screengroup_id': screengroup_id}, content_items)
        logger.debug('Sent %s items for screengroup %s', len(content_list), screengroup_id)

    @socketio.on('displayhive:admin:cts:get_content_element_detail')
    @require_right('content.page')
    def handle_get_content_element_detail(data):
        """Get detailed content data for editing, including all custom field values."""
        sid = request.sid
        content_element_id = data.get('content_element_id') if data else None
        if not content_element_id:
            return

        content_element = db.session.get(ContentElement, content_element_id)
        if not content_element:
            logger.debug('ContentElement %s not found', content_element_id)
            return

        # Build content data with all fields
        content_data = {
            'id': content_element.id,
            'title': content_element.title,
            'active': content_element.active,
            'duration': content_element.duration,
            'start_time': fmt_dt(getattr(content_element, 'start_time', None)),
            'end_time': fmt_dt(getattr(content_element, 'end_time', None)),
            'contenttype_id': content_element.contenttype_id,
        }

        # Parse serialized_input JSON (authoritative source for custom fields)
        input_data = {}
        try:
            if getattr(content_element, 'serialized_input', None):
                input_data = json.loads(content_element.serialized_input or '{}')
        except Exception:
            logger.exception('Failed to parse serialized_input for content_element %s', content_element_id)

        # If the contenttype has tagconfigs, prefer values from
        # serialized_input, fallback to model attributes.
        for tagconfig in (getattr(content_element.contenttype, 'tagconfigs', None) or []):
            field_name = getattr(tagconfig, 'field_name', None)
            if not field_name:
                continue
            if field_name in input_data:
                content_data[field_name] = input_data.get(field_name)
            elif hasattr(content_element, field_name):
                content_data[field_name] = getattr(content_element, field_name)

        # Also merge any other keys present in serialized_input that may not be in tagconfigs
        for k, v in input_data.items():
            if k not in content_data:
                content_data[k] = v

        socketio.emit('displayhive:admin:stc:content_element_detail', {'content': content_data}, room=sid)
        logger.debug('Sent detail for content_element %s to %s', content_element_id, sid)

    @socketio.on('displayhive:admin:cts:get_unassigned_content')
    @require_right('content.page')
    def handle_get_unassigned_content(data=None):
        """Get all content that is unassigned (has no screengroups)."""
        all_content = db.session.execute(
            db.select(ContentElement)
            .options(joinedload(ContentElement.contenttype), selectinload(ContentElement.screengroups))
            .order_by(ContentElement.title)
        ).scalars().all()

        unassigned = [ce for ce in all_content if not ce.screengroups]

        content_list = _emit_content_list('displayhive:admin:stc:unassigned_content', {}, unassigned)
        logger.debug('Sent %s unassigned items', len(content_list))

    @socketio.on('displayhive:admin:cts:get_all_content_element')
    @admin_handler
    def handle_get_all_content_element(data=None):
        """Return all ContentElement items.

        Shared by two callers with different rights: the Content page itself
        (content.page) and the screengroup "assign content" modal
        (screengroups.manage_content). Either right is sufficient — this is
        not a mutation, just a listing, so there's no reason to require both.
        """
        from application.permissions import has_right
        user = current_admin_user()
        if not (has_right(db, user, 'content.page') or has_right(db, user, 'screengroups.manage_content')):
            return
        sid = request.sid
        items = db.session.execute(
            db.select(ContentElement).order_by(ContentElement.title)
        ).scalars().all()

        content_list = [
            {
                'id': mc.id,
                'title': mc.title,
                'active': mc.active,
                'duration': mc.duration,
                'contenttypeName': mc.contenttype.name if mc.contenttype else '',
            }
            for mc in items
        ]

        socketio.emit('displayhive:admin:stc:all_content_element', {'content': content_list}, room=sid)
        logger.debug('Sent %s total content_element items to %s', len(content_list), sid)
