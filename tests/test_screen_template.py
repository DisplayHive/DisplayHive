"""The screen page embeds the active Design's CSS in an inline <script>; it must
be a safely escaped JS string, whatever the CSS contains."""

import json
import re

import pytest

NASTY_CSS = (
    'body { content: "`${alert(1)}`"; }\n'
    "</script><script>alert('x')</script>\n"
    ".a::after { content: '\\\\' }"
)


@pytest.fixture()
def rendered(flask_app):
    from flask import render_template
    with flask_app.app.test_request_context('/'):
        return render_template('index.html', design_css=NASTY_CSS, design_html='')


def _css_literal(html: str) -> str:
    m = re.search(r'const css = (.*?);\n', html)
    assert m, 'design CSS assignment not found'
    return m.group(1)


def test_design_css_is_a_json_string_literal(rendered):
    literal = _css_literal(rendered)
    assert not literal.startswith('`')
    # A JSON string is a valid JS string literal and round-trips to the exact CSS.
    assert json.loads(literal) == NASTY_CSS


def test_design_css_cannot_close_the_script_block(rendered):
    literal = _css_literal(rendered)
    assert '</script>' not in literal.lower()
    assert '<' not in literal and '>' not in literal
