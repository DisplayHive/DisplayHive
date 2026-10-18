"""iFrame: another web page shown inside the container.

Only absolute http(s) addresses of other sites. The frame keeps its own origin (``allow-same-origin`` so
embeds that need cookies or storage keep working), which is safe only because DisplayHive's own origin is
refused: a relative path, the ``PUBLIC_URL`` host or a loopback address would load a page that could then
reach the page around it. No referrer is sent.
"""

import urllib.parse
from html import escape as _html_escape

from flask import current_app, has_app_context
from markupsafe import Markup

from application.plugins.handlers import FieldHandler, RenderContext


SANDBOX = 'allow-scripts allow-same-origin allow-forms allow-popups allow-presentation'
_LOOPBACK = ('localhost', '127.0.0.1', '::1', '0.0.0.0')


def _is_own_origin(parsed) -> bool:
    host = (parsed.hostname or '').lower()
    if host in _LOOPBACK or host.endswith('.localhost'):
        return True
    public = current_app.config.get('PUBLIC_URL') if has_app_context() else None
    return bool(public) and urllib.parse.urlparse(str(public)).netloc.lower() == parsed.netloc.lower()


class Handler(FieldHandler):
    id = 'iframe'

    def render(self, rc: RenderContext):
        if not rc.has_value:
            return None
        url = str(rc.value).strip()
        if not url:
            return None
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.lower() not in ('http', 'https') or not parsed.netloc or _is_own_origin(parsed):
            return ''
        return Markup(
            f'<iframe src="{_html_escape(url)}"'
            f' sandbox="{SANDBOX}" referrerpolicy="no-referrer"'
            f' style="width:100%;height:100%;border:none;"'
            f' allowfullscreen></iframe>'
        )


def register(api):
    api.fieldhandlers.add(Handler())
