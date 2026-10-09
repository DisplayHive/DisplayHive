import logging

from flask import request

logger = logging.getLogger(__name__)

# Keys the generic settings endpoint is allowed to write, and the only
# SystemSetting keys the import/export feature ever touches (see
# application/admin/importexport/helper.py). Anything else (e.g.
# telegram_token) has its own dedicated, validated handler and must not be
# settable through this catch-all upsert, nor leave the instance in an
# export file.
ALLOWED_SETTING_KEYS = {
    'hide_powered_by', 'timezone',
    'welcome_headline', 'welcome_text',
    'hide_community_links', 'hide_helping_hand',
    'hide_demo_mode',
    'hide_user_tours', 'hide_admin_tours',
    'content_edit_preview_size',
    'content_list_preview_size',
    'screen_log_max_age_hours', 'screen_log_max_rows',
    'screen_status_indicator',
}


def _get_system_settings(db):
    """Return all system settings as a {key: value} dict."""
    from application.models import SystemSetting
    rows = db.session.execute(db.select(SystemSetting)).scalars().all()
    return {row.key: row.value for row in rows}


def broadcast_admin_settings(socketio, db, sid=None):
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
        'system_settings': _get_system_settings(db),
        'server_time': datetime.now(timezone.utc).isoformat(),
    }
    socketio.emit('displayhive:admin:stc:admin_settings', payload, room=sid or None)


def register_admin_settings_handlers(socketio, app, db):
    """Register socket handlers for the admin Settings page."""
    from application.socketio_handlers.auth import require_right, fields
    from application.socketio_handlers.actions import admin_action, get_or_fail, Fail, ok

    def _emit_settings(sid=None):
        broadcast_admin_settings(socketio, db, sid)

    @socketio.on('displayhive:admin:cts:get_admin_settings')
    @require_right('settings.page')
    def get_admin_settings(message=None):
        _emit_settings(getattr(request, 'sid', None))

    # ── Outgoing requests to private networks (application/net.py) ─────────────
    # Deliberately not one of ALLOWED_SETTING_KEYS: it is a security switch, so it
    # is neither writable through the generic endpoint below nor part of an
    # export/import file, and only a Superadmin may flip it.

    def _outbound_state():
        from application.models import SystemSetting
        from application import net
        row = db.session.execute(db.select(SystemSetting).where(SystemSetting.key == net.SETTING_KEY)).scalar_one_or_none()
        stored = bool(row and (row.value or '').strip().lower() in ('1', 'true', 'yes', 'on'))
        return ok(allow_private=stored or net.env_allows_private(), forced_by_env=net.env_allows_private())

    @socketio.on('displayhive:admin:cts:get_outbound_policy')
    @require_right('settings.page')
    def get_outbound_policy(data=None):
        return _outbound_state()

    @socketio.on('displayhive:admin:cts:set_outbound_policy')
    @admin_action('settings.edit')
    def set_outbound_policy(data=None):
        from application.models import SystemSetting
        from application import net
        from application.permissions import is_superadmin
        from application.socketio_handlers.auth import current_admin_user
        if not is_superadmin(db, current_admin_user()):
            raise Fail('Only a Superadmin can change this.')
        (allow_private,) = fields(data, 'allow_private')
        value = 'true' if bool(allow_private) else 'false'
        row = db.session.execute(db.select(SystemSetting).where(SystemSetting.key == net.SETTING_KEY)).scalar_one_or_none()
        if row:
            row.value = value
        else:
            db.session.add(SystemSetting(key=net.SETTING_KEY, value=value))
        db.session.commit()
        net.invalidate()
        logger.warning('Outgoing requests to private networks %s by %s',
                       'ALLOWED' if value == 'true' else 'blocked', getattr(current_admin_user(), 'username', '?'))
        return _outbound_state()

    @socketio.on('displayhive:admin:cts:set_default_design')
    @admin_action('settings.edit')
    def handle_set_default_design(data):
        sid = getattr(request, 'sid', None)
        (design_id,) = fields(data, 'id')

        from application.models import Design
        new_default = get_or_fail(db, Design, design_id, 'Design')
        for d in db.session.execute(db.select(Design)).scalars().all():
            d.isDefault = False
        new_default.isDefault = True
        db.session.commit()

        try:
            from application.utils import push_content_list_to_all_screens
            push_content_list_to_all_screens(socketio, app, db)
        except Exception:
            logger.exception('set_default_design: failed to push content to screens')

        _emit_settings(sid)
        return ok()

    @socketio.on('displayhive:admin:cts:set_system_settings')
    @admin_action('settings.edit')
    def handle_set_system_settings(data):
        """Upsert one or more system settings. data = {settings: {key: value, ...}}"""
        sid = getattr(request, 'sid', None)
        (settings,) = fields(data, 'settings')
        if not settings or not isinstance(settings, dict):
            raise Fail('No settings provided')

        from application.models import SystemSetting
        from application import screen_logs
        rejected = []
        for key, value in settings.items():
            if key in screen_logs.RETENTION_SETTINGS:
                try:
                    value = screen_logs.validate_retention_setting(key, value)
                except ValueError as problem:
                    raise Fail(str(problem)) from None
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

        if 'screen_status_indicator' in settings:
            from application.socketio_handlers.devconfig import push_deviceconfig_to_connected_devices
            push_deviceconfig_to_connected_devices(socketio, db)

        if rejected:
            # The known keys above are already saved; only the unknown ones are refused.
            raise Fail(f'Unknown setting(s): {", ".join(rejected)}')
        return ok()
