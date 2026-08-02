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
Each ContentElement is a "scene" — when it's showing, every container in its
Contenttype's own Layout switches together: containers with a field (TagConfig)
targeting them show that field's rendered value, and any other container in
that same Layout falls back to its own `default_content` if one is configured,
or stays blank otherwise. A container that isn't part of the current scene's
Layout at all is never shown, even if it has a default and even if some other
scene in the rotation does use it — defaults are baked directly into each
scene's own `containers` map (not sent globally) precisely so that switching
away from a scene can't leave a container from a *different* Layout showing
through. The payload's `scenes` array is the screen's full shared rotation
queue (ordered, deduplicated); the screen client (frontends/screen/ts/screen)
owns advancing through it by `duration` and creating/positioning each scene's
container divs from the per-scene `containers` map (vh/vw top/left/width/height).
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

    # CSS precedence, low to high (all layers are equal-specificity single-
    # class/element selectors, so source order breaks the tie): per-container
    # overrides, then global overrides, then the Backdrop (gradients/image/
    # color), then the Design's own hand-written CSS last — so a plain CSS
    # edit always wins, a global default beats a per-container tweak, and an
    # unset property just falls through to whatever's beneath it.
    css_layers = []
    if design is not None:
        from application.admin.designs.helper import render_container_style_css, render_global_style_css, render_backdrop_css
        container_style_css = render_container_style_css(db, design)
        if container_style_css:
            css_layers.append(container_style_css)
        global_style_css = render_global_style_css(db, design)
        if global_style_css:
            css_layers.append(global_style_css)
        backdrop_css = render_backdrop_css(db, design)
        if backdrop_css:
            css_layers.append(backdrop_css)
    base_css = getattr(design, 'css', '') or ''
    if base_css:
        css_layers.append(base_css)
    css = '\n\n'.join(css_layers)

    design_payload = {
        'name': getattr(design, 'name', '') or '',
        'html': getattr(design, 'html', '') or '',
        'css':  css,
    }

    # Animated canvas background effect: not representable as CSS (see
    # Design.background_effect comment), so it's handed to the screen client
    # as data — effect key + its opaque settings object — rather than baked
    # into `css` above. Malformed settings JSON degrades to an empty object
    # rather than breaking the whole upd_content push.
    effect_key = (getattr(design, 'background_effect', '') or '').strip()
    if effect_key:
        effect_settings = {}
        raw_settings = getattr(design, 'background_effect_settings', '') or ''
        if raw_settings:
            try:
                effect_settings = json.loads(raw_settings)
            except Exception:
                effect_settings = {}
        if effect_settings:
            from application.admin.designs.helper import resolve_default_colors_deep
            effect_settings = resolve_default_colors_deep(effect_settings, design)
        design_payload['background_effect'] = {
            'name': effect_key,
            'settings': effect_settings,
        }
    else:
        design_payload['background_effect'] = None

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

    # Each ContentElement is one "scene": every container in its Contenttype's
    # own Layout switches together when this scene is showing — never a
    # container from some other Layout, even if another scene in the
    # rotation happens to use it.
    from application.admin.content.helper import render_container_default

    scenes = []
    for mc in content_elements:
        tagconfigs = getattr(mc.contenttype, 'tagconfigs', None) or []
        rendered_by_container = parse_content_html(mc.html, tagconfigs)

        # A TagConfig's contentcontainer_id can go stale if a container is
        # later removed from the Contenttype's Layout elsewhere (editing a
        # Layout doesn't touch any Contenttype's TagConfig rows) — without
        # this check, that container would keep rendering this scene's old
        # content forever even though it's no longer part of the Layout.
        layout_containers = list(getattr(mc.contenttype.layout, 'contentcontainers', None) or []) if mc.contenttype.layout else []
        layout_container_ids = {c.id for c in layout_containers}

        scene_containers = {}
        for tc in tagconfigs:
            container = tc.contentcontainer
            if container is None or container.id not in layout_container_ids:
                continue
            scene_containers[str(container.id)] = {
                'name': container.name,
                'top': container.top, 'left': container.left,
                'width': container.width, 'height': container.height,
                'html': rendered_by_container.get(str(tc.contentcontainer_id), ''),
            }

        # Any container that's part of this scene's own Layout but has no
        # field targeting it at all (no TagConfig, as opposed to an empty
        # field value — render_content_fields() already handles that case)
        # falls back to its own default_content, scoped to this scene only.
        for container in layout_containers:
            if str(container.id) in scene_containers:
                continue
            html = render_container_default(container, db=db)
            if not html:
                continue
            scene_containers[str(container.id)] = {
                'name': container.name,
                'top': container.top, 'left': container.left,
                'width': container.width, 'height': container.height,
                'html': html,
            }

        if not scene_containers:
            # Nothing to show for this scene (no fields targeting a real
            # container) — skip it rather than occupy a rotation slot with
            # a blank scene.
            continue

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

    from datetime import datetime as _dt, timezone as _tz
    return {
        'design':      design_payload,
        'scenes':      scenes,
        'server_time': _dt.now(_tz.utc).isoformat(),
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
