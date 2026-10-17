"""QR code: a code for a link, text, contact, Wi-Fi access, e-mail, SMS, phone number, map position, event or payment.

The code is drawn on the server as an inline SVG (the ``segno`` library), so it shows in the admin previews and on
a screen that is offline just the same, and needs no script on the screen. What it says (the text a phone turns into
an action) is built in payload.py.

A field's values: ``<name>`` is the link or the text of the types ``url`` and ``text``; every other value is
``<name>__<key>``: ``type`` (see payload.TYPES), the type's own keys, and the looks: ``size`` (vh, empty: as large as
the container allows), ``fg`` / ``bg`` (colours, ``#rrggbb``; empty background: transparent), ``ec`` (error correction
l/m/q/h) and ``border`` (quiet zone in modules).
"""

import json
import logging
import re

import segno
from markupsafe import Markup

from application.plugins.handlers import FieldHandler, RenderContext

from .payload import TYPES, payload_for

logger = logging.getLogger(__name__)

_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')
_LEVELS = ('l', 'm', 'q', 'h')


def _color(value, default):
    value = str(value or '').strip()
    return value if _COLOR.match(value) else default


def draw(text: str, *, size=0, fg='#000000', bg='#ffffff', ec='m', border=2) -> str:
    """The SVG of a code for *text*, or ``''`` when it does not fit in a QR code."""
    try:
        code = segno.make(text, error=ec if ec in _LEVELS else 'm', micro=False, boost_error=False)
    except (segno.DataOverflowError, ValueError):
        logger.warning('A QR code field holds more than a QR code can carry (%s characters)', len(text))
        return ''
    border = max(0, min(int(border), 8))
    svg = code.svg_inline(scale=1, border=border, dark=_color(fg, '#000000'), light=_color(bg, None) if bg else None,
                          omitsize=True, svgclass='dh-qrcode-svg', lineclass=None)
    try:
        side = float(size)
    except (TypeError, ValueError):
        side = 0
    box = f'height:{side:g}vh;width:{side:g}vh;' if side > 0 else 'width:100%;height:100%;'
    style = f'{box}max-width:100%;max-height:100%;display:block;shape-rendering:crispEdges;'
    svg = svg.replace('<svg ', f'<svg style="{style}" ', 1)
    return ('<div class="dh-qrcode" style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;">'
            f'{svg}</div>')


class Handler(FieldHandler):
    id = 'qrcode'

    def render(self, rc: RenderContext):
        kind = str(rc.option('type', 'url') or 'url')
        if kind not in TYPES:
            kind = 'url'
        values = {key: rc.option(key, '') for key in TYPES[kind][1]}
        main = str(rc.values.get(rc.field_name, '') or '')
        values['url'] = values['text'] = main
        text = payload_for(kind, values)
        if not text:
            return ''
        try:
            border = int(rc.option('border', 2) or 2)
        except (TypeError, ValueError):
            border = 2
        bg = rc.option('bg', '#ffffff')
        return Markup(draw(text, size=rc.option('size', 0), fg=rc.option('fg', '#000000'),
                           bg=bg if bg != '' else '', ec=str(rc.option('ec', 'm') or 'm').lower(), border=border))

    def default_values(self, packed: str) -> dict:
        # A container's default: {"content": …, "type": …, "<key>": …} — `content` is the field's own value.
        try:
            parsed = json.loads(packed)
        except (ValueError, TypeError):
            return {'default': packed}
        if not isinstance(parsed, dict):
            return {'default': packed}
        out = {'default': str(parsed.get('content', ''))}
        for key, value in parsed.items():
            if key != 'content':
                out[f'default__{key}'] = value
        return out


def register(api):
    api.fieldhandlers.add(Handler())
