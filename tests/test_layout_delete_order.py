"""Deleting a layout and then its (now unused) container, the way the admin does one after the other
(an earlier E2E run saw a StaleDataError on the second step once)."""

import pytest

from tests.test_admin_actions import superadmin_client  # noqa: F401  (fixture)

CREATE_CONTAINER = 'displayhive:admin:cts:create_container'
CREATE_LAYOUT = 'displayhive:admin:cts:create_layout'
DELETE_LAYOUT = 'displayhive:admin:cts:delete_layout'
DELETE_CONTAINER = 'displayhive:admin:cts:delete_container'
UPDATE_LAYOUT = 'displayhive:admin:cts:update_layout'


def _ack(client, event, data=None):
    return client.emit(event, data, callback=True)


def _make(client, containers=2):
    ids = []
    for n in range(containers):
        ack = _ack(client, CREATE_CONTAINER, {'name': f'ldo-{n}', 'top': 0, 'left': n * 10, 'width': 10, 'height': 10})
        assert ack['success'], ack
        ids.append(ack['id'])
    layout = _ack(client, CREATE_LAYOUT, {'name': 'ldo-layout', 'container_ids': ids})
    assert layout['success'], layout
    return layout['id'], ids


def test_delete_layout_then_its_containers_one_by_one(superadmin_client):
    layout_id, container_ids = _make(superadmin_client)
    assert _ack(superadmin_client, DELETE_LAYOUT, {'id': layout_id})['success']
    for cid in container_ids:
        ack = _ack(superadmin_client, DELETE_CONTAINER, {'id': cid})
        assert ack['success'], ack


def test_delete_a_container_that_is_still_in_a_layout_then_the_layout(superadmin_client):
    layout_id, container_ids = _make(superadmin_client)
    ack = _ack(superadmin_client, DELETE_CONTAINER, {'id': container_ids[0]})
    assert ack['success'], ack
    assert _ack(superadmin_client, DELETE_LAYOUT, {'id': layout_id})['success']
    ack = _ack(superadmin_client, DELETE_CONTAINER, {'id': container_ids[1]})
    assert ack['success'], ack
