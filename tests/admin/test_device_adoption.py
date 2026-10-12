"""Device adoption and screen authentication on connect:
application/admin/devices/management.py (approve_registration) and
application/admin/devices/connection.py (adoptionkey / devicekey handshake)."""

import uuid

import pytest

from application.auth import create_token

APPROVE = 'displayhive:devices:cts:approve_registration'
APPROVED = 'displayhive:devices:stc:registration_approved'
ADOPTION_APPROVED = 'displayhive:devices:stc:adoption_approved'
AUTHENTICATED = 'displayhive:devices:stc:device_authenticated'
REJECTED = 'displayhive:devices:stc:connection_rejected'


def _events(client, name):
    return [m['args'][0] for m in client.get_received() if m['name'] == name]


def _screen_client(flask_app, **query):
    qs = '&'.join(f'{k}={v}' for k, v in query.items())
    return flask_app.socketio.test_client(flask_app.app, query_string=qs)


@pytest.fixture()
def admin_client(flask_app, db_session, make_user, make_group):
    """A connected Socket.IO admin session in a superadmin group."""
    from application.models import UserGroup
    user = make_user()
    group = make_group(is_superadmin=True)
    db_session.add(UserGroup(user_id=user.id, group_id=group.id))
    db_session.commit()
    token = create_token(flask_app.app, user)
    client = flask_app.socketio.test_client(flask_app.app, auth={'token': token})
    assert client.is_connected()
    client.get_received()
    yield client
    client.disconnect()


@pytest.fixture()
def unprivileged_admin_client(flask_app, db_session, make_user):
    """A connected admin session without any group, i.e. without device.adopt."""
    client = flask_app.socketio.test_client(flask_app.app, auth={'token': create_token(flask_app.app, make_user())})
    assert client.is_connected()
    client.get_received()
    yield client
    client.disconnect()


def _device(db_session, token):
    from application.models import Device
    db_session.expire_all()
    return db_session.execute(db_session.query(Device).filter_by(registration_token=token).statement).scalar_one_or_none()


# --- Admin approves a registration token ----------------------------------------------

def test_approve_creates_an_active_device_with_a_devicekey(db_session, admin_client):
    token = str(uuid.uuid4())
    admin_client.emit(APPROVE, {'token': token, 'device_name': 'lobby'})

    reply = _events(admin_client, APPROVED)
    assert reply and reply[0]['success'] is True and reply[0]['devicekey']
    dev = _device(db_session, token)
    assert dev.devicekey == reply[0]['devicekey']
    assert dev.name == 'lobby' and dev.is_active is True and dev.screen_id is None


def test_approving_the_same_token_twice_returns_the_same_device(db_session, admin_client):
    token = str(uuid.uuid4())
    admin_client.emit(APPROVE, {'token': token})
    first = _events(admin_client, APPROVED)[0]['devicekey']
    admin_client.emit(APPROVE, {'token': token})
    second = _events(admin_client, APPROVED)[0]['devicekey']

    assert first == second
    from application.models import Device
    assert db_session.query(Device).filter_by(registration_token=token).count() == 1


def test_approve_without_a_token_is_rejected(db_session, admin_client):
    admin_client.emit(APPROVE, {})
    reply = _events(admin_client, APPROVED)
    assert reply and reply[0]['success'] is False


def test_approve_requires_the_device_adopt_right(db_session, unprivileged_admin_client):
    token = str(uuid.uuid4())
    unprivileged_admin_client.emit(APPROVE, {'token': token})
    assert _device(db_session, token) is None


# --- The screen adopts itself ------------------------------------------------------------

def test_adoptionkey_of_an_approved_device_returns_its_devicekey(flask_app, db_session, admin_client):
    token = str(uuid.uuid4())
    admin_client.emit(APPROVE, {'token': token})
    devicekey = _events(admin_client, APPROVED)[0]['devicekey']

    screen = _screen_client(flask_app, adoptionkey=token)
    assert screen.is_connected()
    received = _events(screen, ADOPTION_APPROVED)
    assert received == [{'success': True, 'devicekey': devicekey}]
    screen.disconnect()


def test_unknown_adoptionkey_is_refused(flask_app, db_session):
    screen = _screen_client(flask_app, adoptionkey=str(uuid.uuid4()))
    assert not screen.is_connected()


def test_first_devicekey_connect_authenticates_and_consumes_the_registration_token(flask_app, db_session, admin_client):
    token = str(uuid.uuid4())
    admin_client.emit(APPROVE, {'token': token})
    devicekey = _events(admin_client, APPROVED)[0]['devicekey']

    screen = _screen_client(flask_app, devicekey=devicekey)
    assert screen.is_connected()
    assert _events(screen, AUTHENTICATED)[0]['success'] is True

    from application.models import Device
    db_session.expire_all()
    dev = db_session.query(Device).filter_by(devicekey=devicekey).one()
    assert dev.is_online is True and dev.registration_token is None
    screen.disconnect()

    # The adoption key is single-use: it no longer opens anything.
    again = _screen_client(flask_app, adoptionkey=token)
    assert not again.is_connected()


# --- Screen authentication on later connects -------------------------------------------

def test_unknown_devicekey_is_refused(flask_app, db_session):
    assert not _screen_client(flask_app, devicekey=str(uuid.uuid4())).is_connected()


def test_connection_without_any_key_is_refused(flask_app, db_session):
    assert not flask_app.socketio.test_client(flask_app.app).is_connected()


def test_deactivated_device_is_told_why_and_is_not_marked_online(flask_app, db_session):
    from application.models import Device
    dev = Device(devicekey=str(uuid.uuid4()), name='off', is_active=False)
    db_session.add(dev)
    db_session.commit()

    screen = _screen_client(flask_app, devicekey=dev.devicekey)
    received = _events(screen, REJECTED)
    assert received and received[0]['reason'] == 'device_inactive'
    assert not _events(screen, AUTHENTICATED)
    db_session.expire_all()
    assert db_session.get(Device, dev.id).is_online is False
