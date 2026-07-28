"""Helpers for admin Designs page (server-side).

Provides helper to emit the designs list payload to admin clients.
"""

import logging
from typing import Optional

from application.models import Design

logger = logging.getLogger(__name__)


def emit_designs_update(socketio, app, db, room: Optional[str] = None):
    """Build a minimal designs payload and emit to clients.

    Payload shape: {'data': [ {id, name, description, isDefault}, ... ]}
    """
    try:
        all_designs = db.session.execute(db.select(Design)).scalars().all()
        designs = [
            {
                'id': d.id,
                'name': d.name,
                'description': d.description or '',
                'isDefault': bool(getattr(d, 'isDefault', False)),
            }
            for d in all_designs
        ]

        payload = {'data': designs}
        socketio.emit('displayhive:admin:stc:upd_designs', payload, room=room or 'admins')
    except Exception:
        logger.exception("Error emitting designs update")
