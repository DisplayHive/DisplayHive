"""Browser sessions in an HttpOnly cookie (application/session.py), next to Bearer tokens."""

import pytest

from application import oidc
from application.auth import create_token

PASSWORD = 'a-long-enough-password'
CSRF = {'X-DisplayHive-Request': '1'}


@pytest.fixture()
def user(make_user, db_session):
    return make_user(username='cookie-user', password=PASSWORD)


@pytest.fixture()
def client(flask_app):
    return flask_app.app.test_client()


def _login(client, username='cookie-user', headers=CSRF, **extra):
    return client.post('/admin/api/auth/login', json={'username': username, 'password': PASSWORD, 'session': 'cookie'},
                       headers=headers, **extra)


def _set_cookie_headers(response):
    return response.headers.getlist('Set-Cookie')


def _cookie_named(response, name):
    return next((h for h in _set_cookie_headers(response) if h.startswith(name + '=')), None)


# --- logging in -------------------------------------------------------------------------------


def test_cookie_login_sets_an_httponly_strict_cookie_and_keeps_the_token_out_of_the_body(client, user):
    response = _login(client)
    body = response.get_json()
    assert response.status_code == 200 and body['success'] is True
    assert 'token' not in body and body['expires_at'] and body['username'] == 'cookie-user'
    cookie = _cookie_named(response, 'dh_session')
    assert cookie and 'HttpOnly' in cookie and 'SameSite=Strict' in cookie and 'Path=/' in cookie
    assert 'Secure' not in cookie                                    # plain http (development)


def test_over_https_the_cookie_is_secure_and_host_prefixed(client, user):
    response = _login(client, base_url='https://admin.example.com')
    cookie = _cookie_named(response, '__Host-dh_session')
    assert cookie and 'Secure' in cookie and 'HttpOnly' in cookie and 'Path=/' in cookie and 'Domain' not in cookie


def test_the_public_url_makes_cookies_secure_even_behind_a_plain_http_proxy(flask_app, client, user, monkeypatch):
    monkeypatch.setitem(flask_app.app.config, 'PUBLIC_URL', 'https://signage.example.com')
    assert _cookie_named(_login(client), '__Host-dh_session')


def test_bearer_login_is_unchanged(client, user):
    response = client.post('/admin/api/auth/login', json={'username': 'cookie-user', 'password': PASSWORD})
    body = response.get_json()
    assert body['token'] and not _set_cookie_headers(response)


def test_the_cookie_session_works_for_get_and_post_with_the_csrf_header(client, user):
    _login(client)
    me = client.get('/admin/api/auth/me')
    assert me.status_code == 200 and me.get_json()['session'] == 'cookie' and me.get_json()['expires_at']
    ok = client.patch('/admin/api/auth/me/preferences', json={'preferences': {'theme': 'dark'}}, headers=CSRF)
    assert ok.status_code == 200


# --- cross-site request forgery -----------------------------------------------------------------


def test_a_cookie_session_cannot_change_anything_without_the_csrf_header(client, user):
    _login(client)
    response = client.patch('/admin/api/auth/me/preferences', json={'preferences': {'theme': 'dark'}})
    assert response.status_code == 403 and 'X-DisplayHive-Request' in response.get_json()['error']


def test_a_foreign_origin_is_refused_even_with_the_header(client, user):
    _login(client)
    response = client.patch('/admin/api/auth/me/preferences', json={'preferences': {'theme': 'dark'}},
                            headers={**CSRF, 'Origin': 'https://evil.example'})
    assert response.status_code == 403 and 'Cross-origin' in response.get_json()['error']


def test_our_own_origin_is_accepted(client, user):
    _login(client)
    response = client.patch('/admin/api/auth/me/preferences', json={'preferences': {'theme': 'dark'}},
                            headers={**CSRF, 'Origin': 'http://localhost'})        # the test client's host
    assert response.status_code == 200


def test_the_public_url_origin_is_accepted_and_a_wildcard_cors_setting_grants_nothing(flask_app, client, user, monkeypatch):
    monkeypatch.setitem(flask_app.app.config, 'PUBLIC_URL', 'https://signage.example.com')
    monkeypatch.setitem(flask_app.app.config, 'CORS_ORIGINS', '*')
    _login(client)
    send = lambda origin: client.patch('/admin/api/auth/me/preferences', json={'preferences': {'theme': 'dark'}},   # noqa: E731
                                       headers={**CSRF, 'Origin': origin})
    assert send('https://signage.example.com').status_code == 200
    assert send('https://anything.example').status_code == 403


