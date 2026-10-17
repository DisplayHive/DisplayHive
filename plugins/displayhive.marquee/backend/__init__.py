"""Marquee: text that scrolls across the container."""

import json
from html import escape as _html_escape

from markupsafe import Markup

from application.plugins.handlers import FieldHandler, RenderContext


class Handler(FieldHandler):
    id = 'marquee'

    def render(self, rc: RenderContext):
        if rc.field_name not in rc.values:
            return None
        text = str(rc.values.get(rc.field_name, '')).strip()
        speed = rc.option('speed', 20)
        try:
            speed = float(speed)
        except (TypeError, ValueError):
            speed = 20
        if speed <= 0:
            speed = 20
        escaped = _html_escape(text)
        return Markup(
            f'<style>@keyframes dh-marquee{{from{{transform:translateX(100vw)}}to{{transform:translateX(-100%)}}}}</style>'
            f'<div style="overflow:hidden;white-space:nowrap;width:100%;height:100%;display:flex;align-items:center;">'
            f'<span style="display:inline-block;animation:dh-marquee {speed:.1f}s linear infinite;">{escaped}</span>'
            f'</div>'
        )

    def default_values(self, packed: str) -> dict:
        try:
            parsed = json.loads(packed)
            return {'default': parsed.get('text', ''), 'default__speed': parsed.get('speed', 20)}
        except (ValueError, TypeError, AttributeError):
            return {'default': packed, 'default__speed': 20}


def register(api):
    api.fieldhandlers.add(Handler())
