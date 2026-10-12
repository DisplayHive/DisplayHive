"""Which media files does anything still use (application/admin/media/usage.py)."""

import json
from datetime import datetime

from application.admin.media.usage import media_usage
from application.models import db
from application.models.content import ContentElement, Design, Media, SystemSetting


def _media(db_session, filename, folder='', tags=''):
    m = Media(filename=filename, folder_path=folder, tags=tags, created_at=datetime.now())
    db_session.add(m)
    db_session.commit()
    return m


def _element(db_session, title, bag):
    el = ContentElement(active=True, title=title, html='', duration=5, serialized_input=json.dumps(bag))
    db_session.add(el)
    db_session.commit()
    return el


def test_unused_file_has_no_usage(db_session):
    m = _media(db_session, 'lonely.png')
    assert media_usage(db, [m]) == {}


def test_content_value_with_url_uses_the_file(db_session):
    m = _media(db_session, 'a.png', folder='sub')
    el = _element(db_session, 'Welcome', {'img': '/static/media/sub/a.png'})
    assert media_usage(db, [m]) == {m.id: [{'kind': 'content', 'id': el.id, 'name': 'Welcome'}]}


def test_absolute_and_encoded_urls_match(db_session):
    m = _media(db_session, 'my pic.png')
    _element(db_session, 'x', {'img': 'https://example.org/static/media/my%20pic.png'})
    assert list(media_usage(db, [m])) == [m.id]


def test_similar_name_is_not_a_match(db_session):
    m = _media(db_session, 'a.png')
    _element(db_session, 'x', {'img': '/static/media/aa.png', 'p': '/static/media_previews/a_preview.jpg'})
    assert media_usage(db, [m]) == {}


def test_random_tag_field_uses_every_file_with_the_tag(db_session):
    tagged = _media(db_session, 't.png', tags='logo, summer')
    other = _media(db_session, 'o.png', tags='winter')
    _element(db_session, 'Rand', {'pic__image_mode': 'random_tags', 'pic__image_tags': ['summer']})
    assert list(media_usage(db, [tagged, other])) == [tagged.id]


def test_tags_without_random_mode_do_not_count(db_session):
    m = _media(db_session, 't.png', tags='summer')
    _element(db_session, 'Fixed', {'pic__image_mode': 'single', 'pic__image_tags': ['summer']})
    assert media_usage(db, [m]) == {}


def test_design_backdrop_and_setting_use_the_file(db_session):
    m = _media(db_session, 'bg.jpg')
    design = Design(name='D', html='', background_image_url='/static/media/bg.jpg')
    db_session.add(design)
    db_session.add(SystemSetting(key='logo', value='/static/media/bg.jpg'))
    db_session.commit()
    kinds = sorted(o['kind'] for o in media_usage(db, [m])[m.id])
    assert kinds == ['design', 'setting']


def test_owner_is_named_by_its_title(db_session):
    m = _media(db_session, 'listed.png')
    _element(db_session, 'Uses', {'img': '/static/media/listed.png'})
    assert [o['name'] for o in media_usage(db, [m])[m.id]] == ['Uses']
