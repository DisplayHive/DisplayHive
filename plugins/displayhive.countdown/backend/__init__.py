"""Countdown: counts down to a date and time; the screen keeps it ticking (frontends/screen/ts/screen/countdown.ts)."""

import json
from html import escape as _html_escape

from markupsafe import Markup

from application.plugins.handlers import FieldHandler, RenderContext


class Handler(FieldHandler):
    id = 'countdown'

    def render(self, rc: RenderContext):
        target = str(rc.values.get(rc.field_name, '')).strip()
        fmt_str = str(rc.option('format', 'DD:HH:mm:ss')).strip() or 'DD:HH:mm:ss'
        finished_text = str(rc.option('finished_text', '')).strip()
        return Markup(
            f'<div class="dh-countdown" data-dh-countdown="1"'
            f' data-dh-countdown-target="{_html_escape(target)}"'
            f' data-dh-countdown-format="{_html_escape(fmt_str)}"'
            f' data-dh-countdown-finished="{_html_escape(finished_text)}"></div>'
        )

    def default_values(self, packed: str) -> dict:
        try:
            parsed = json.loads(packed)
            return {
                'default': parsed.get('target', ''),
                'default__format': parsed.get('format', 'DD:HH:mm:ss'),
                'default__finished_text': parsed.get('finished_text', ''),
            }
        except (ValueError, TypeError, AttributeError):
            return {'default': packed, 'default__format': 'DD:HH:mm:ss', 'default__finished_text': ''}


def register(api):
    api.fieldhandlers.add(Handler())
