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
