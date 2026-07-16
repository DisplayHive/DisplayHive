"""Shared template/content utility helpers reused across multiple modules."""

import os
import logging

logger = logging.getLogger(__name__)


def get_default_template(db):
    """Return the active default template using the standard fallback chain.

    Resolution order:
      1. Template with isDefault == True
      2. Template named 'default'
      3. First template by id
    """
    from application.models import Template

    template = db.session.execute(
        db.select(Template).where(Template.isDefault == True)
    ).scalar()
    if not template:
        template = db.session.execute(
            db.select(Template).where(Template.name == 'default')
        ).scalar()
    if not template:
        template = db.session.execute(
            db.select(Template).order_by(Template.id).limit(1)
        ).scalar()
    return template


def reload_devices_on_screen(socketio, db, screen):
    """Mark all devices on *screen* offline and send a RELOAD command to each."""
    from application.models import Device

    devices = db.session.execute(
        db.select(Device).where(Device.screen_id == screen.id)
    ).scalars().all()
    for device in devices:
        if getattr(device, 'devicekey', None):
            try:
                device.is_online = False
                db.session.add(device)
                db.session.commit()
            except Exception:
                db.session.rollback()
            socketio.emit('command', {'CMD': 'RELOAD'}, room=f'device_{device.devicekey}')
    logger.info("Reload command sent to screen '%s'", screen.name)


def reload_devices_for_template(socketio, db, template):
    """Send a RELOAD command to every device whose screen uses *template*.

    A screen uses a template either directly (`Screen.template_id ==
    template.id`) or implicitly, by leaving `template_id` unset, when
    *template* is the resolved system default.
    """
    from application.models import Screen

    if getattr(template, 'isDefault', False):
        screens = db.session.execute(
            db.select(Screen).where(
                db.or_(Screen.template_id == template.id, Screen.template_id.is_(None))
            )
        ).scalars().all()
    else:
        screens = db.session.execute(
            db.select(Screen).where(Screen.template_id == template.id)
        ).scalars().all()

    for screen in screens:
        reload_devices_on_screen(socketio, db, screen)


def build_field_handlers(contenttype_obj) -> dict:
    """Return {field_name: field_handler} from a Contenttype's tagconfigs."""
    if not contenttype_obj:
        return {}
    return {
        tc.field_name: tc.field_handler
        for tc in (getattr(contenttype_obj, 'tagconfigs', None) or [])
        if getattr(tc, 'field_name', None) and getattr(tc, 'field_handler', None)
    }


def media_file_urls(m) -> tuple:
    """Return (url, preview_url) for a Media record."""
    folder = m.folder_path or ''
    file_rel = f'{folder}/{m.filename}' if folder else m.filename
    preview_base = os.path.splitext(m.filename)[0] + '_preview.jpg'
    preview_rel = f'{folder}/{preview_base}' if folder else preview_base
    return f'/static/media/{file_rel}', f'/static/media_previews/{preview_rel}'
