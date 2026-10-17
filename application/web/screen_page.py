"""The screen/kiosk page served at `/`."""

import logging

from flask import Blueprint, current_app, render_template, request

from application.models import db

logger = logging.getLogger(__name__)
bp = Blueprint('screen_page', __name__)


@bp.route('/')
def index():
    """Serve the screen/kiosk page with the active Design's HTML/CSS background.

    Design is a single, instance-wide setting (no per-screen override).
    Containers are no longer baked into the Design's markup — they're created
    dynamically client-side, positioned via vh/vw, from the `upd_content`
    socket payload (see application/socketio_handlers/upd_content.py).

    Supports an optional ?preview=true&content_id=<id>&container=<name> query
    string so the admin UI can render a single content item for preview
    without the normal playlist logic.
    """
    preview_mode = request.args.get('preview', 'false').lower() == 'true'
    content_id = request.args.get('content_id', type=int)
    preview_container = request.args.get('container', 'maincontent')

    from application.utils import get_default_design
    design = get_default_design(db)

    if design:
        design_html = design.html or ''
        design_css = design.css or ''
    else:
        design_html = ''
        design_css = ''

    try:
        from application.models import SystemSetting
        row = db.session.execute(db.select(SystemSetting).where(SystemSetting.key == 'hide_powered_by')).scalar_one_or_none()
        hide_powered_by = (row.value if row else '') in ('true', '1', 'yes')
    except Exception:
        logger.warning('Could not read the hide_powered_by setting; showing the badge', exc_info=True)
        db.session.rollback()
        hide_powered_by = False

    from application.plugins import service as plugin_service
    plugins = [p for p in plugin_service.public_list(current_app) if p['screen']]

    return render_template('index.html',
                           plugins=plugins,
                           async_mode=current_app.extensions['socketio'].async_mode,
                           design_html=design_html,
                           design_css=design_css,
                           preview_mode=preview_mode,
                           preview_content_id=content_id,
                           preview_container=preview_container,
                           hide_powered_by=hide_powered_by)
