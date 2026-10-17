"""Icon: an icon of an installed icon library, with size and colour.

The value is "<library>/<icon-name>". The backend has no access to the SVGs (the libraries are installed
in DATA_DIR/icons), so it emits a placeholder that the screen turns into markup (icon-resolver.ts).
"""

import json
import logging
from html import escape as _html_escape

from markupsafe import Markup

from application.plugins.handlers import FieldHandler, RenderContext

logger = logging.getLogger(__name__)


def resolve_icon_color(raw, db=None) -> str:
    """Resolve an `icon` field's color value to a literal CSS color.

    A literal ('#rrggbb', 'red', …) passes through; a "@default:<id>"
    reference is resolved against the active Design's palette (same
    mechanism as the Designs page — see resolve_default_color in
    application/admin/designs/helper.py); a blank value, an unresolvable
    reference, or a missing db all yield '' (meaning "keep the icon's own
    colors").
    """
    raw = (raw or '').strip()
    if not raw:
        return ''
    if not raw.startswith('@default:'):
        return raw
    if db is None:
        return ''
    try:
        from application.utils.design import get_default_design
        from application.admin.designs.helper import resolve_default_color
        design = get_default_design(db)
        return resolve_default_color(design, raw) if design is not None else ''
    except Exception:
        logger.debug('resolve_icon_color: failed to resolve %r', raw, exc_info=True)
        return ''


class Handler(FieldHandler):
    id = 'icon'

    def render(self, rc: RenderContext):
        if not rc.has_value:
            return None
        raw = str(rc.value).strip()
        if '/' not in raw:
            return ''
        library, name = raw.split('/', 1)
        size = rc.option('size')
        try:
            size = float(size)
        except (TypeError, ValueError):
            size = 0
        size = size if size > 0 else 5
        color = resolve_icon_color(rc.option('color'), rc.db)
        color_attr = f' data-dh-icon-color="{_html_escape(color)}"' if color else ''
        return Markup(
            f'<div class="dh-icon"'
            f' data-dh-icon-library="{_html_escape(library)}"'
            f' data-dh-icon-name="{_html_escape(name)}"'
            f'{color_attr}'
            f' style="height:{size}vh;display:inline-block;"></div>'
        )

    def default_values(self, packed: str) -> dict:
        try:
            parsed = json.loads(packed)
        except (ValueError, TypeError):
            parsed = None
        if isinstance(parsed, dict) and 'icon' in parsed:
            return {
                'default': parsed.get('icon', ''),
                'default__size': parsed.get('size') or 0,
                'default__color': parsed.get('color', ''),
            }
        return {'default': packed}


def register(api):
    api.fieldhandlers.add(Handler())
