"""Helpers for admin contenttypes page (server-side).

Provides helper to emit the contenttypes list payload to admin clients.
"""

import logging
from typing import Optional

from application.models import Contenttype

logger = logging.getLogger(__name__)


def emit_contenttypes_update(socketio, app, db, room: Optional[str] = None):
    """Build a minimal contenttypes payload and emit to clients.

    Payload shape: {'data': [ {id, name, description}, ... ]}
    """
    try:
        all_ct = db.session.execute(db.select(Contenttype)).scalars().all()
        contenttypes = [
            {
                'id': ct.id,
                'name': ct.name,
                'description': ct.description or '',
            }
            for ct in all_ct
        ]

        payload = {'data': contenttypes}
        socketio.emit('displayhive:admin:stc:upd_contenttypes', payload, room=room or None)
    except Exception:
        logger.exception("Error emitting contenttypes update")
