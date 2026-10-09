"""The shared acknowledgement helpers for admin socket handlers
(application/socketio_handlers/actions.py), and the handlers converted to them:
users, screengroups membership, settings."""

from datetime import datetime, timezone

import pytest

from application.auth import create_token

CREATE_USER = 'displayhive:admin:users:cts:create_user'
DELETE_USER = 'displayhive:admin:users:cts:delete_user'
SET_ACTIVE = 'displayhive:admin:users:cts:set_active'
ADD_SCREEN = 'displayhive:admin:cts:add_screen_to_screengroup'
SET_SETTINGS = 'displayhive:admin:cts:set_system_settings'
SET_DEFAULT_DESIGN = 'displayhive:admin:cts:set_default_design'


@pytest.fixture()
def superadmin_client(flask_app, db_session, make_user, make_group):
    from application.models import UserGroup
    user = make_user()
    group = make_group(is_superadmin=True)
    db_session.add(UserGroup(user_id=user.id, group_id=group.id))
    db_session.commit()
    client = flask_app.socketio.test_client(flask_app.app, auth={'token': create_token(flask_app.app, user)})
    assert client.is_connected()
    client.get_received()
    yield client
    client.disconnect()


@pytest.fixture()
def plain_client(flask_app, db_session, make_user):
    """An authenticated admin without any group, so without any right."""
    client = flask_app.socketio.test_client(flask_app.app, auth={'token': create_token(flask_app.app, make_user())})
    assert client.is_connected()
    client.get_received()
    yield client
    client.disconnect()


def _ack(client, event, data=None):
    return client.emit(event, data, callback=True)


# --- the helpers on their own -----------------------------------------------------------

def test_get_or_fail_distinguishes_missing_id_from_missing_row(db_session, make_user):
    from application.models import AdminUser, db
    from application.socketio_handlers.actions import Fail, get_or_fail
    user = make_user()
    assert get_or_fail(db, AdminUser, user.id, 'User').id == user.id
    with pytest.raises(Fail, match='Missing id'):
        get_or_fail(db, AdminUser, None, 'User')
    with pytest.raises(Fail, match='User not found'):
        get_or_fail(db, AdminUser, 10_000_000, 'User')
    with pytest.raises(Fail, match='User not found'):
        get_or_fail(db, AdminUser, 'not-an-id', 'User')


def test_a_fail_rolls_back_what_the_handler_wrote_before_it(flask_app, db_session):
    from application.models import SystemSetting, db
    from application.socketio_handlers import actions

    @actions.admin_action()
    def handler():
        db.session.add(SystemSetting(key='actions-rollback', value='1'))
        db.session.flush()
        raise actions.Fail('nope')

    # require_admin() needs a socket; stub it so the decorator's own logic is what runs.
    original = actions.require_admin
    actions.require_admin = lambda: True
    try:
        assert handler() == {'success': False, 'error': 'nope'}
    finally:
        actions.require_admin = original
    assert db.session.execute(db.select(SystemSetting).where(SystemSetting.key == 'actions-rollback')).first() is None


def test_an_unexpected_error_is_answered_not_swallowed(flask_app, db_session):
    from application.socketio_handlers import actions

    @actions.admin_action()
    def handler():
        raise RuntimeError('boom')

    original = actions.require_admin
    actions.require_admin = lambda: True
    try:
        assert handler() == {'success': False, 'error': 'Internal error'}
    finally:
        actions.require_admin = original


def test_an_unauthenticated_socket_gets_no_answer(flask_app):
    from application.socketio_handlers import actions

    @actions.admin_action('users.page')
    def handler():
        return actions.ok()

    assert handler() is None  # no socket / room: not an admin


# --- users --------------------------------------------------------------------------------

def test_create_user_and_the_duplicate_error(superadmin_client):
    first = _ack(superadmin_client, CREATE_USER, {'username': 'newbie', 'password': 'Correct-Horse-9!'})
    assert first['success'] is True and first['id']
    again = _ack(superadmin_client, CREATE_USER, {'username': 'newbie', 'password': 'Correct-Horse-9!'})
    assert again == {'success': False, 'error': 'Username already exists'}


