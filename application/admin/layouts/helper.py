"""Helpers for admin Layouts page (server-side).

Provides helpers to emit the layouts and containers list payloads to admin clients.
"""

import logging
from typing import Optional

from application.aspect_ratio import BASE_RATIO, best_ratio
from application.models import Layout, ContentContainer, TagConfig

logger = logging.getLogger(__name__)


def container_geometry(container, ratio: str = BASE_RATIO) -> dict:
    """The container's {top, left, width, height} at *ratio*: its dedicated
    ContainerPosition if one exists, else its base (16:9) columns."""
    if ratio != BASE_RATIO:
        for p in (container.positions or []):
            if p.aspect_ratio == ratio:
                return {'top': p.top, 'left': p.left, 'width': p.width, 'height': p.height}
    return {'top': container.top, 'left': container.left, 'width': container.width, 'height': container.height}


def layout_ratios(layout) -> list:
    """Every aspect ratio *layout* has a variant for: the base first."""
    return [BASE_RATIO] + [v.aspect_ratio for v in (layout.variations or []) if v.aspect_ratio != BASE_RATIO]


def containers_for_ratio(layout, ratio: str = BASE_RATIO) -> list:
    """The member containers of *layout*'s variant at exactly *ratio*."""
    if ratio == BASE_RATIO:
        return list(layout.contentcontainers or [])
    for v in (layout.variations or []):
        if v.aspect_ratio == ratio:
            return list(v.contentcontainers or [])
    return []


def resolve_layout_ratio(layout, target) -> str:
    """The layout variant ratio that best matches *target* (a screen's ratio)."""
    return best_ratio(target, layout_ratios(layout))


def all_member_container_ids(layout) -> set:
    """Container ids that belong to *layout* in any variant."""
    ids = {c.id for c in (layout.contentcontainers or [])}
    for v in (layout.variations or []):
        ids.update(c.id for c in (v.contentcontainers or []))
    return ids


def _serialize_container(c, used_container_ids: set) -> dict:
    return {
        'id': c.id,
        'name': c.name,
        'order': c.order,
        'top': c.top,
        'left': c.left,
        'width': c.width,
        'height': c.height,
        'locked': c.locked,
        'show_when_empty': c.show_when_empty,
        # Dedicated per-aspect-ratio positions: {"4:3": {top, left, width, height}}
        'positions': {
            p.aspect_ratio: {'top': p.top, 'left': p.left, 'width': p.width, 'height': p.height}
            for p in (c.positions or [])
        },
        'default_field_handler': c.default_field_handler,
        'default_content': c.default_content,
        # In use = at least one Contenttype field (TagConfig) renders into it.
        # Deleting it out from under a live field would break that field's
        # rendering, so the admin UI blocks deletion while this is true.
        'in_use': c.id in used_container_ids,
    }


def emit_layouts_update(socketio, app, db, room: Optional[str] = None):
    """Build a minimal layouts payload and emit to clients.

    Payload shape: {'data': [ {id, name, description, container_ids, in_use}, ... ]}
    """
    try:
        all_layouts = db.session.execute(db.select(Layout)).scalars().all()
        layouts = [
            {
                'id': layout.id,
                'name': layout.name,
                'description': layout.description or '',
                'container_ids': [c.id for c in (layout.contentcontainers or [])],
                'variations': [
                    {'aspect_ratio': v.aspect_ratio, 'container_ids': [c.id for c in (v.contentcontainers or [])]}
                    for v in (layout.variations or [])
                ],
                # In use = at least one Contenttype is bound to this Layout.
                'in_use': len(layout.contenttypes or []) > 0,
                # Which Contenttypes use it (for "used by" links in the admin).
                'contenttypes': [{'id': ct.id, 'name': ct.name} for ct in (layout.contenttypes or [])],
            }
            for layout in all_layouts
        ]
        payload = {'data': layouts}
        socketio.emit('displayhive:admin:stc:upd_layouts', payload, room=room or 'admins')
    except Exception:
        logger.exception("Error emitting layouts update")


def emit_containers_update(socketio, app, db, room: Optional[str] = None):
    """Build the full ContentContainer list payload and emit to clients."""
    try:
        all_containers = db.session.execute(db.select(ContentContainer).order_by(ContentContainer.order)).scalars().all()
        used_container_ids = {
            row[0] for row in db.session.execute(
                db.select(TagConfig.contentcontainer_id).where(TagConfig.contentcontainer_id.is_not(None)).distinct()
            ).all()
        }
        payload = {'data': [_serialize_container(c, used_container_ids) for c in all_containers]}
        socketio.emit('displayhive:admin:stc:upd_containers', payload, room=room or 'admins')
    except Exception:
        logger.exception("Error emitting containers update")
