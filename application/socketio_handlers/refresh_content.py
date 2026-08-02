"""Socket.IO handler for per-item content refresh requests from screen devices.

Screen devices emit `displayhive:screen:cts:refresh_content` with ``{'id': <int>}``
after displaying a scene that has ``update_after_show`` set.  The handler
re-renders every one of the ContentElement's Contenttype's fields (TagConfig)
(picking a new random image if applicable), updates ``ContentElement.html``
(a JSON map of ``{contentcontainer_id: rendered_html}``) in the database, and
emits ``displayhive:screen:stc:content_updated`` with
``{'id': <int>, 'containers': {contentcontainer_id: html}}`` back to the
requesting socket only.  On any failure the handler emits nothing so the
client silently keeps its existing rendered HTML.
"""

import json
import time
import logging

from flask import request

logger = logging.getLogger(__name__)

# Tracks the last re-render timestamp per ContentElement id to throttle
# screen-triggered refreshes to at most once per minute.
_last_render: dict[int, float] = {}

_REFRESH_THROTTLE_SECONDS = 60


def register_refresh_content_handlers(socketio, app, db):
    """Register the refresh_content socket handler for screen devices."""

    @socketio.on('displayhive:screen:cts:get_server_time')
    def handle_get_server_time(data=None):
        """Return the current UTC server time so screen players can re-calibrate their clock offset."""
        from datetime import datetime, timezone
        sid = request.sid
        socketio.emit(
            'displayhive:screen:stc:server_time',
            {'server_time': datetime.now(timezone.utc).isoformat()},
            room=sid,
        )

    @socketio.on('displayhive:screen:cts:refresh_content')
    def handle_refresh_content(data):
        """Re-render a content item and push the updated HTML back to the requesting screen.

        Called by screen devices after displaying an item with `update_after_show` set.
        Re-renders `ContentElement.html` from the stored `serialized_input` (picking a
        fresh random image if applicable), persists the result, and emits
        `displayhive:screen:stc:content_updated` back to the requesting socket.
        On any failure, nothing is emitted so the client keeps its cached HTML.
        """
        def _log(msg):
            logger.debug('%s', msg)
        _log('handle_refresh_content called')
        sid = request.sid
        if not data or not isinstance(data, dict):
            return
        content_id = data.get('id')
        if not content_id:
            return
        try:
            content_id = int(content_id)
        except (TypeError, ValueError):
            return

        # Authorize the caller: it must be a connected screen device, and it may
        # only refresh content that belongs to its own screen. Without this any
        # connected socket could force re-renders of — and read back the HTML of
        # — arbitrary content items by id, across screens.
        devicekey = None
        try:
            from application.socketio_handlers.lifecycle import connected_devices
            for k, v in list(connected_devices.items()):
                if v.get('sid') == sid:
                    devicekey = k
                    break
        except Exception:
            logger.debug('Failed to resolve devicekey for sid=%s from connected_devices', sid, exc_info=True)
        if not devicekey and getattr(request, 'args', None):
            # Impersonation sessions aren't tracked in connected_devices but do
            # carry their devicekey in the handshake args.
            try:
                devicekey = request.args.get('devicekey')
            except Exception:
                devicekey = None
        if not devicekey:
            _log('refused: caller is not a recognised device')
            return

        try:
            from application.models import ContentElement, Device, Screen
            from application.admin.content.helper import render_content_fields
            from application.utils.design import parse_content_html

            dev = db.session.execute(
                db.select(Device).where(Device.devicekey == devicekey)
            ).scalar_one_or_none()
            if not dev or not getattr(dev, 'is_active', True) or not getattr(dev, 'screen_id', None):
                _log('refused: device missing, inactive, or unassigned')
                return

            mc = db.session.get(ContentElement, content_id)
            if not mc:
                _log(f'ContentElement {content_id} not found')
                return

            # Scope: the item must share a screengroup with the device's screen —
            # i.e. it is genuinely part of what this screen plays.
            screen = db.session.get(Screen, dev.screen_id)
            screen_group_ids = {sg.id for sg in getattr(screen, 'screengroups', [])} if screen else set()
            content_group_ids = {sg.id for sg in getattr(mc, 'screengroups', [])}
            if not (screen_group_ids & content_group_ids):
                _log(f'refused: content {content_id} is not assigned to this device\'s screen')
                return

            # Throttle: if rendered less than 60 s ago, return cached HTML without
            # hitting external APIs. The admin manual-save path bypasses this entirely
            # since it calls render_content_fields directly, not this handler.
            elapsed = time.time() - _last_render.get(content_id, 0)
            if elapsed < _REFRESH_THROTTLE_SECONDS:
                _log(f'Throttled refresh for {content_id} ({elapsed:.0f}s < {_REFRESH_THROTTLE_SECONDS}s), returning cached HTML')
                if mc.html:
                    tagconfigs = getattr(mc.contenttype, 'tagconfigs', None) or []
                    cached = parse_content_html(mc.html, tagconfigs)
                    socketio.emit(
                        'displayhive:screen:stc:content_updated',
                        {'id': content_id, 'containers': cached},
                        room=sid,
                    )
                return

            tagconfigs = getattr(mc.contenttype, 'tagconfigs', None) or []
            rendered_by_container = render_content_fields(tagconfigs, mc.serialized_input or '{}', db=db)

            mc.html = json.dumps(rendered_by_container, ensure_ascii=False)
            db.session.add(mc)
            db.session.commit()

            _last_render[content_id] = time.time()
            _log(f'Re-rendered ContentElement {content_id}, emitting update to {sid}')
            socketio.emit(
                'displayhive:screen:stc:content_updated',
                {'id': content_id, 'containers': rendered_by_container},
                room=sid,
            )
        except Exception:
            db.session.rollback()
            logger.exception('Error refreshing content %s', content_id)