def test_create_user_validates_input(superadmin_client):
    assert _ack(superadmin_client, CREATE_USER, {'username': '  ', 'password': 'x'})['error'] == 'Username is required'
    assert _ack(superadmin_client, CREATE_USER, None)['success'] is False


def test_an_admin_without_the_right_is_told_so(plain_client):
    assert _ack(plain_client, CREATE_USER, {'username': 'x', 'password': 'Correct-Horse-9!'}) == {
        'success': False, 'error': 'Permission denied'}


def test_delete_user_reports_missing_and_unknown_ids(superadmin_client):
    assert _ack(superadmin_client, DELETE_USER, {})['error'] == 'Missing id'
    assert _ack(superadmin_client, DELETE_USER, {'id': 10_000_000})['error'] == 'User not found'


def test_the_last_active_admin_cannot_be_deactivated(superadmin_client, db_session):
    from application.models import AdminUser
    only = db_session.execute(db_session.query(AdminUser).statement).scalars().all()
    # Other tests leave users behind; keep exactly the caller active so "last" is true.
    for user in only:
        user.is_active = False
    caller = [u for u in only if u.username][-1]
    caller.is_active = True
    db_session.commit()
    result = _ack(superadmin_client, SET_ACTIVE, {'id': caller.id, 'is_active': False})
    assert result['success'] is False


# --- screengroup membership ---------------------------------------------------------------

def test_screengroup_membership_errors_come_back_as_acks(superadmin_client):
    assert _ack(superadmin_client, ADD_SCREEN, {})['error'] == 'missing screengroup_id'
    assert _ack(superadmin_client, ADD_SCREEN, {'screengroup_id': 1})['error'] == 'missing item id'
    assert _ack(superadmin_client, ADD_SCREEN, {'screengroup_id': 10_000_000, 'screen_id': 1})['error'] == 'screengroup not found'


def test_screengroup_membership_add_then_unknown_screen(superadmin_client, db_session):
    from application.models import Screen, Screengroup
    group = Screengroup(name='actions-group')
    screen = Screen(name='actions-screen', active=True, lastseen=datetime.now(timezone.utc))
    db_session.add_all([group, screen])
    db_session.commit()
    assert _ack(superadmin_client, ADD_SCREEN, {'screengroup_id': group.id, 'screen_id': screen.id}) == {'success': True}
    db_session.expire_all()
    assert screen in group.screens
    assert _ack(superadmin_client, ADD_SCREEN, {'screengroup_id': group.id, 'screen_id': 10_000_000})['error'] == 'item not found'


# --- settings -----------------------------------------------------------------------------

def test_unknown_setting_keys_are_refused_but_known_ones_saved(superadmin_client, db_session):
    from application.models import SystemSetting
    result = _ack(superadmin_client, SET_SETTINGS, {'settings': {'timezone': 'Europe/Berlin', 'telegram_token': 'x'}})
    assert result == {'success': False, 'error': 'Unknown setting(s): telegram_token'}
    db_session.expire_all()
    row = db_session.execute(db_session.query(SystemSetting).filter_by(key='timezone').statement).scalar_one()
    assert row.value == 'Europe/Berlin'


def test_settings_need_a_payload(superadmin_client):
    assert _ack(superadmin_client, SET_SETTINGS, {'settings': {}})['error'] == 'No settings provided'
    assert _ack(superadmin_client, SET_SETTINGS, None)['error'] == 'No settings provided'


def test_set_default_design_reports_an_unknown_design(superadmin_client):
    assert _ack(superadmin_client, SET_DEFAULT_DESIGN, {'id': 10_000_000})['error'] == 'Design not found'
    assert _ack(superadmin_client, SET_DEFAULT_DESIGN, {})['error'] == 'Missing id'


# --- screens, devices, rights, login providers, content, media ----------------------------

