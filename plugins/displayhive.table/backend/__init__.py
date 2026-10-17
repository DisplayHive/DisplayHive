"""Table: a JSON table (columns and rows) rendered as an HTML table with escaped cells."""

import json
from html import escape as _html_escape

from markupsafe import Markup

from application.plugins.handlers import FieldHandler, RenderContext


def render_table(raw_value) -> str:
    """Render a table field value (JSON) as an HTML <table>."""
    try:
        data = json.loads(str(raw_value or ''))
        columns = data.get('columns', [])
        rows = data.get('rows', [])
        if not isinstance(columns, list) or not isinstance(rows, list):
            return ''
    except Exception:
        return ''

    parts = ['<table class="dh-table">']
    if columns:
        parts.append('<thead><tr>')
        for col in columns:
            parts.append(f'<th>{_html_escape(str(col))}</th>')
        parts.append('</tr></thead>')
    if rows:
        parts.append('<tbody>')
        for row in rows:
            parts.append('<tr>')
            if isinstance(row, list):
                for cell in row:
                    parts.append(f'<td>{_html_escape(str(cell))}</td>')
            parts.append('</tr>')
        parts.append('</tbody>')
    parts.append('</table>')
    return ''.join(parts)


class Handler(FieldHandler):
    id = 'table'

    def render(self, rc: RenderContext):
        return Markup(render_table(rc.values.get(rc.field_name, '')))


def register(api):
    api.fieldhandlers.add(Handler())
