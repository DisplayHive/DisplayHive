"""Raw HTML: the stored HTML, shown in a sandboxed frame of its own.

The iframe is sandboxed without `allow-same-origin`, so it gets an opaque origin — whatever the HTML does
(scripts, event handlers, `javascript:` links) cannot reach the page around it, its DOM, its Socket.IO
connection or its storage. Scripts still run inside, so embed codes keep working. The frame does not
inherit the design's fonts or colours: it is a separate document.
"""

from html import escape as _html_escape

from markupsafe import Markup

from application.plugins.handlers import FieldHandler, RenderContext

FRAME_STYLE = 'html,body{margin:0;width:100%;height:100%;background:transparent;}'


def sandboxed_html(html: str) -> Markup:
    """The field's value as a sandboxed ``<iframe srcdoc>``."""
    document = (
        '<!doctype html><meta charset="utf-8">'
        f'<style>{FRAME_STYLE}</style>'
        f'{html}'
    )
    return Markup(
        '<iframe sandbox="allow-scripts" referrerpolicy="no-referrer"'
        ' style="width:100%;height:100%;border:none;background:transparent;"'
        f' srcdoc="{_html_escape(document, quote=True)}"></iframe>'
    )


class Handler(FieldHandler):
    id = 'rawhtml'

    def render(self, rc: RenderContext):
        if not rc.has_value:
            return None
        return sandboxed_html(str(rc.value))


def register(api):
    api.fieldhandlers.add(Handler())
