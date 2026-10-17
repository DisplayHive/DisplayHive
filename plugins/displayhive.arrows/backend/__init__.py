"""Arrow: a single character (an arrow) at a chosen size."""

import json
from html import escape as _html_escape

from markupsafe import Markup

from application.plugins.handlers import FieldHandler, RenderContext


class Handler(FieldHandler):
    id = 'arrows'

    def render(self, rc: RenderContext):
        if not rc.has_value:
            return None
        char = _html_escape(str(rc.value).strip())
        size = rc.values.get(f'{rc.field_name}_size', 5)
        try:
            size = float(size)
        except (ValueError, TypeError):
            size = 5
        if char:
            return Markup(f'<span style="font-size:{size}vh;line-height:1;">{char}</span>')
        return None

    def default_values(self, packed: str) -> dict:
        try:
            parsed = json.loads(packed)
            return {'default': parsed.get('char', ''), 'default_size': parsed.get('size', 5)}
        except (ValueError, TypeError, AttributeError):
            return {'default': packed}


def register(api):
    api.fieldhandlers.add(Handler())
