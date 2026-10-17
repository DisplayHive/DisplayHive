"""Short text: plain text, escaped, line breaks kept."""

from html import escape as _html_escape

from markupsafe import Markup

from application.plugins.handlers import FieldHandler, RenderContext


class Handler(FieldHandler):
    id = 'textklein'

    def render(self, rc: RenderContext):
        if rc.field_name not in rc.values:
            return None
        return Markup(_html_escape(str(rc.value)).replace('\n', '<br>'))


def register(api):
    api.fieldhandlers.add(Handler())
