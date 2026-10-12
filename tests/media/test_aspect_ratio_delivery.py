"""End to end (DB level): a screen is sent the Layout variation that best
matches its aspect ratio, with that ratio's own container membership and
positions."""

from datetime import datetime, timezone

from application.models import (
    ContainerPosition, ContentContainer, ContentElement, Contenttype, Layout,
    LayoutVariation, Screen, Screengroup, TagConfig,
)
from application.socketio_handlers.upd_content import _build_payload


def _setup(db_session, screen_ratio):
    a = ContentContainer(name='a', top=0, left=0, width=50, height=50, show_when_empty=True)
    b = ContentContainer(name='b', top=50, left=50, width=50, height=50, show_when_empty=True)
    db_session.add_all([a, b])
    db_session.flush()

    layout = Layout(name='L')
    layout.contentcontainers = [a, b]
    db_session.add(layout)
    db_session.flush()

    # 4:3 variation: only container `b`, at its own position
    variation = LayoutVariation(layout_id=layout.id, aspect_ratio='4:3')
    variation.contentcontainers = [b]
    db_session.add(variation)
    db_session.add(ContainerPosition(contentcontainer_id=b.id, aspect_ratio='4:3', top=1, left=2, width=30, height=40))

    ct = Contenttype(name='T', layout_id=layout.id)
    db_session.add(ct)
    db_session.flush()
    db_session.add(TagConfig(contenttype_id=ct.id, contentcontainer_id=b.id, field_name='f', field_handler='textklein'))

    ce = ContentElement(
        active=True, title='x', html='{}', duration=5, serialized_input='{}', contenttype_id=ct.id,
    )
    sg = Screengroup(name='g')
    screen = Screen(active=True, lastseen=datetime.now(timezone.utc), name='s', aspect_ratio=screen_ratio)
    sg.screens.append(screen)
    ce.screengroups.append(sg)
    db_session.add_all([ce, sg, screen])
    db_session.flush()
    return a, b, screen


def _containers(payload):
    assert len(payload['scenes']) == 1
    return payload['scenes'][0]['containers']


def test_base_screen_gets_base_membership_and_positions(flask_app, db_session):
    a, b, screen = _setup(db_session, '16:9')
    containers = _containers(_build_payload(flask_app.db, screen))
    assert set(containers) == {str(a.id), str(b.id)}
    assert containers[str(b.id)]['top'] == 50


def test_4_3_screen_gets_variation_membership_and_own_position(flask_app, db_session):
    a, b, screen = _setup(db_session, '4:3')
    containers = _containers(_build_payload(flask_app.db, screen))
    assert set(containers) == {str(b.id)}
    assert (containers[str(b.id)]['top'], containers[str(b.id)]['left']) == (1, 2)
    assert containers[str(b.id)]['width'] == 30


def test_unmatched_ratio_falls_back_to_closest_variant(flask_app, db_session):
    # 16:10 is closer to 16:9 than to 4:3 -> base variant
    a, b, screen = _setup(db_session, '16:10')
    assert set(_containers(_build_payload(flask_app.db, screen))) == {str(a.id), str(b.id)}
    # 5:4 is closer to 4:3 than to 16:9 -> 4:3 variant
    screen.aspect_ratio = '5:4'
    db_session.flush()
    assert set(_containers(_build_payload(flask_app.db, screen))) == {str(b.id)}