def test_screens_create_validates_and_rejects_duplicates(superadmin_client):
    create = 'displayhive:screens:cts:create_screen'
    assert _ack(superadmin_client, create, {'name': ' '})['error'] == 'name is required'
    first = _ack(superadmin_client, create, {'name': 'actions-lobby'})
    assert first['success'] is True and first['screen_id']
    assert _ack(superadmin_client, create, {'name': 'actions-lobby'})['error'] == 'Screen "actions-lobby" already exists'
    assert _ack(superadmin_client, 'displayhive:screens:cts:delete_screen', {'screen_id': first['screen_id']}) == {'success': True}
    assert _ack(superadmin_client, 'displayhive:screens:cts:delete_screen', {'screen_id': first['screen_id']})['error'] == 'Screen not found'
    assert _ack(superadmin_client, 'displayhive:screens:cts:toggle_monitoring', {})['error'] == 'Missing id'


def test_device_actions_report_unknown_devices(superadmin_client):
    for event, data in (
        ('displayhive:devices:cts:update_device', {'device_id': 10_000_000}),
        ('displayhive:devices:cts:assign_device_screen', {'device_id': 10_000_000}),
        ('displayhive:devices:cts:find_device', {'device_id': 10_000_000}),
    ):
        assert _ack(superadmin_client, event, data)['error'] == 'Device not found'
    assert _ack(superadmin_client, 'displayhive:devices:cts:update_device', None)['error'] == 'Missing id'
    assert _ack(superadmin_client, 'displayhive:devices:cts:delete_device', {})['error'] == 'Missing id'


def test_rights_handlers_answer_permission_denied_and_validation_errors(superadmin_client, plain_client):
    create_group = 'displayhive:admin:rights:cts:create_group'
    assert _ack(plain_client, create_group, {'name': 'x'}) == {'success': False, 'error': 'Permission denied'}
    assert _ack(superadmin_client, create_group, {'name': ''})['error'] == 'Group name is required'
    made = _ack(superadmin_client, create_group, {'name': 'actions-group-rights'})
    assert made['success'] is True and made['id']
    assert _ack(superadmin_client, create_group, {'name': 'actions-group-rights'})['error'] == 'A group with that name already exists'
    assert _ack(superadmin_client, 'displayhive:admin:rights:cts:delete_group', {'id': made['id']}) == {'success': True}
    assert _ack(superadmin_client, 'displayhive:admin:rights:cts:delete_group', {'id': made['id']})['error'] == 'Group not found'


def test_login_provider_validation(superadmin_client):
    save = 'displayhive:admin:authproviders:cts:save_provider'
    assert _ack(superadmin_client, save, {})['error'] == 'Name is required'
    assert _ack(superadmin_client, save, {'name': 'x', 'client_id': 'c', 'issuer': 'ftp://bad'})['error'].startswith('Issuer must')
    assert _ack(superadmin_client, 'displayhive:admin:authproviders:cts:delete_provider', {'id': 10_000_000})['error'] == 'Provider not found'


def test_content_and_media_actions_report_unknown_rows(superadmin_client):
    assert _ack(superadmin_client, 'displayhive:admin:cts:update_content_element_active', {})['error'] == 'Missing id'
    assert _ack(superadmin_client, 'displayhive:admin:cts:update_content_element_active', {'content_element_id': 10_000_000})['error'] == 'ContentElement not found'
    assert _ack(superadmin_client, 'displayhive:admin:cts:delete_content_element', {'content_element_id': 10_000_000})['error'] == 'ContentElement not found'
    assert _ack(superadmin_client, 'displayhive:admin:cts:create_content_element', {'id': 10_000_000, 'title': 't'})['error'] == 'Content not found'
    assert _ack(superadmin_client, 'displayhive:media:cts:update_media', {'id': 10_000_000})['error'] == 'Media not found'
    assert _ack(superadmin_client, 'displayhive:media:cts:delete_media', {})['error'] == 'Missing id'
