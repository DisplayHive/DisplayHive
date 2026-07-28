"""Helper to assemble and emit `upd_content` snapshots for connected devices.

This module exposes:

  send_upd_content(socketio, db, *, screens=None, screengroups=None, content_ids=None)
    - screens:      list of Screen ORM objects — pushed directly.
    - screengroups: list of Screengroup ORM objects — resolved to their member screens.
    - content_ids:  list of ContentElement ids — each item's screengroups are resolved
                    to their member screens.
    All three sources are merged and de-duplicated by screen id before pushing.

Best-effort; callers must not rely on it raising.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def _build_payload(db, screen):
    """Build the upd_content payload dict for a given screen.

    Template resolution order:
      1. Screen-specific template (screen.template_id is set)
      2. System default template via get_default_template()

    Returns the payload dict, or None if building fails.
    """
    from application.models import Template, ContentContainer, ContentElement, Screengroup
    from application.utils.template import get_default_template

    # 1. Screen-specific template, then system default fallback
    template = None
    if screen and getattr(screen, 'template_id', None):
        template = db.session.get(Template, screen.template_id)
    if not template:
        template = get_default_template(db)

    template_payload = {
        'name': getattr(template, 'name', '') or '',
        'html': getattr(template, 'html', '') or '',
        'css':  getattr(template, 'css',  '') or ''
    }

    # Load magic tags once; applied to HTML, template CSS, and contenttype CSS below.
    _tvars: dict = {}
    try:
        from application.admin.magictags.helper import load_magic_tags, substitute_magic_tags
        _tvars = load_magic_tags(db)
    except Exception:
        pass

    # Replace {{ tag_name }} placeholders with <div data-container="tag_name"></div>
    # so the client receives ready-to-inject HTML (same substitution done in app.py for page load).
    import re as _re
    raw_html = template_payload['html']
    if raw_html:
        # Substitute {{ var_<name> }} before converting container tags so var_ tags
        # are not turned into data-container divs.
        if _tvars:
            raw_html = substitute_magic_tags(raw_html, _tvars)
        template_payload['html'] = _re.sub(
            r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}',
            r'<div data-container="\1"></div>',
            raw_html,
        )
    else:
        template_payload['html'] = '<div data-container="maincontent"></div>'

    # Substitute magic tags in template CSS.
    if _tvars and template_payload['css']:
        template_payload['css'] = substitute_magic_tags(template_payload['css'], _tvars)

    containers = []
    if template:
        contentcontainers = db.session.execute(
            db.select(ContentContainer)
            .where(ContentContainer.template_id == template.id)
        ).scalars().all()
        containers = [c.name for c in contentcontainers]
    if not containers:
        containers = ['maincontent']

    screen_group_ids = set()
    if screen and hasattr(screen, 'screengroups'):
        screen_group_ids = {sg.id for sg in screen.screengroups}

    playlists = []
    all_ids: set = set()
    for container in containers:
        if screen_group_ids:
            content_elements = db.session.execute(
                db.select(ContentElement)
                .where(ContentElement.active == True)
                .where(
                    (ContentElement.contentcontainer == container)
                    | ((ContentElement.contentcontainer == None) & (container == 'maincontent'))
                )
                .where(ContentElement.screengroups.any(Screengroup.id.in_(list(screen_group_ids))))
                .distinct()
            ).scalars().all()
        else:
            content_elements = []

        content_list = []
        for mc in content_elements:
            entry: dict = {'id': mc.id, 'title': mc.title, 'duration': mc.duration}
            # Transmit scheduling window so the screen can skip items that
            # have not started yet or have already ended.
            if mc.start_time is not None:
                entry['start_time'] = mc.start_time.isoformat()
            if mc.end_time is not None:
                entry['end_time'] = mc.end_time.isoformat()
            # Flag items that use random_tags or pretalx_table so the client
            # requests a re-render after each display, keeping content fresh.
            try:
                import json as _json
                si = _json.loads(mc.serialized_input or '{}')
                if any(v == 'random_tags' for k, v in si.items() if k.endswith('__image_mode')):
                    entry['update_after_show'] = True
                elif any(
                    getattr(tc, 'field_handler', '') == 'pretalx_table'
                    for tc in getattr(getattr(mc, 'contenttype', None), 'tagconfigs', [])
                ):
                    entry['update_after_show'] = True
            except Exception:
                pass
            content_list.append(entry)
            all_ids.add(mc.id)
        playlists.append({'container': container, 'data': content_list})

    content_html = {}
    content_css = {}
    if all_ids:
        for mc in db.session.execute(
            db.select(ContentElement).where(ContentElement.id.in_(list(all_ids)))
        ).scalars().all():
            content_html[mc.id] = mc.html
            ct_css = getattr(getattr(mc, 'contenttype', None), 'css', None)
            if ct_css:
                if _tvars:
                    ct_css = substitute_magic_tags(ct_css, _tvars)
                content_css[mc.id] = ct_css

    from datetime import datetime as _dt, timezone as _tz
    return {
        'template':     template_payload,
        'containers':   containers,
        'playlists':    playlists,
        'content_html': content_html,
        'content_css':  content_css,
        'server_time':  _dt.now(_tz.utc).isoformat(),
    }


def _emit_to_screen(socketio, db, screen):
    """Resolve device rooms for *screen* and emit a personalised payload."""
    try:
        from application.models import Device
        payload = _build_payload(db, screen)
        if payload is None:
            return
        devices = db.session.execute(
            db.select(Device).where(Device.screen_id == screen.id)
        ).scalars().all()
        sent = False
        for dev in devices:
            dk = getattr(dev, 'devicekey', None)
            if dk:
                socketio.emit('upd_content', payload, room=f'device_{dk}')
                logger.debug("[send_upd_content] Sent to '%s' via 'device_%s'", screen.name, dk)
                sent = True
        if not sent:
            logger.debug("[send_upd_content] No devices found for screen '%s', skipping", screen.name)
    except Exception:
        logger.exception("[send_upd_content] Error emitting to screen '%s'", getattr(screen, 'name', '?'))


def send_upd_content(
    socketio,
    db,
    *,
    screens: Optional[List] = None,
    screengroups: Optional[List] = None,
    content_ids: Optional[List[int]] = None,
):
    """Emit personalised upd_content payloads to one or more screens.

    Parameters
    ----------
    screens:
        Explicit list of Screen ORM objects to push to.
    screengroups:
        List of Screengroup ORM objects whose member screens receive updates.
    content_ids:
        List of ContentElement ids.  Each item's screengroups are resolved to
        their member screens, which are merged into the target set.

    All three sources are merged and de-duplicated by screen id.  If all are
    omitted the function is a no-op.
    """
    try:
        from application.models import ContentElement as _ContentElement
        from sqlalchemy.orm import joinedload as _joinedload

        seen_ids: set = set()
        target_screens = []

        def _add_screen(s):
            """Add *s* to target_screens if it hasn't been added yet (deduplication by id)."""
            if s is not None and s.id not in seen_ids:
                seen_ids.add(s.id)
                target_screens.append(s)

        for s in (screens or []):
            _add_screen(s)

        for sg in (screengroups or []):
            for s in getattr(sg, 'screens', []):
                _add_screen(s)

        if content_ids:
            from application.models import Screengroup as _Screengroup
            items = db.session.execute(
                db.select(_ContentElement)
                .options(_joinedload(_ContentElement.screengroups).joinedload(_Screengroup.screens))
                .where(_ContentElement.id.in_(list(content_ids)))
            ).unique().scalars().all()
            for item in items:
                for sg in getattr(item, 'screengroups', []):
                    for s in getattr(sg, 'screens', []):
                        _add_screen(s)

        for screen in target_screens:
            _emit_to_screen(socketio, db, screen)

    except Exception:
        logger.exception("[send_upd_content] Unexpected error")
