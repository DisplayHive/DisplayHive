"""The content list the Dashboard reads: schedule, assignment and last-change time."""

import json
from datetime import datetime

from application.admin.content.queries import emit_all_content_element
from application.models import Screengroup, db
from application.models.content import ContentElement


class _Capture:
    def emit(self, event, payload, room=None):
        self.payload = payload


def _listing():
    capture = _Capture()
    emit_all_content_element(capture, db, room='x')
    return {c['title']: c for c in capture.payload['content']}


def test_listing_carries_schedule_assignment_and_updated_at(db_session):
    group = Screengroup(name='dash-group')
    scheduled = ContentElement(
        active=True, title='dash-scheduled', html='', duration=5, serialized_input=json.dumps({}),
        start_time=datetime(2026, 10, 1, 8, 0), end_time=datetime(2026, 10, 20, 18, 30),
    )
    scheduled.screengroups.append(group)
    plain = ContentElement(active=True, title='dash-plain', html='', duration=5, serialized_input='{}')
    db_session.add_all([group, scheduled, plain])
    db_session.commit()

    listing = _listing()
    assert listing['dash-scheduled']['start_time'] == '2026-10-01T08:00'
    assert listing['dash-scheduled']['end_time'] == '2026-10-20T18:30'
    assert listing['dash-scheduled']['assigned'] is True
    assert listing['dash-plain']['end_time'] is None
    assert listing['dash-plain']['assigned'] is False
    assert listing['dash-plain']['updated_at'].endswith('Z')


def test_updated_at_moves_when_the_row_is_written(db_session):
    el = ContentElement(active=True, title='dash-touch', html='', duration=5, serialized_input='{}')
    db_session.add(el)
    db_session.commit()
    first = el.updated_at
    el.updated_at = datetime(2000, 1, 1)  # pretend it was written long ago
    db_session.commit()
    el.title = 'dash-touched'
    db_session.commit()
    assert first is not None
    assert el.updated_at > datetime(2000, 1, 2)


# --- The detailed list the Content page reads ---------------------------------------------------

def test_the_design_is_sent_once_and_the_base_ratio_once(flask_app, db_session):
    from application.admin.content.serializers import build_content_dict
    from application.models import Contenttype, ContentElement, Layout
    layout = Layout(name='dl-layout')
    contenttype = Contenttype(name='dl-ct', layout=layout)
    element = ContentElement(active=True, title='dl-el', html='{}', duration=5, serialized_input='{}', contenttype=contenttype)
    db_session.add_all([layout, contenttype, element])
    db_session.commit()
    row = build_content_dict(element, db=db)
    assert 'design' not in row                       # sent once with the list, not in every row
    assert '16:9' not in row['containers_by_ratio']  # the base is `containers`


def test_a_container_default_is_rendered_once_for_a_whole_list(flask_app, db_session, monkeypatch):
    from application.admin.content import scene
    calls = []
    monkeypatch.setattr(scene, 'render_container_default', lambda c, db=None: calls.append(c.id) or '<p>default</p>')
    container = type('C', (), {'id': 7, 'default_field_handler': 'textklein', 'default_content': 'x', 'show_when_empty': False})()
    monkeypatch.setattr('application.admin.layouts.helper.container_geometry', lambda c, ratio: {'top': 0, 'left': 0, 'width': 1, 'height': 1})
    cache = {}
    for _ in range(3):
        scene.combine_layout_containers([container], {}, defaults=cache)
    assert calls == [7]
