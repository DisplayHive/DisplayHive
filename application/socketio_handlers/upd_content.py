"""Helper to assemble and emit `upd_content` snapshots for connected devices.

This module exposes:

  send_upd_content(socketio, db, *, screens=None, screengroups=None, content_ids=None)
    - screens:      list of Screen ORM objects — pushed directly.
    - screengroups: list of Screengroup ORM objects — resolved to their member screens.
    - content_ids:  list of ContentElement ids — each item's screengroups are resolved
                    to their member screens.
    All three sources are merged and de-duplicated by screen id before pushing.

Best-effort; callers must not rely on it raising.

Rendering model: a screen has no independent per-container playlists anymore.
Each ContentElement is a "scene" — when it's showing, every container its
Contenttype's fields (TagConfig) map to switches together; containers not
covered by the current scene fall back to their own `default_content`
(rendered once into `container_defaults`, keyed by container id) if one is
configured, or stay blank otherwise. The payload's `scenes` array is the
screen's full shared rotation queue (ordered, deduplicated); the screen
client (frontends/screen/ts/screen) owns advancing through it by `duration`
and creating/positioning each scene's container divs from the per-scene
`containers` map (vh/vw top/left/width/height).
"""

import json
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def _build_payload(db, screen):
    """Build the upd_content payload dict for a given screen.

    Design resolution: Design is a single, instance-wide active setting (no
    per-screen override) — see get_default_design().

    Returns the payload dict, or None if building fails.
    """
    from application.models import ContentElement, Screengroup
    from application.utils.template import get_default_design, parse_content_html

    design = get_default_design(db)
    design_payload = {
        'name': getattr(design, 'name', '') or '',
        'html': getattr(design, 'html', '') or '',
        'css':  getattr(design, 'css',  '') or '',
    }

    # Load magic tags once; applied to Design HTML/CSS and content-handler CSS below.
    _tvars: dict = {}
    try:
        from application.admin.magictags.helper import load_magic_tags, substitute_magic_tags
        _tvars = load_magic_tags(db)
    except Exception:
        pass

    if _tvars:
        if design_payload['html']:
            design_payload['html'] = substitute_magic_tags(design_payload['html'], _tvars)
        if design_payload['css']:
            design_payload['css'] = substitute_magic_tags(design_payload['css'], _tvars)

    screen_group_ids = set()
    if screen and hasattr(screen, 'screengroups'):
        screen_group_ids = {sg.id for sg in screen.screengroups}

    content_elements = []
    if screen_group_ids:
        content_elements = db.session.execute(
            db.select(ContentElement)
            .where(ContentElement.active == True)
            .where(ContentElement.screengroups.any(Screengroup.id.in_(list(screen_group_ids))))
            .distinct()
            .order_by(ContentElement.id)
        ).unique().scalars().all()

    # Each ContentElement is one "scene": every container its Contenttype's
    # fields (TagConfig) target must switch together when this scene is showing.
    scenes = []
    all_container_ids: set = set()
    for mc in content_elements:
        tagconfigs = getattr(mc.contenttype, 'tagconfigs', None) or []
        rendered_by_container = parse_content_html(mc.html, tagconfigs)

        scene_containers = {}
        for tc in tagconfigs:
            container = tc.contentcontainer
            if container is None:
                continue
            scene_containers[str(container.id)] = {
                'name': container.name,
                'top': container.top, 'left': container.left,
                'width': container.width, 'height': container.height,
                'html': rendered_by_container.get(str(tc.contentcontainer_id), ''),
            }

        if not scene_containers:
            # Nothing to show for this scene (no fields targeting a real
            # container) — skip it rather than occupy a rotation slot with
            # a blank scene.
            continue

        all_container_ids.update(int(cid) for cid in scene_containers)

        scene: dict = {
            'id': mc.id,
            'title': mc.title,
            'duration': mc.duration,
            'containers': scene_containers,
        }
        if mc.start_time is not None:
            scene['start_time'] = mc.start_time.isoformat()
        if mc.end_time is not None:
            scene['end_time'] = mc.end_time.isoformat()
        try:
            si = json.loads(mc.serialized_input or '{}')
            if any(v == 'random_tags' for k, v in si.items() if k.endswith('__image_mode')):
                scene['update_after_show'] = True
            elif any(
                getattr(tc, 'field_handler', '') == 'pretalx_table'
                for tc in (getattr(mc.contenttype, 'tagconfigs', None) or [])
            ):
                scene['update_after_show'] = True
        except Exception:
            pass

        scenes.append(scene)

    # Fallback content for containers that show up in this screen's rotation
    # but aren't targeted by whichever scene is currently active — rendered
    # once here (not per-scene) since a container's default doesn't change
    # from scene to scene.
    container_defaults = {}
    if all_container_ids:
        from application.admin.content.helper import render_container_default
        from application.models import ContentContainer

        for container in db.session.execute(
            db.select(ContentContainer).where(ContentContainer.id.in_(all_container_ids))
        ).scalars().all():
            html = render_container_default(container, db=db)
            if not html:
                continue
            container_defaults[str(container.id)] = {
                'name': container.name,
                'top': container.top, 'left': container.left,
                'width': container.width, 'height': container.height,
                'html': html,
            }

    from datetime import datetime as _dt, timezone as _tz
    return {
        'design':             design_payload,
        'scenes':             scenes,
        'container_defaults': container_defaults,
        'server_time':        _dt.now(_tz.utc).isoformat(),
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