def test_logging_in_with_a_cookie_is_protected_against_cross_site_forms_too(client, user):
    refused = _login(client, headers={})                                     # no header
    assert refused.status_code == 403 and not _set_cookie_headers(refused)
    foreign = _login(client, headers={**CSRF, 'Origin': 'https://evil.example'})
    assert foreign.status_code == 403 and not _set_cookie_headers(foreign)


def test_bearer_requests_need_no_csrf_header(client, flask_app, user):
    token = create_token(flask_app.app, user)
    response = client.patch('/admin/api/auth/me/preferences', json={'preferences': {'theme': 'dark'}},
                            headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 200


def test_an_invalid_cookie_is_unauthorized(client, user):
    client.set_cookie('dh_session', 'not-a-token')
    assert client.get('/admin/api/auth/me').status_code == 401


# --- logging out ----------------------------------------------------------------------------------


def test_logout_removes_the_cookies(client, user):
    _login(client)
    response = client.post('/admin/api/auth/logout')
    cleared = _set_cookie_headers(response)
    assert any(h.startswith('dh_session=;') or h.startswith('dh_session="";') or 'dh_session=;' in h for h in cleared)
    assert any(h.startswith('dh_original=') for h in cleared)
    assert client.get('/admin/api/auth/me').status_code == 401


# --- changing the password ------------------------------------------------------------------------


def test_changing_the_password_in_a_cookie_session_replaces_the_cookie_and_revokes_the_old_one(client, user):
    _login(client)
    old = client.get_cookie('dh_session').value
    response = client.post('/admin/api/auth/me/password', headers=CSRF,
                           json={'current_password': PASSWORD, 'new_password': 'another-long-password-1'})
    body = response.get_json()
    assert response.status_code == 200 and 'token' not in body and _cookie_named(response, 'dh_session')
    assert client.get_cookie('dh_session').value != old
    assert client.get('/admin/api/auth/me').status_code == 200            # the session carries on


# --- single sign-on ----------------------------------------------------------------------------------


def test_sso_exchange_in_cookie_mode_sets_the_cookie(client, user):
    code = oidc.create_handoff(user.id)
    response = client.post('/admin/api/auth/oidc/exchange', json={'code': code, 'session': 'cookie'}, headers=CSRF)
    assert response.status_code == 200 and 'token' not in response.get_json() and _cookie_named(response, 'dh_session')


def test_sso_exchange_in_bearer_mode_returns_the_token(client, user):
    response = client.post('/admin/api/auth/oidc/exchange', json={'code': oidc.create_handoff(user.id)})
    assert response.get_json()['token'] and not _set_cookie_headers(response)


# --- impersonation ---------------------------------------------------------------------------------------


@pytest.fixture()
def admin_and_target(db_session, make_user, make_group):
    from application.models import UserGroup
    admin = make_user(username='boss', password=PASSWORD)
    db_session.add(UserGroup(user_id=admin.id, group_id=make_group(is_superadmin=True).id))
    db_session.commit()
    return admin, make_user(username='target', password=PASSWORD)


def test_impersonating_keeps_the_own_session_in_a_second_cookie_and_stop_restores_it(client, admin_and_target):
    _admin, target = admin_and_target
    _login(client, 'boss')
    started = client.post('/admin/api/auth/impersonate', json={'user_id': target.id}, headers=CSRF)
    body = started.get_json()
    assert started.status_code == 200 and body['username'] == 'target' and body['impersonator_username'] == 'boss'
    assert 'token' not in body and _cookie_named(started, 'dh_original') and 'HttpOnly' in _cookie_named(started, 'dh_original')

    me = client.get('/admin/api/auth/me').get_json()
    assert me['username'] == 'target' and me['impersonator_username'] == 'boss' and me['can_stop_impersonating'] is True

    stopped = client.post('/admin/api/auth/impersonate/stop', headers=CSRF)
    assert stopped.status_code == 200 and stopped.get_json()['username'] == 'boss'
    after = client.get('/admin/api/auth/me').get_json()
    assert after['username'] == 'boss' and after['impersonator_username'] is None
    assert client.get_cookie('dh_original') is None


def test_impersonation_over_http_refuses_what_the_socket_event_refuses(client, admin_and_target, make_user):
    admin, target = admin_and_target
    _login(client, 'boss')
    assert client.post('/admin/api/auth/impersonate', json={'user_id': admin.id}, headers=CSRF).status_code == 400   # yourself
    assert client.post('/admin/api/auth/impersonate', json={'user_id': 999999}, headers=CSRF).status_code == 400
    client.post('/admin/api/auth/impersonate', json={'user_id': target.id}, headers=CSRF)
    chained = client.post('/admin/api/auth/impersonate', json={'user_id': admin.id}, headers=CSRF)
    assert chained.status_code in (400, 401)                                       # the target has no right, and could not chain


def test_impersonating_needs_the_right(client, user, make_user):
    other = make_user(username='someone', password=PASSWORD)
    _login(client)
    assert client.post('/admin/api/auth/impersonate', json={'user_id': other.id}, headers=CSRF).status_code == 401


def test_impersonation_over_http_needs_the_csrf_header(client, admin_and_target):
    _admin, target = admin_and_target
    _login(client, 'boss')
    assert client.post('/admin/api/auth/impersonate', json={'user_id': target.id}).status_code == 403


def test_a_bearer_client_gets_the_impersonation_token_back(flask_app, client, admin_and_target):
    admin, target = admin_and_target
    token = create_token(flask_app.app, admin)
    response = client.post('/admin/api/auth/impersonate', json={'user_id': target.id}, headers={'Authorization': f'Bearer {token}'})
    assert response.get_json()['token'] and not _set_cookie_headers(response)


def test_stop_without_an_original_session_logs_out(client, admin_and_target):
    _admin, target = admin_and_target
    _login(client, 'boss')
    client.post('/admin/api/auth/impersonate', json={'user_id': target.id}, headers=CSRF)
    client.delete_cookie('dh_original')
    response = client.post('/admin/api/auth/impersonate/stop', headers=CSRF)
    assert response.status_code == 401 and 'expired' in response.get_json()['error']


# --- the socket handshake --------------------------------------------------------------------------------------


JOINED = 'displayhive:admin:stc:joined_admins'


def _socket(flask_app, client, **kwargs):
    return flask_app.socketio.test_client(flask_app.app, flask_test_client=client, **kwargs)


def test_an_admin_socket_connects_with_the_cookie_from_our_own_origin(flask_app, client, user):
    _login(client)
    socket = _socket(flask_app, client, headers={'Origin': 'http://localhost'})
    try:
        assert socket.is_connected()
        assert JOINED in [m['name'] for m in socket.get_received()]
    finally:
        socket.disconnect()


def test_the_cookie_is_not_accepted_for_a_socket_from_another_origin(flask_app, client, user):
    _login(client)
    assert not _socket(flask_app, client, headers={'Origin': 'https://evil.example'}).is_connected()


def test_a_missing_origin_is_fine_for_a_same_origin_request(flask_app, client, user):
    """Browsers leave Origin off a same-origin GET — Socket.IO's first polling request, also
    when the dev server's proxy forwards it."""
    _login(client)
    for headers in ({}, {'Sec-Fetch-Site': 'same-origin'}):
        socket = _socket(flask_app, client, headers=headers)
        try:
            assert socket.is_connected()
        finally:
            socket.disconnect()


@pytest.mark.parametrize('site', ['cross-site', 'same-site'])
def test_a_missing_origin_is_not_fine_when_the_browser_says_the_request_is_not_same_origin(flask_app, client, user, site):
    _login(client)
    assert not _socket(flask_app, client, headers={'Sec-Fetch-Site': site}).is_connected()


def test_without_the_cookie_there_is_still_no_anonymous_access(flask_app, user):
    anonymous = flask_app.app.test_client()
    assert not _socket(flask_app, anonymous, headers={'Origin': 'http://localhost'}).is_connected()


def test_a_screen_with_a_device_key_is_never_treated_as_an_admin_because_of_a_cookie(flask_app, client, user, db_session):
    import uuid
    from application.models import Device
    device = Device(devicekey=str(uuid.uuid4()), name='lobby', is_active=True)
    db_session.add(device)
    db_session.commit()
    _login(client)                                                       # an admin cookie in the same browser
    screen = _socket(flask_app, client, query_string=f'devicekey={device.devicekey}', headers={'Origin': 'https://elsewhere.example'})
    try:
        assert screen.is_connected()                                    # the device key decides; no origin check, no admin rights
        names = [m['name'] for m in screen.get_received()]
        assert JOINED not in names and 'displayhive:devices:stc:device_authenticated' in names
    finally:
        screen.disconnect()


def test_the_token_in_the_handshake_still_works(flask_app, user):
    socket = flask_app.socketio.test_client(flask_app.app, auth={'token': create_token(flask_app.app, user)})
    try:
        assert socket.is_connected()
    finally:
        socket.disconnect()
