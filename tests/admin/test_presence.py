"""Device presence (Device.is_online + the in-memory connection registry)
across connects, reconnects and disconnects — application/admin/devices/
connection.py and application/socketio_handlers/lifecycle.py."""

import uuid

import pytest
from sqlalchemy import event


@pytest.fixture()
def device(db_session):
    from application.models import Device
    dev = Device(devicekey=str(uuid.uuid4()), name='lobby', is_active=True)
    db_session.add(dev)
    db_session.commit()
    return dev


def _connect(flask_app, devicekey):
    client = flask_app.socketio.test_client(flask_app.app, query_string=f'devicekey={devicekey}')
    assert client.is_connected()
    return client


def _online(db_session, device):
    db_session.expire_all()
    return db_session.get(type(device), device.id).is_online


def test_online_and_offline_are_written_while_holding_the_registry_lock(flask_app, db_session, device):
    """The fix for "reconnected screen shows offline": the connect handler's
    is_online=True and the disconnect handler's is_online=False must each
    happen together with their registry change, under registry_lock — so an
    old socket's disconnect can't land between a reconnect's two steps."""
    from application.models import Device
    from application.socketio_handlers.lifecycle import registry_lock

    writes = []

    def record(target, value, oldvalue, initiator):
        if target.devicekey == device.devicekey:
            writes.append((value, registry_lock._is_owned()))

    event.listen(Device.is_online, 'set', record)
    try:
        client = _connect(flask_app, device.devicekey)
        client.disconnect()
    finally:
        event.remove(Device.is_online, 'set', record)

    assert (True, True) in writes
    assert (False, True) in writes
    assert all(held for _, held in writes)


def test_disconnect_of_a_replaced_socket_keeps_the_device_online(flask_app, db_session, device):
    from application.socketio_handlers.lifecycle import connected_devices

    old = _connect(flask_app, device.devicekey)
    new = _connect(flask_app, device.devicekey)
    new_sid = connected_devices[device.devicekey]['sid']

    old.disconnect()  # the old socket's teardown arrives after the reconnect
    assert _online(db_session, device) is True
    assert connected_devices[device.devicekey]['sid'] == new_sid

    new.disconnect()
    assert _online(db_session, device) is False
    assert device.devicekey not in connected_devices


def test_plain_connect_and_disconnect(flask_app, db_session, device):
    from application.socketio_handlers.lifecycle import connected_devices

    client = _connect(flask_app, device.devicekey)
    assert _online(db_session, device) is True
    assert device.devicekey in connected_devices
    client.disconnect()
    assert _online(db_session, device) is False
