"""Socket handlers for in-app contextual help content.

Read-only and available to any authenticated admin (no specific right
gates it — it's UI guidance, not privileged data).
"""

import logging

from flask import request

logger = logging.getLogger(__name__)

DEFAULT_LOCALE = 'en'


def register_admin_help_handlers(socketio, app, db):
    """Register socket handlers for in-app help content."""
    from application.socketio_handlers.auth import admin_handler

    def _serialize_help(locale):
        from application.models import HelpTopic

        topics = db.session.execute(db.select(HelpTopic)).scalars().all()
        result = {}
        for topic in topics:
            by_locale = {t.locale: t for t in topic.translations}
            translation = by_locale.get(locale) or by_locale.get(DEFAULT_LOCALE)
            if translation is None:
                continue
            result[topic.key] = {
                'category': topic.category,
                'context': topic.context,
                'title': translation.title,
                'body': translation.body,
                'docs_url': topic.docs_url,
            }
        return result

    @socketio.on('displayhive:admin:cts:get_all_help')
    @admin_handler
    def handle_get_all_help(data=None):
        locale = (data or {}).get('locale') or DEFAULT_LOCALE
        sid = getattr(request, 'sid', None)
        payload = _serialize_help(locale)
        socketio.emit('displayhive:admin:stc:all_help', payload, room=sid)
