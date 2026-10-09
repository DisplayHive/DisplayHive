"""The Superadmin's switch for private networks, and what it guards: Pretalx URLs."""

import pytest

from application import net
from application.auth import create_token
from application.models import PretalxApiUrl, SystemSetting

GET = 'displayhive:admin:cts:get_outbound_policy'
SET = 'displayhive:admin:cts:set_outbound_policy'
GENERIC = 'displayhive:admin:cts:set_system_settings'
ADD_URL = 'displayhive:admin:pretalx:cts:add_url'


def _client(flask_app, user):
    client = flask_app.socketio.test_client(flask_app.app, auth={'token': create_token(flask_app.app, user)})
    assert client.is_connected()
    client.get_received()
    return client


def _call(client, event, data=None):
    return client.emit(event, data or {}, callback=True)


@pytest.fixture(autouse=True)
def clean_policy(monkeypatch):
    monkeypatch.delenv('OUTBOUND_ALLOW_PRIVATE', raising=False)
    net.invalidate()
    yield
    net.invalidate()


@pytest.fixture()
def superadmin(flask_app, db_session, make_user, make_group):
    from application.models import UserGroup
    user = make_user()
    group = make_group(is_superadmin=True)
    db_session.add(UserGroup(user_id=user.id, group_id=group.id))
    db_session.commit()
    client = _client(flask_app, user)
    yield client
    client.disconnect()


@pytest.fixture()
def settings_editor(flask_app, db_session, make_user, make_group):
    """Not a Superadmin, but allowed to edit settings and manage Pretalx."""
    from sqlalchemy import select
    from application.models import GroupRight, RightDefinition, UserGroup
    user = make_user()
    group = make_group()
    db_session.add(UserGroup(user_id=user.id, group_id=group.id))
    for key in ('settings.page', 'settings.edit', 'pretalx.manage', 'pretalx.page'):
        right = db_session.execute(select(RightDefinition).where(RightDefinition.key == key)).scalar_one()
        db_session.add(GroupRight(group_id=group.id, right_id=right.id))
    db_session.commit()
    client = _client(flask_app, user)
    yield client
    client.disconnect()


def test_private_networks_are_blocked_until_a_superadmin_allows_them(superadmin):
    assert _call(superadmin, GET) == {'success': True, 'allow_private': False, 'forced_by_env': False}

    allowed = _call(superadmin, SET, {'allow_private': True})
    assert allowed['allow_private'] is True and net.private_allowed() is True

    blocked = _call(superadmin, SET, {'allow_private': False})
    assert blocked['allow_private'] is False and net.private_allowed() is False


def test_only_a_superadmin_can_change_it(settings_editor, db_session):
    assert _call(settings_editor, GET)['allow_private'] is False          # may look
    refused = _call(settings_editor, SET, {'allow_private': True})
    assert refused == {'success': False, 'error': 'Only a Superadmin can change this.'}
    assert net.private_allowed() is False
    assert db_session.query(SystemSetting).filter_by(key=net.SETTING_KEY).count() == 0


def test_the_generic_settings_endpoint_cannot_set_it(settings_editor, db_session):
    result = _call(settings_editor, GENERIC, {'settings': {net.SETTING_KEY: 'true'}})
    assert result['success'] is False and 'Unknown setting' in result['error']
    assert net.private_allowed() is False


def test_it_is_not_part_of_an_export_or_import():
    from application.admin.importexport.helper import _exportable_setting_keys
    assert net.SETTING_KEY not in _exportable_setting_keys()


def test_the_environment_switch_is_reported_as_forcing_it(superadmin, monkeypatch):
    monkeypatch.setenv('OUTBOUND_ALLOW_PRIVATE', '1')
    assert _call(superadmin, GET) == {'success': True, 'allow_private': True, 'forced_by_env': True}


def test_a_pretalx_address_in_a_private_network_is_not_saved(superadmin, db_session):
    result = _call(superadmin, ADD_URL, {'name': 'Internal', 'url': 'http://127.0.0.1:9/api/events/x/'})
    assert result['ok'] is False and '127.0.0.1' in result['error'] and 'private' in result['error']
    assert db_session.query(PretalxApiUrl).count() == 0


def test_once_allowed_the_address_is_saved_even_if_nothing_answers_yet(superadmin, db_session):
    _call(superadmin, SET, {'allow_private': True})
    result = _call(superadmin, ADD_URL, {'name': 'Internal', 'url': 'http://127.0.0.1:9/api/events/x/'})   # port 9: nobody listens
    assert result['ok'] is True and result['is_valid'] is False
    assert db_session.query(PretalxApiUrl).count() == 1
