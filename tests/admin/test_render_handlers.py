"""What every field handler renders — pinned byte for byte (tests/admin/golden/render_handlers.json).

The handlers are plugins (``plugins/<id>/``), and the host calls them through the plugin registry. These
cases are the contract of that move: the HTML each handler produces for a stored value must not change
unless a handler is changed on purpose. To accept an intended change run the tests once with
``UPDATE_GOLDEN=1`` and review the diff of the JSON file.
"""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from application.admin.content.helper import render_content_fields, render_default_value

GOLDEN = Path(__file__).parent / 'golden' / 'render_handlers.json'

# (case id, handler id, flat value dict as stored in ContentElement.serialized_input)
FIELD_CASES = [
    ('textklein', 'textklein', {'f': 'Hello <b>&"world"</b>\nline 2'}),
    ('textklein-empty', 'textklein', {'f': ''}),
    ('textbig', 'textbig', {'f': 'Multi\nline <script>x</script>'}),
    ('link', 'link', {'f': 'https://example.org/?a=1&b=2'}),
    ('wysiwyg', 'wysiwyg', {'f': '<p><strong>Rich</strong> <em>text</em></p>'}),
    ('numbers', 'numbers', {'f': 42}),
    ('numbers-zero', 'numbers', {'f': 0}),
    ('checkbox-true', 'checkbox', {'f': True}),
    ('checkbox-false', 'checkbox', {'f': False}),
    ('table', 'table', {'f': json.dumps({'columns': ['A', 'B <x>'], 'rows': [['1', '2'], ['3', '4']]})}),
    ('table-bad', 'table', {'f': 'not json'}),
    ('image', 'image', {'f': 'https://example.org/a.png', 'f__size': 40, 'f__fit': 'cover'}),
    ('image-plain', 'image', {'f': '/static/media/x.png'}),
    ('image-data', 'image', {'f': 'data:image/png;base64,AAAA'}),
    ('image-js', 'image', {'f': 'javascript:alert(1)'}),
    ('icon', 'icon', {'f': 'lucide/home', 'f__size': 8, 'f__color': '#ff0000'}),
    ('icon-default-size', 'icon', {'f': 'lucide/home'}),
    ('icon-no-library', 'icon', {'f': 'home'}),
    ('arrows', 'arrows', {'f': '→', 'f_size': 12}),
    ('arrows-default', 'arrows', {'f': '<'}),
    ('datetime', 'datetime_format', {'f': 'HH:mm:ss DD.MM.YYYY'}),
    ('datetime-default', 'datetime_format', {}),
    ('countdown', 'countdown', {'f': '2030-01-01T10:00', 'f__format': 'DD:HH', 'f__finished_text': 'Done "now"'}),
    ('countdown-default', 'countdown', {'f': '2030-01-01T10:00'}),
    ('marquee', 'marquee', {'f': 'Scrolling <text>', 'f__speed': 12.5}),
    ('marquee-bad-speed', 'marquee', {'f': 'x', 'f__speed': -3}),
    ('rawhtml', 'rawhtml', {'f': '<p onclick="x">Hi</p><script>1</script>'}),
    ('rawhtml-empty', 'rawhtml', {'f': ''}),
    ('iframe', 'iframe', {'f': 'https://example.org/embed?a=1&b="2"'}),
    ('iframe-js', 'iframe', {'f': 'javascript:alert(1)'}),
    ('iframe-relative', 'iframe', {'f': '/admin/'}),
    ('iframe-loopback', 'iframe', {'f': 'http://localhost:5000/'}),
    ('pretalx-empty', 'pretalx_table', {'f': '', 'f__type': 'list', 'f__linecount': 5}),
    ('none', '', {'f': 'ignored'}),
]

# (case id, handler id, the packed value stored in ContentContainer.default_content)
DEFAULT_CASES = [
    ('d-textklein', 'textklein', 'Plain <default>'),
    ('d-image-url', 'image', 'https://example.org/a.png'),
    ('d-image-json', 'image', json.dumps({'url': 'https://example.org/b.png', 'size': 30, 'fit': 'contain'})),
    ('d-icon', 'icon', json.dumps({'icon': 'lucide/star', 'size': 6, 'color': 'blue'})),
    ('d-arrows', 'arrows', json.dumps({'char': '↑', 'size': 9})),
    ('d-arrows-plain', 'arrows', '↓'),
    ('d-marquee', 'marquee', json.dumps({'text': 'News', 'speed': 15})),
    ('d-marquee-plain', 'marquee', 'Plain news'),
    ('d-countdown', 'countdown', json.dumps({'target': '2031-02-03T04:05', 'format': 'HH:mm', 'finished_text': 'Over'})),
    ('d-rawhtml', 'rawhtml', '<b>raw</b>'),
    ('d-iframe', 'iframe', 'https://example.org/'),
    ('d-datetime', 'datetime_format', 'HH:mm'),
    ('d-table', 'table', json.dumps({'columns': ['X'], 'rows': [['1']]})),
]


