"""Socket.IO handlers for content-related events."""

import logging

from flask import request

logger = logging.getLogger(__name__)


def register_content_handlers(socketio, app, db):
    """Register all content-related socket.io event handlers."""
    
    from application.models import Screen, Screengroup, ContentElement
    from application.utils import parse_content_html

    # Old endpoints `request_content_list` and `request_content_html` removed.
    # Devices should use the unified `device_request` event below.

    @socketio.event
    def device_request(message):
        """Unified device request.

        message should contain a `type` field with one of:
          - 'screenconfig' : expects 'name' -> replies with 'debug_mode' (+ logger status)
          - 'playlist'     : expects 'name' and optional 'container' -> replies with 'content_list_response'
          - 'contentelement': expects 'ids' (or 'id') and optional 'container' -> replies with 'content_html_response'

        Replies are emitted to the requesting socket via room=request.sid to preserve compatibility
        with existing client handlers.
        """
        try:
            if not message or not isinstance(message, dict):
                return

            req_type = (message.get('type') or '').lower()

            # Log only the request type, not the full payload.
            logger.debug("device_request received from sid=%s type=%s", getattr(request, 'sid', 'unknown'), req_type)

            # CONTENT ELEMENT(S): return HTML for ids
            if req_type == 'contentelement':
                ids = []
                if message.get('ids'):
                    ids = message.get('ids')
                elif message.get('id'):
                    ids = [message.get('id')]

                container = message.get('container', 'maincontent')
                if not ids:
                    return

                content_elements = db.session.execute(
                    db.select(ContentElement).where(ContentElement.id.in_(ids))
                ).scalars().all()

                # ContentElement.html is a JSON map of {contentcontainer_id: rendered_html},
                # one entry per field (TagConfig) on its Contenttype. Pick out the
                # fragment for the field whose container matches by name.
                html_data = {}
                for content in content_elements:
                    tagconfigs = getattr(content.contenttype, 'tagconfigs', None) or []
                    rendered_by_container = parse_content_html(content.html, tagconfigs)
                    html_data[content.id] = ''
                    for tc in tagconfigs:
                        cc = tc.contentcontainer
                        if cc is not None and cc.name == container:
                            html_data[content.id] = rendered_by_container.get(str(tc.contentcontainer_id), '')
                            break

                socketio.emit('content_html_response', {
                    'data': html_data,
                    'container': container
                }, room=request.sid)
                return

            # PLAYLIST: return id+duration list for a screen and container
            if req_type == 'playlist':
                screen_name = message.get('name', '')
                container = message.get('container', 'maincontent')
                if not screen_name:
                    return

                # Prefer most recently seen screen with that name
                screen = db.session.execute(
                    db.select(Screen).where(Screen.name == screen_name).order_by(Screen.lastseen.desc())
                ).scalars().first()

                if not screen:
                    socketio.emit('playlist_response', {'container': container, 'data': []}, room=request.sid)
                    return

                screen_group_ids = {sg.id for sg in screen.screengroups}
                if screen_group_ids:
                    candidates = db.session.execute(
                        db.select(ContentElement)
                        .join(ContentElement.screengroups)
                        .where(Screengroup.id.in_(screen_group_ids))
                        .where(ContentElement.active == True)
                        .distinct()
                    ).scalars().all()
                    # A ContentElement has no direct container reference — it's
                    # eligible for *container* if one of its Contenttype's
                    # fields (TagConfig) targets a container with that name.
                    content_elements = [
                        c for c in candidates
                        if any(
                            tc.contentcontainer is not None and tc.contentcontainer.name == container
                            for tc in (getattr(c.contenttype, 'tagconfigs', None) or [])
                        )
                    ]
                else:
                    content_elements = []

                content_list = []
                for c in content_elements:
                    entry: dict = {'id': c.id, 'duration': c.duration}
                    if c.start_time is not None:
                        entry['start_time'] = c.start_time.isoformat()
                    if c.end_time is not None:
                        entry['end_time'] = c.end_time.isoformat()
                    content_list.append(entry)
                socketio.emit('playlist_response', {'container': container, 'data': content_list}, room=request.sid)
                return

            # SCREEN CONFIG: return debug mode + logger status
            if req_type == 'screenconfig':
                screen_name = message.get('name', '')
                # If no name provided, send defaults
                if not screen_name:
                    socketio.emit('debug_mode', {'debug': False}, room=request.sid)
                    logger_active = False
                    try:
                        from .logger import get_logger_status
                        logger_active = get_logger_status()
                    except Exception:
                        pass
                    if logger_active:
                        socketio.emit('logger_active', {}, room=request.sid)
                    else:
                        socketio.emit('logger_inactive', {}, room=request.sid)
                    return

                screen = db.session.execute(
                    db.select(Screen).where(Screen.name == screen_name).order_by(Screen.lastseen.desc())
                ).scalars().first()

                if screen:
                    debug_state = screen.debug if screen.debug is not None else False
                    socketio.emit('debug_mode', {'debug': debug_state}, room=request.sid)
                else:
                    socketio.emit('debug_mode', {'debug': False}, room=request.sid)

                logger_active = False
                try:
                    from .logger import get_logger_status
                    logger_active = get_logger_status()
                except Exception:
                    pass
                if logger_active:
                    socketio.emit('logger_active', {}, room=request.sid)
                else:
                    socketio.emit('logger_inactive', {}, room=request.sid)
                return

        except Exception:
            logger.exception("Error in device_request")
