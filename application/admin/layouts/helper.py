"""Helpers for admin Layouts page (server-side).

Provides helpers to emit the layouts and containers list payloads to admin clients.
"""

import logging
from typing import Optional

from application.models import Layout, ContentContainer, TagConfig

logger = logging.getLogger(__name__)


def _serialize_container(c, used_container_ids: set) -> dict:
    return {
        'id': c.id,
        'name': c.name,
        'title': c.title or c.name,
        'order': c.order,
        'top': c.top,
        'left': c.left,
        'width': c.width,
        'height': c.height,
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
                # In use = at least one Contenttype is bound to this Layout.
                'in_use': len(layout.contenttypes or []) > 0,
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
