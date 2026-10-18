"""Content is stored rendered (``ContentElement.html``), so what a field's rendering depends on beyond the element's own
values has to render it again when that changes.

A field handler says what its output depends on with ``FieldHandler.depends_on``:

* ``'design'`` — the active Design (the icon handler resolves a palette colour at render time),
* ``'media'``  — the media library (a random image by tag puts the matching files into the HTML).

When that changes (a Design is saved or made the default, media are uploaded, changed or deleted) the host renders the
content types that use such a handler again and pushes the result to the screens: ``schedule(kind)``. Calls that come
in a burst (a hundred uploads) are coalesced into one run a few seconds after the last. After an import everything is
rendered again (``'all'``): the imported HTML was made against another database.
"""

import logging
import threading

logger = logging.getLogger(__name__)

DELAY_SECONDS = 3.0
ALL = 'all'

_lock = threading.Lock()
_pending: set = set()
_running = False


def contenttypes_depending_on(db, kinds) -> list:
    """Ids of the content types that have a field whose handler depends on one of *kinds* (``'all'``: every content type)."""
    from application.models import Contenttype, TagConfig
    from application.plugins.registry import registry
    if ALL in kinds:
        return sorted(db.session.execute(db.select(Contenttype.id)).scalars().all())
    handlers = sorted({h for kind in kinds for h in registry.handlers_depending_on(kind)})
    if not handlers:
        return []
    return sorted({row for row in db.session.execute(
        db.select(TagConfig.contenttype_id).where(TagConfig.field_handler.in_(handlers))).scalars().all() if row is not None})


def rerender_now(socketio, db, kinds) -> int:
    """Render again the content that depends on *kinds* and push it to the screens; returns how many elements changed."""
    from application.admin.content.helper import rerender_content_element_for_contenttype
    from application.socketio_handlers.upd_content import send_upd_content
    updated = []
    for contenttype_id in contenttypes_depending_on(db, kinds):
        updated.extend(rerender_content_element_for_contenttype(db, contenttype_id))
    if updated:
        send_upd_content(socketio, db, content_ids=updated)
        logger.info('Rendered %s content element(s) again after a change of %s', len(updated), ', '.join(sorted(kinds)))
    return len(updated)


def schedule(kind: str) -> None:
    """Something content's rendering depends on changed: render the dependent content again soon (coalesced)."""
    global _running
    from application.plugins import host
    socketio, app = host.socketio(), host.app()
    if socketio is None or app is None:
        return
    with _lock:
        _pending.add(kind)
        if _running:
            return
        _running = True

    def run():
        global _running
        try:
            while True:
                socketio.sleep(DELAY_SECONDS)
                with _lock:
                    kinds = set(_pending)
                    _pending.clear()
                try:
                    with app.app_context():
                        from application.models import db
                        rerender_now(socketio, db, kinds)
                except Exception:
                    logger.exception('Rendering content again after a change failed')
                with _lock:
                    if not _pending:
                        _running = False
                        return
        except BaseException:
            with _lock:
                _running = False
            raise

    socketio.start_background_task(run)
