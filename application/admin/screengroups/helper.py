"""Helpers for admin screengroups page: building and emitting screengroups lists."""

import logging

logger = logging.getLogger(__name__)

_EVENT = 'displayhive:admin:stc:upd_screengroups'


def _has_screengroups_access(db, sid):
    """True if the socket's caller may see the screengroups list.

    Deliberately either-right: screengroups.page is the obvious owner, but
    the Content page's screen-filter dropdown (content.page) also depends on
    this same list — it's a read-only name/count summary, not the group's
    full screen/content membership, so there's no reason to withhold it from
    a content-only user.
    """
    from application.socketio_handlers.auth import resolve_admin_user
    from application.security.permissions import has_right
    user = resolve_admin_user(sid)
    return has_right(db, user, 'screengroups.page') or has_right(db, user, 'content.page')


def emit_screengroups_update(socketio, app, db, room=None):
    """Build and emit the namespaced `displayhive:admin:stc:upd_screengroups` payload.

    Each screengroup entry follows a JSON:API-style shape with `attributes` and
    `relationships.screens` so the frontend can populate inverse relations without
    additional round-trips.

    Only pushed to sockets whose caller holds screengroups.page — this is a
    proactive server push (on connect, and after every mutation), not a
    response to an explicit request, so it needs its own right check rather
    than relying on the read handler's @require_right to have gated it.
    Falls back to the previous unconditional-broadcast behavior if per-socket
    enumeration is ever unavailable, so a masking failure never breaks the
    live screengroups list for users who *do* have the right.
    """
    with app.app_context():
        try:
            from application.models import Screengroup

            screengroups = db.session.execute(
                db.select(Screengroup).order_by(Screengroup.name)
            ).scalars().all()

            screengroups_data = [
                {
                    'id': sg.id,
                    'type': 'screengroup',
                    'attributes': {
                        'name': sg.name,
                        'screensCount': len(sg.screens),
                        'contentCount': len(sg.content_elements),
                        'is_one_screen': bool(getattr(sg, 'is_one_screen', False)),
                    },
                    'relationships': {
                        'screens': {
                            'data': [{'id': s.id, 'type': 'screen'} for s in sg.screens],
                        }
                    },
                }
                for sg in screengroups
            ]

            payload = {'data': screengroups_data}
            logger.debug('Emitting %s screengroups to %s', len(screengroups_data), room or 'admins')

            if room and room != 'admins':
                if _has_screengroups_access(db, room):
                    socketio.emit(_EVENT, payload, room=room)
                return

            try:
                participants = list(socketio.server.manager.get_participants('/', 'admins'))
            except Exception:
                participants = None

            if not participants:
                socketio.emit(_EVENT, payload, room='admins')
                return

            for sid, _eio_sid in participants:
                if _has_screengroups_access(db, sid):
                    socketio.emit(_EVENT, payload, room=sid)

        except Exception:
            logger.exception('Error emitting screengroups update')
