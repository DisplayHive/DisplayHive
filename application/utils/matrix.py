"""Utilities for zuweisungen (assignments) matrix operations."""

import logging

logger = logging.getLogger(__name__)


def get_zuweisungen_matrix_data(db):
    """Build zuweisungen (assignment) matrix data with screens and screengroups"""
    try:
        from application.models import Screen, Screengroup

        screengroup_entries = db.session.execute(db.select(Screengroup)).scalars().all()
        screens = db.session.execute(db.select(Screen)).scalars().all()

        screengroups = [
            {'id': sg.id, 'name': sg.name}
            for sg in screengroup_entries
        ]

        screens_data = [
            {
                'id': screen.id,
                'name': screen.name,
                'screengroup_ids': [sg.id for sg in screen.screengroups]
            }
            for screen in screens
        ]

        return {
            'screengroups': screengroups,
            'screens': screens_data
        }
    except Exception:
        logger.exception("Error building zuweisungen matrix")
        return {'screengroups': [], 'screens': []}


def emit_zuweisungen_matrix_update(socketio, db):
    """Broadcast zuweisungen matrix update to all admin clients"""
    try:
        matrix_data = get_zuweisungen_matrix_data(db)
        socketio.emit('upd_zuweisungen_matrix', {'data': matrix_data})
        logger.debug("Emitted zuweisungen matrix update")
    except Exception:
        logger.exception("Error emitting zuweisungen matrix")
