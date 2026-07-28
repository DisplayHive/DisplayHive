import logging

from flask import request

logger = logging.getLogger(__name__)


def register_admin_settings_handlers(socketio, app, db):
    """Register socket handlers for the admin Settings page."""
    from application.socketio_handlers.auth import require_right

    # Keys the generic settings endpoint is allowed to write. Anything else
    # (e.g. telegram_token) has its own dedicated, validated handler and must
    # not be settable through this catch-all upsert.
    ALLOWED_SETTING_KEYS = {
        'hide_powered_by', 'timezone',
        'welcome_headline', 'welcome_text',
        'hide_community_links', 'hide_helping_hand',
        'hide_demo_mode',
    }

    def _get_system_settings():
        """Return all system settings as a {key: value} dict."""
        from application.models import SystemSetting
        rows = db.session.execute(db.select(SystemSetting)).scalars().all()
        return {row.key: row.value for row in rows}

    def _emit_settings(sid=None):
        """Build the full settings payload and emit it."""
        from application.models import Design
        from datetime import datetime, timezone
        designs = db.session.execute(db.select(Design)).scalars().all()
        design_list = [
            {'id': d.id, 'name': d.name, 'isDefault': bool(getattr(d, 'isDefault', False))}
            for d in designs
        ]
        default_design_id = next(
            (d.id for d in designs if getattr(d, 'isDefault', False)), None
        )
        payload = {
            'designs': design_list,
            'default_design_id': default_design_id,
            'system_settings': _get_system_settings(),
            'server_time': datetime.now(timezone.utc).isoformat(),
        }
        socketio.emit('displayhive:admin:stc:admin_settings', payload, room=sid or None)

    @socketio.on('displayhive:admin:cts:get_admin_settings')
    @require_right('settings.page')
    def get_admin_settings(message=None):
        _emit_settings(getattr(request, 'sid', None))

    @socketio.on('displayhive:admin:cts:set_default_design')
    @require_right('settings.edit')
    def handle_set_default_design(data):
        sid = getattr(request, 'sid', None)
        design_id = data.get('id') if data else None
        if design_id is None:
            return

        from application.models import Design
        all_designs = db.session.execute(db.select(Design)).scalars().all()
        for d in all_designs:
            d.isDefault = False

        new_default = db.session.get(Design, design_id)
        if not new_default:
            logger.warning('Design with id %s not found', design_id)
            return

        new_default.isDefault = True
        db.session.commit()

        try:
            from application.utils import push_content_list_to_all_screens
            push_content_list_to_all_screens(socketio, app, db)
        except Exception:
            logger.exception('set_default_design: failed to push content to screens')

        _emit_settings(sid)

    @socketio.on('displayhive:admin:cts:set_system_settings')
    @require_right('settings.edit')
    def handle_set_system_settings(data):
        """Upsert one or more system settings. data = {settings: {key: value, ...}}"""
        sid = getattr(request, 'sid', None)
        settings = data.get('settings', {}) if data else {}
        if not settings:
            return {'success': False, 'error': 'No settings provided'}

        from application.models import SystemSetting
        rejected = []
        for key, value in settings.items():
            if key not in ALLOWED_SETTING_KEYS:
                logger.warning('Ignoring unknown system setting key: %r', key)
                rejected.append(key)
                continue
            existing = db.session.execute(
                db.select(SystemSetting).where(SystemSetting.key == key)
            ).scalar_one_or_none()
            if existing:
                existing.value = value
            else:
                db.session.add(SystemSetting(key=key, value=value))

        db.session.commit()
        _emit_settings(sid)

        if rejected:
            return {'success': False, 'error': f'Unknown setting(s): {", ".join(rejected)}'}
        return {'success': True}
