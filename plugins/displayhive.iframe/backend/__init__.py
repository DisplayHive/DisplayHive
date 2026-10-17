"""iFrame: another web page shown inside the container (http and https only)."""

import urllib.parse
from html import escape as _html_escape

from markupsafe import Markup

from application.plugins.handlers import FieldHandler, RenderContext


class Handler(FieldHandler):
    id = 'iframe'

    def render(self, rc: RenderContext):
        if not rc.has_value:
            return None
        url = str(rc.value).strip()
        if urllib.parse.urlparse(url).scheme.lower() not in ('', 'http', 'https'):
            return ''
        if url:
            return Markup(
                f'<iframe src="{_html_escape(url)}"'
                f' style="width:100%;height:100%;border:none;"'
                f' allowfullscreen></iframe>'
            )
        return None


def register(api):
    api.fieldhandlers.add(Handler())
