"""Shared design/content utility helpers reused across multiple modules."""

import json
import os
import logging

logger = logging.getLogger(__name__)


def parse_content_html(raw, handlers) -> dict:
    """Parse ContentElement.html into {contentcontainer_id_str: rendered_html}.

    Rows created by the current pipeline already store this JSON map. Rows
    that predate the per-field container mapping (or came from a v3 import)
    store a single rendered HTML string instead — in that case the same
    string is applied to every one of *handlers*' containers, since legacy
    data only ever had one field/container per Contenttype.
    """
    try:
        parsed = json.loads(raw or '{}')
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {str(h.contentcontainer_id): (raw or '') for h in (handlers or [])}


def get_default_design(db):
    """Return the active default design using the standard fallback chain.

    Resolution order:
      1. Design with isDefault == True
      2. Design named 'default'
      3. First design by id
    """
    from application.models import Design

    design = db.session.execute(
        db.select(Design).where(Design.isDefault == True)
    ).scalar()
    if not design:
        design = db.session.execute(
            db.select(Design).where(Design.name == 'default')
        ).scalar()
    if not design:
        design = db.session.execute(
            db.select(Design).order_by(Design.id).limit(1)
        ).scalar()
    return design


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


def reload_devices_on_all_screens(socketio, db):
    """Send a RELOAD command to every device on every screen.

    Design is a single instance-wide setting (no per-screen override), so
    changing the active Design affects every screen at once.
    """
    from application.models import Screen

    screens = db.session.execute(db.select(Screen)).scalars().all()
    for screen in screens:
        reload_devices_on_screen(socketio, db, screen)


def media_file_urls(m) -> tuple:
    """Return (url, preview_url) for a Media record."""
    folder = m.folder_path or ''
    file_rel = f'{folder}/{m.filename}' if folder else m.filename
    preview_base = os.path.splitext(m.filename)[0] + '_preview.jpg'
    preview_rel = f'{folder}/{preview_base}' if folder else preview_base
    return f'/static/media/{file_rel}', f'/static/media_previews/{preview_rel}'