def _tagconfig(handler):
    return SimpleNamespace(field_name='f', field_handler=handler, contentcontainer_id=1,
                           option_flags=None, default_value=None, contentcontainer=None)


def _render_field(handler, values, db=None):
    return str(render_content_fields([_tagconfig(handler)], json.dumps(values), db=db).get('1', ''))


def _render_default(handler, packed, db=None):
    return str(render_default_value(handler, packed, db=db))


def _all_results(db=None):
    results = {}
    for case_id, handler, values in FIELD_CASES:
        results[case_id] = _render_field(handler, values, db)
    for case_id, handler, packed in DEFAULT_CASES:
        results[case_id] = _render_default(handler, packed, db)
    return results


def _load():
    return json.loads(GOLDEN.read_text(encoding='utf-8'))


@pytest.fixture()
def pretalx_plugin(flask_app):
    """The Pretalx integration ships bundled but switched off; render with it on."""
    from application.plugins import loader
    manifest = loader.discover()['displayhive.pretalx'][0]
    loader.load(manifest)
    yield
    loader.unload('displayhive.pretalx')


def test_every_handler_renders_what_it_always_did(flask_app, db_session, app_ctx, pretalx_plugin):
    results = _all_results(db=None)
    if os.environ.get('UPDATE_GOLDEN'):
        GOLDEN.write_text(json.dumps(results, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    expected = _load()
    assert set(results) == set(expected)
    for case_id in results:
        assert results[case_id] == expected[case_id], case_id


def test_the_cases_cover_every_handler_of_the_editor():
    covered = {h for _, h, _ in FIELD_CASES}
    assert covered >= {
        'textklein', 'textbig', 'link', 'wysiwyg', 'numbers', 'checkbox', 'table', 'image', 'icon', 'arrows',
        'datetime_format', 'countdown', 'marquee', 'rawhtml', 'iframe', 'pretalx_table', '',
    }


def test_the_clock_uses_the_instance_time_zone(flask_app, db_session, app_ctx):
    from application.models import SystemSetting, db
    db.session.add(SystemSetting(key='timezone', value='Europe/Berlin'))
    db.session.flush()
    assert _render_field('datetime_format', {'f': 'HH:mm'}, db=db) == (
        '<div class="dh-clock" data-dh-clock="HH:mm" data-dh-timezone="Europe/Berlin"></div>'
    )


def test_a_random_image_field_carries_the_whole_pool(flask_app, db_session, app_ctx):
    from application.models import db
    from datetime import datetime
    from application.models.content import Media
    now = datetime(2026, 1, 1)
    db.session.add_all([
        Media(filename='a.png', title='a', tags='sun, sea', folder_path='', mime_type='image/png', file_size=1, created_at=now),
        Media(filename='b.png', title='b', tags='sea', folder_path='trip', mime_type='image/png', file_size=1, created_at=now),
        Media(filename='c.png', title='c', tags='city', folder_path='', mime_type='image/png', file_size=1, created_at=now),
    ])
    db.session.flush()
    html = _render_field('image', {'f': '', 'f__image_mode': 'random_tags', 'f__image_tags': ['sea'], 'f__size': 30}, db=db)
    assert html.startswith('<img data-dh-random-pool=')
    assert '/static/media/a.png' in html and '/static/media/trip/b.png' in html
    assert 'c.png' not in html


def test_a_container_default_saved_as_a_key_bag_renders_like_the_packed_form(flask_app, db_session, app_ctx):
    from application.admin.content.helper import render_default_value
    assert render_default_value('textklein', '{"default": "DHCON 2027"}') == 'DHCON 2027'
    assert render_default_value('marquee', '{"default": "Hi", "default__speed": 30}') == render_default_value('marquee', '{"text": "Hi", "speed": 30}')


def test_iframe_refuses_the_own_origin_and_is_sandboxed(flask_app, db_session, app_ctx, monkeypatch):
    monkeypatch.setitem(flask_app.app.config, 'PUBLIC_URL', 'https://signage.example.org')
    own = ('https://signage.example.org/admin/', '//signage.example.org/', '/admin/', 'http://127.0.0.1:8000/',
           'http://screen.localhost/', 'ftp://example.org/', 'https:///nohost')
    for url in own:
        assert _render_field('iframe', {'f': url}) == '', url
    other = _render_field('iframe', {'f': 'https://signage.example.org.evil.test/x'})
    assert 'sandbox="allow-scripts allow-same-origin' in other and 'referrerpolicy="no-referrer"' in other
