"""Read-only admin socket handlers for Content — media pickers, container and
content listings. Split out of the former monolithic ``sockethandlers`` module.
"""

import json
import logging

from flask import request

from application.utils.template import get_default_template, media_file_urls
from application.admin.content.serializers import (
    build_containers_for_template,
    resolve_preview_css,
    build_content_dict,
    fmt_dt,
)
from application.models import ContentElement, ContentContainer, Contenttype, Template
from application.models.content import Media

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

    @socketio.on('displayhive:admin:cts:get_images_by_tags')
    @admin_handler
    def handle_get_images_by_tags(data=None):
        """Return image URLs (and metadata) for media items that match any of the provided tags."""
        sid = request.sid
        tags = (data or {}).get('tags', [])
        if not tags:
            socketio.emit('displayhive:admin:stc:images_by_tags', {'images': [], 'tags': tags}, room=sid)
            return
        all_media = db.session.execute(db.select(Media)).scalars().all()
        matched = []
        for m in all_media:
            media_tags = {t.strip() for t in (m.tags or '').split(',') if t.strip()}
            if any(t in media_tags for t in tags):
                matched.append(_media_entry(m))
        socketio.emit('displayhive:admin:stc:images_by_tags', {'images': matched, 'tags': tags}, room=sid)

    @socketio.on('displayhive:admin:cts:get_containers')
    @require_right('content.page')
    def handle_get_containers(data=None):
        """Get all content containers from the default template."""
        sid = request.sid
        template = get_default_template(db)
        containers = build_containers_for_template(db, template)
        socketio.emit('displayhive:admin:stc:containers', {'containers': containers}, room=sid)
        logger.debug('Sent %s containers to %s', len(containers), sid)

    @socketio.on('displayhive:admin:cts:get_containers_for_screen')
    @require_right('content.page')
    def handle_get_containers_for_screen(data=None):
        """Return content containers for a specific screen, using its assigned template.

        Falls back to the system default template if the screen has no template assigned.
        """
        sid = request.sid
        screen_id = (data or {}).get('screen_id')
        if not screen_id:
            return

        from application.models import Screen
        screen = db.session.get(Screen, int(screen_id))
        if not screen:
            return

        # Resolve template: screen-specific → isDefault → first
        template = None
        if screen.template_id:
            template = db.session.get(Template, screen.template_id)
        if not template:
            template = (
                db.session.execute(db.select(Template).where(Template.isDefault == True)).scalar_one_or_none()
                or db.session.execute(db.select(Template)).scalars().first()
            )

        containers = build_containers_for_template(db, template)
        socketio.emit('displayhive:admin:stc:containers_for_screen', {'containers': containers}, room=sid)
        logger.debug('Sent %s containers for screen %s (template: %s) to %s',
                     len(containers), screen_id, getattr(template, 'name', 'none'), sid)

    @socketio.on('displayhive:admin:cts:get_all_containers_for_picker')
    @admin_handler
    def handle_get_all_containers_for_picker(data=None):
        """Return containers from every template, each with template_name, for the contenttype editor."""
        sid = request.sid
        all_templates = db.session.execute(
            db.select(Template).order_by(Template.isDefault.desc(), Template.name)
        ).scalars().all()
        containers = []
        for tpl in all_templates:
            for cc in (tpl.contentcontainers or []):
                containers.append({
                    'id': getattr(cc, 'id', None),
                    'name': cc.name,
                    'title': cc.title or cc.name,
                    'order': cc.order,
                    'template_name': tpl.name,
                    'template_id': tpl.id,
                })
        containers.sort(key=lambda x: (x.get('template_name') or '', x.get('order') or 0))
        socketio.emit('displayhive:admin:stc:all_containers_for_picker', {'containers': containers}, room=sid)
        logger.debug('Sent %s all_containers_for_picker to %s', len(containers), sid)

    @socketio.on('displayhive:admin:cts:get_template_containers')
    @admin_handler
    def handle_get_template_containers(data=None):
        """Get content containers for a specific template by id."""
        sid = request.sid
        template_id = None
        if data and isinstance(data, dict):
            template_id = data.get('id') or data.get('template_id')
        if not template_id:
            return

        tpl = None
        try:
            tpl = db.session.get(Template, int(template_id))
        except (ValueError, TypeError):
            tpl = None

        containers = []
        if tpl and tpl.contentcontainers:
            for cc in tpl.contentcontainers:
                count = db.session.execute(
                    db.select(db.func.count()).select_from(ContentElement).where(
                        ContentElement.contentcontainer == cc.name
                    )
                ).scalar()
                containers.append({
                    'id': getattr(cc, 'id', None),
                    'name': cc.name,
                    'title': cc.title or cc.name,
                    'order': cc.order,
                    'contentCount': count,
                    'template_name': tpl.name,
                })

        containers.sort(key=lambda x: x['order'])

        socketio.emit('displayhive:admin:stc:template_containers', {'containers': containers, 'template_id': template_id}, room=sid)
        # legacy name
        socketio.emit('template_containers', {'containers': containers, 'template_id': template_id}, room=sid)
        logger.debug('Sent %s template_containers for template %s to %s', len(containers), template_id, sid)

    def _emit_content_list(event, extra, content_items):
        """Serialize content items with preview CSS and emit them under *event*."""
        preview_css = resolve_preview_css(db)
        content_list = [build_content_dict(c, preview_css) for c in content_items]
        socketio.emit(event, {**extra, 'content': content_list}, room=request.sid)
        return content_list

    @socketio.on('displayhive:admin:cts:get_content_by_container')
    @require_right('content.page')
    def handle_get_content_by_container(data):
        """Get all content_element for a specific container."""
        container_name = data.get('container') if data else None
        if not container_name:
            return

        content_items = db.session.execute(
            db.select(ContentElement)
            .where(ContentElement.contentcontainer == container_name)
            .order_by(ContentElement.title)
        ).scalars().all()

        content_list = _emit_content_list(
            'displayhive:admin:stc:content_list', {'container': container_name}, content_items)
        logger.debug('Sent %s items for container %s', len(content_list), container_name)

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
            .order_by(ContentElement.title)
        ).unique().scalars().all()

        content_list = _emit_content_list(
            'displayhive:admin:stc:content_by_screengroup', {'screengroup_id': screengroup_id}, content_items)
        logger.debug('Sent %s items for screengroup %s', len(content_list), screengroup_id)

    @socketio.on('displayhive:admin:cts:get_content_by_screengroup_and_container')
    @require_right('content.page')
    def handle_get_content_by_screengroup_and_container(data):
        """Get content_element for a specific screengroup filtered by container name."""
        raw_id = data.get('screengroup_id') if data else None
        if isinstance(raw_id, dict):
            raw_id = raw_id.get('id')
        container_name = data.get('container') if data else None
        if raw_id is None or not container_name:
            return
        screengroup_id = int(raw_id)

        from application.models import Screengroup

        content_items = db.session.execute(
            db.select(ContentElement)
            .join(ContentElement.screengroups)
            .where(ContentElement.contentcontainer == container_name)
            .where(Screengroup.id == screengroup_id)
            .order_by(ContentElement.title)
        ).unique().scalars().all()

        content_list = _emit_content_list(
            'displayhive:admin:stc:content_by_screengroup_and_container',
            {'screengroup_id': screengroup_id, 'container': container_name}, content_items)
        logger.debug('Sent %s items for sg=%s container=%s', len(content_list), screengroup_id, container_name)

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
            'contentcontainer': content_element.contentcontainer,
            'contenttype_id': content_element.contenttype_id,
        }

        # Parse serialized_input JSON (authoritative source for custom fields)
        input_data = {}
        try:
            if getattr(content_element, 'serialized_input', None):
                input_data = json.loads(content_element.serialized_input or '{}')
        except Exception:
            logger.exception('Failed to parse serialized_input for content_element %s', content_element_id)

        # If tagconfigs exist, prefer values from serialized_input, fallback to model attributes
        if content_element.contenttype and hasattr(content_element.contenttype, 'tagconfigs'):
            for tagconfig in (content_element.contenttype.tagconfigs or []):
                field_name = getattr(tagconfig, 'field_name', None) or getattr(tagconfig, 'name', None)
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
        """Get all content that is unassigned.

        A content item counts as unassigned if:
          - its contentcontainer is empty or null, or
          - its contentcontainer name does not exist in any of the templates
            used by the screens it is actually assigned to (via its
            screengroups). Content with no screengroups, or whose
            screengroups have no screens in them, has no templates to match
            against and is therefore also unassigned.
        """
        default_template = get_default_template(db)

        def _template_for_screen(screen):
            return screen.template if screen.template_id else default_template

        all_content = db.session.execute(
            db.select(ContentElement).order_by(ContentElement.title)
        ).scalars().all()

        unassigned = []
        for ce in all_content:
            if not ce.contentcontainer:
                unassigned.append(ce)
                continue

            assigned_screens = {
                screen
                for sg in (ce.screengroups or [])
                for screen in (sg.screens or [])
            }

            container_names = set()
            for screen in assigned_screens:
                tpl = _template_for_screen(screen)
                if tpl:
                    container_names.update(cc.name for cc in (tpl.contentcontainers or []))

            if ce.contentcontainer not in container_names:
                unassigned.append(ce)

        content_list = _emit_content_list('displayhive:admin:stc:unassigned_content', {}, unassigned)
        logger.debug('Sent %s unassigned items', len(content_list))

    @socketio.on('displayhive:admin:cts:get_all_content_element')
    @admin_handler
    def handle_get_all_content_element(data=None):
        """Return all ContentElement items regardless of container.

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
                'contentcontainer': mc.contentcontainer or '',
                'contenttypeName': mc.contenttype.name if mc.contenttype else '',
            }
            for mc in items
        ]

        socketio.emit('displayhive:admin:stc:all_content_element', {'content': content_list}, room=sid)
        logger.debug('Sent %s total content_element items to %s', len(content_list), sid)
