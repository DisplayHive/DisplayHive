"""A Raw HTML field is rendered inside a sandboxed iframe (application/admin/content/helper.py).

The sandbox has no `allow-same-origin`, so the HTML — scripts, event handlers, `javascript:` links — runs
in an opaque origin and cannot reach the screen page around it. These tests pin that markup.
"""

import json
from html.parser import HTMLParser
from types import SimpleNamespace

from application.admin.content.helper import render_content_fields


class _Frames(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.frames = []
        self.other_tags = []

    def handle_starttag(self, tag, attrs):
        if tag == 'iframe':
            self.frames.append(dict(attrs))
        else:
            self.other_tags.append(tag)


def _render(value):
    tc = SimpleNamespace(field_name='html', field_handler='rawhtml', contentcontainer_id=1,
                         option_flags=None, default_value=None, contentcontainer=None)
    return render_content_fields([tc], json.dumps({'html': value}))['1']


def _frames(rendered):
    parser = _Frames()
    parser.feed(str(rendered))
    return parser


def test_raw_html_is_one_sandboxed_iframe():
    parser = _frames(_render('<p>Hello</p>'))
    assert len(parser.frames) == 1 and parser.other_tags == []
    frame = parser.frames[0]
    assert frame['sandbox'] == 'allow-scripts'
    assert 'allow-same-origin' not in frame['sandbox']
    assert frame['referrerpolicy'] == 'no-referrer'
    assert '<p>Hello</p>' in frame['srcdoc']


def test_the_html_cannot_break_out_of_the_srcdoc_attribute():
    payload = '"></iframe><script>alert(1)</script><img src=x onerror=alert(2)>'
    parser = _frames(_render(payload))
    # Still exactly one iframe and nothing else at the top level: the payload lives inside srcdoc.
    assert len(parser.frames) == 1
    assert parser.other_tags == []
    assert payload in parser.frames[0]['srcdoc']
    assert '<script>' not in str(_render(payload))


def test_empty_raw_html_renders_nothing():
    tc = SimpleNamespace(field_name='html', field_handler='rawhtml', contentcontainer_id=1,
                         option_flags=None, default_value=None, contentcontainer=None)
    result = render_content_fields([tc], json.dumps({'html': ''}))
    assert '<iframe' not in str(result.get('1', ''))
