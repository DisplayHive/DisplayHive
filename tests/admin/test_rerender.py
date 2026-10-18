"""Content is stored rendered; what its rendering depends on besides its own values renders it again when it changes
(application/admin/content/rerender.py)."""

import json

import pytest

from application.admin.content import rerender
from application.models import ContentContainer, ContentElement, Contenttype, Design, Layout, TagConfig
from application.plugins.registry import registry


def test_the_handlers_say_what_they_depend_on(flask_app):
    assert registry.handlers_depending_on('design') == ['icon']
    assert registry.handlers_depending_on('media') == ['image']
    assert registry.handlers_depending_on('nothing') == []


@pytest.fixture()
def content(db_session):
    """An icon field (its colour is a palette reference), an image field and a text field, each in a content type of its own."""
    layout = Layout(name='rr-layout')
    container = ContentContainer(name='rr-container', order=1)
    db_session.add_all([layout, container])
    db_session.flush()
    made = {}
    for handler, values in (('icon', {'f': 'lucide/home', 'f__color': '@default:c1'}), ('image', {'f': '/static/media/a.png'}),
                            ('textklein', {'f': 'plain'})):
        ct = Contenttype(name=f'rr-{handler}', layout_id=layout.id)
        db_session.add(ct)
        db_session.flush()
        db_session.add(TagConfig(contenttype_id=ct.id, field_name='f', field_handler=handler, contentcontainer_id=container.id, order=0))
        element = ContentElement(title=f'rr-{handler}', html='STALE', duration=5, active=True,
                                 serialized_input=json.dumps(values), contenttype_id=ct.id)
        db_session.add(element)
        made[handler] = element
    db_session.commit()
    return made


def test_only_the_content_types_that_use_such_a_handler_are_rendered_again(flask_app, db_session, content, monkeypatch):
    sent = []
    monkeypatch.setattr('application.socketio_handlers.upd_content.send_upd_content', lambda sio, db, content_ids=None: sent.append(sorted(content_ids)))
    mine = {content['icon'].contenttype_id, content['image'].contenttype_id, content['textklein'].contenttype_id}
    assert set(rerender.contenttypes_depending_on(flask_app.db, {'design'})) & mine == {content['icon'].contenttype_id}
    assert set(rerender.contenttypes_depending_on(flask_app.db, {'media'})) & mine == {content['image'].contenttype_id}
    assert set(rerender.contenttypes_depending_on(flask_app.db, {'design', 'media'})) & mine == {content['icon'].contenttype_id, content['image'].contenttype_id}
    assert mine <= set(rerender.contenttypes_depending_on(flask_app.db, {rerender.ALL}))

    assert rerender.rerender_now(None, flask_app.db, {'design'}) >= 1
    db_session.refresh(content['icon'])
    db_session.refresh(content['textklein'])
    assert content['icon'].html != 'STALE'
    assert content['textklein'].html == 'STALE'             # does not depend on the Design: left alone
    assert content['icon'].id in sent[-1]


def test_a_palette_change_reaches_the_stored_icon_colour(flask_app, db_session, content, monkeypatch):
    monkeypatch.setattr('application.socketio_handlers.upd_content.send_upd_content', lambda *a, **k: None)
    design = db_session.query(Design).filter_by(isDefault=True).first() or Design(name='rr-design', html='', css='', isDefault=True)
    db_session.add(design)
    design.default_colors = json.dumps([{'id': 'c1', 'name': 'Brand', 'hex': '#ff0000'}])
    db_session.commit()
    rerender.rerender_now(None, flask_app.db, {'design'})
    db_session.refresh(content['icon'])
    assert '#ff0000' in content['icon'].html
    design.default_colors = json.dumps([{'id': 'c1', 'name': 'Brand', 'hex': '#00ff00'}])
    db_session.commit()
    rerender.rerender_now(None, flask_app.db, {'design'})
    db_session.refresh(content['icon'])
    assert '#00ff00' in content['icon'].html and '#ff0000' not in content['icon'].html


def test_a_burst_of_changes_is_one_run(flask_app, monkeypatch):
    runs, tasks = [], []

    class Socket:
        def sleep(self, seconds):
            pass

        def start_background_task(self, fn):
            tasks.append(fn)

    from application.plugins import host
    monkeypatch.setattr(host, 'socketio', lambda: Socket())
    monkeypatch.setattr(rerender, 'rerender_now', lambda sio, db, kinds: runs.append(set(kinds)) or 0)
    monkeypatch.setattr(rerender, '_running', False)
    monkeypatch.setattr(rerender, '_pending', set())
    for _ in range(5):
        rerender.schedule('media')
    rerender.schedule('design')
    assert len(tasks) == 1                                 # one worker, however many changes
    tasks[0]()
    assert runs == [{'media', 'design'}]
    assert rerender._running is False


# --- What sets it off ---------------------------------------------------------------------------

@pytest.fixture()
def admin(flask_app, db_session, make_user, make_group):
    from application.models import UserGroup
    from application.security.auth import create_token
    user = make_user()
    group = make_group(is_superadmin=True)
    db_session.add(UserGroup(user_id=user.id, group_id=group.id))
    db_session.commit()
    client = flask_app.socketio.test_client(flask_app.app, auth={'token': create_token(flask_app.app, user)})
    client.get_received()
    yield client
    client.disconnect()


@pytest.fixture()
def scheduled(monkeypatch):
    calls = []
    monkeypatch.setattr(rerender, 'schedule', lambda kind: calls.append(kind))
    return calls


def test_saving_the_default_design_and_making_one_the_default_schedule_a_run(flask_app, db_session, admin, scheduled):
    first = Design(name='rr-a', html='', css='', isDefault=True)
    second = Design(name='rr-b', html='', css='', isDefault=False)
    db_session.add_all([first, second])
    db_session.commit()
    assert admin.emit('displayhive:admin:cts:update_design', {'id': second.id, 'name': 'rr-b2'}, callback=True)['success']
    assert scheduled == []                                                 # not the active Design: no palette in use
    assert admin.emit('displayhive:admin:cts:update_design', {'id': first.id, 'default_colors': '[]'}, callback=True)['success']
    assert scheduled == ['design']
    assert admin.emit('displayhive:admin:cts:set_default_design', {'id': second.id}, callback=True)['success']
    assert scheduled == ['design', 'design']


def test_changing_or_deleting_media_schedules_a_run(flask_app, db_session, admin, scheduled, tmp_path):
    from datetime import datetime
    from application.models import Media
    media = Media(title='m', filename='rr-missing.png', folder_path='', mime_type='image/png', tags='a', created_at=datetime(2026, 1, 1))
    db_session.add(media)
    db_session.commit()
    assert admin.emit('displayhive:media:cts:update_media', {'id': media.id, 'title': 'only the title'}, callback=True)['success']
    assert scheduled == []                                                 # the title is not what a pool is made from
    assert admin.emit('displayhive:media:cts:update_media', {'id': media.id, 'tags': ['b']}, callback=True)['success']
    assert scheduled == ['media']
    admin.emit('displayhive:media:cts:delete_media', {'id': media.id})
    assert scheduled == ['media', 'media']


def test_an_import_renders_everything_again(flask_app, scheduled):
    from application.admin.importexport.service import _finish_import
    sio = type('S', (), {'emit': lambda *a, **k: None})()
    _finish_import({'success': False}, app=flask_app.app, db=flask_app.db, socketio=sio, media_folder='', renditions_folder='')
    assert scheduled == []                                                 # a failed import changed nothing
