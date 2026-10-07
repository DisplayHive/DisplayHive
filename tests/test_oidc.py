"""Tests for SSO (OpenID Connect) login: application/oidc.py, its HTTP routes
in application/admin/auth/routes.py, and the account-management rules that
come with it (password-login flag, merging, the break-glass Superadmin).

The identity provider is faked in-process: its discovery document and token
endpoint replace `requests.get`/`requests.post` inside application.oidc, and
its signing key replaces the JWKS client. Everything DisplayHive itself does
— PKCE, state/nonce/cookie checks, ID-token verification, account mapping,
the handoff code — runs for real.
"""

import base64
import hashlib
import time
import urllib.parse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from application import oidc
from application.auth import user_from_token

ISSUER = 'https://idp.example.com/realms/main'
CLIENT_ID = 'displayhive'
CLIENT_SECRET = 's3cret'


class _Response:
    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise oidc.requests.HTTPError(str(self.status_code))


class FakeIdP:
    """Discovery + token endpoint + signing key of a fake provider."""

    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.doc = {
            'issuer': ISSUER,
            'authorization_endpoint': f'{ISSUER}/protocol/openid-connect/auth',
            'token_endpoint': f'{ISSUER}/protocol/openid-connect/token',
            'jwks_uri': f'{ISSUER}/protocol/openid-connect/certs',
            'id_token_signing_alg_values_supported': ['RS256'],
            'code_challenge_methods_supported': ['S256'],
        }
        self.sub = 'user-123'
        self.extra_claims = {'preferred_username': 'anna', 'email': 'anna@example.com'}
        self.claim_overrides = {}
        self.nonce = None
        self.code_challenge = None
        self.token_requests = []

    def id_token(self):
        now = int(time.time())
        claims = {
            'iss': ISSUER, 'sub': self.sub, 'aud': CLIENT_ID,
            'iat': now, 'exp': now + 300, 'nonce': self.nonce,
            **self.extra_claims, **self.claim_overrides,
        }
        return jwt.encode(claims, self.key, algorithm='RS256', headers={'kid': 'k1'})

    # Stand-ins for requests.get / requests.post inside application.oidc.
    def get(self, url, timeout=None):
        assert url == f'{ISSUER}/.well-known/openid-configuration'
        return _Response(self.doc)

    def post(self, url, data=None, auth=None, headers=None, timeout=None):
        assert url == self.doc['token_endpoint']
        self.token_requests.append({'data': dict(data), 'auth': auth})
        verifier_hash = base64.urlsafe_b64encode(
            hashlib.sha256(data['code_verifier'].encode()).digest()
        ).rstrip(b'=').decode()
        if data.get('code') != 'good-code' or verifier_hash != self.code_challenge:
            return _Response({'error': 'invalid_grant'}, status_code=400)
        return _Response({'access_token': 'x', 'token_type': 'Bearer', 'id_token': self.id_token()})


class _JwksClient:
    def __init__(self, key):
        self._key = key

    def get_signing_key_from_jwt(self, token):
        return type('SigningKey', (), {'key': self._key})()


@pytest.fixture(autouse=True)
def reset_oidc_state():
    for store in (oidc._pending, oidc._handoffs, oidc._discovery_cache, oidc._jwks_clients):
        store.clear()
    yield
    for store in (oidc._pending, oidc._handoffs, oidc._discovery_cache, oidc._jwks_clients):
        store.clear()


@pytest.fixture()
def idp(monkeypatch):
    fake = FakeIdP()
    monkeypatch.setattr(oidc.requests, 'get', fake.get)
    monkeypatch.setattr(oidc.requests, 'post', fake.post)
    published_key = fake.key.public_key()  # what the provider's JWKS serves, fixed now
    monkeypatch.setattr(oidc, '_jwks_client', lambda uri: _JwksClient(published_key))
    return fake


@pytest.fixture()
def provider(db_session):
    from application.models import AuthProvider
    p = AuthProvider(slug='main', name='Main IdP', issuer=ISSUER, client_id=CLIENT_ID,
                     client_secret=CLIENT_SECRET, scopes='openid profile email', enabled=True)
    db_session.add(p)
    db_session.commit()
    return p


def _fragment(response):
    location = response.headers['Location']
    assert location.startswith('/admin/#'), location
    return dict(urllib.parse.parse_qsl(location.split('#', 1)[1]))


def _start(client, idp, slug='main'):
    response = client.get(f'/admin/api/auth/oidc/{slug}/start')
    assert response.status_code == 302
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(response.headers['Location']).query))
    idp.nonce = query.get('nonce')
    idp.code_challenge = query.get('code_challenge')
    return query


def _callback(client, query, code='good-code', slug='main'):
    return client.get(f'/admin/api/auth/oidc/{slug}/callback?' + urllib.parse.urlencode(
        {'code': code, 'state': query['state']}))


def _sso_login(client, idp):
    """Run the whole flow; returns the exchange endpoint's JSON."""
    query = _start(client, idp)
    fragment = _fragment(_callback(client, query))
    assert 'oidc_code' in fragment, fragment
    response = client.post('/admin/api/auth/oidc/exchange', json={'code': fragment['oidc_code']})
    assert response.status_code == 200
    return response.get_json()


def _user(db_session, username):
    from application.models import AdminUser
    return db_session.execute(
        db_session.query(AdminUser).filter_by(username=username).statement
    ).scalar_one_or_none()


# --- The login flow ------------------------------------------------------------


def test_first_login_creates_account_without_password_or_groups(flask_app, db_session, idp, provider):
    from application.models import UserGroup

    result = _sso_login(flask_app.app.test_client(), idp)
    assert result['success'] is True
    assert result['username'] == 'anna'
    assert result['must_change_password'] is False

    user = _user(db_session, 'anna')
    assert user.password_hash == ''
    assert user.password_login_allowed is False
    assert [(i.issuer, i.subject, i.display_name) for i in user.identities] == [(ISSUER, 'user-123', 'anna@example.com')]
    assert db_session.query(UserGroup).filter_by(user_id=user.id).count() == 0
    assert user_from_token(flask_app.app, flask_app.db, result['token']).id == user.id


def test_second_login_reuses_the_account(flask_app, db_session, idp, provider):
    from application.models import AdminUser

    client = flask_app.app.test_client()
    first = _sso_login(client, idp)
    idp.extra_claims = {'preferred_username': 'anna.renamed'}  # name changes don't matter, sub does
    second = _sso_login(client, idp)
    assert first['username'] == second['username'] == 'anna'
    assert db_session.query(AdminUser).filter(AdminUser.username.like('anna%')).count() == 1


def test_username_collision_gets_a_suffix(flask_app, db_session, idp, provider, make_user):
    make_user(username='anna')
    result = _sso_login(flask_app.app.test_client(), idp)
    assert result['username'] == 'anna-2'


def test_flow_uses_pkce_and_client_secret(flask_app, db_session, idp, provider):
    client = flask_app.app.test_client()
    query = _start(client, idp)
    assert query['code_challenge_method'] == 'S256'
    assert query['client_id'] == CLIENT_ID
    assert query['redirect_uri'] == 'http://localhost/admin/api/auth/oidc/main/callback'
    assert 'openid' in query['scope'].split()
    _callback(client, query)
    request = idp.token_requests[-1]
    assert request['auth'] == (CLIENT_ID, CLIENT_SECRET)
    assert request['data']['redirect_uri'] == query['redirect_uri']
    assert 'client_secret' not in request['data']


@pytest.mark.parametrize('override, message', [
    ({'nonce': 'someone-elses-nonce'}, 'different login attempt'),
    ({'aud': 'another-app'}, 'could not be verified'),
    ({'iss': 'https://evil.example.com'}, 'could not be verified'),
    ({'exp': int(time.time()) - 3600}, 'could not be verified'),
])
def test_invalid_id_tokens_are_rejected(flask_app, db_session, idp, provider, override, message):
    from application.models import AdminUserIdentity

    idp.claim_overrides = override
    client = flask_app.app.test_client()
    fragment = _fragment(_callback(client, _start(client, idp)))
    assert 'oidc_code' not in fragment
    assert message in fragment['oidc_error']
    assert db_session.query(AdminUserIdentity).count() == 0


def test_token_signed_with_another_key_is_rejected(flask_app, db_session, idp, provider):
    idp.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)  # not the published one
    client = flask_app.app.test_client()
    fragment = _fragment(_callback(client, _start(client, idp)))
    assert 'could not be verified' in fragment['oidc_error']


def test_state_is_single_use(flask_app, db_session, idp, provider):
    client = flask_app.app.test_client()
    query = _start(client, idp)
    assert 'oidc_code' in _fragment(_callback(client, query))
    assert 'already used' in _fragment(_callback(client, query))['oidc_error']


def test_callback_from_another_browser_is_rejected(flask_app, db_session, idp, provider):
    query = _start(flask_app.app.test_client(), idp)
    fragment = _fragment(_callback(flask_app.app.test_client(), query))
    assert 'different browser' in fragment['oidc_error']


def test_handoff_code_is_single_use(flask_app, db_session, idp, provider):
    client = flask_app.app.test_client()
    code = _fragment(_callback(client, _start(client, idp)))['oidc_code']
    assert client.post('/admin/api/auth/oidc/exchange', json={'code': code}).status_code == 200
    assert client.post('/admin/api/auth/oidc/exchange', json={'code': code}).status_code == 401


def test_provider_error_and_disabled_provider(flask_app, db_session, idp, provider):
    client = flask_app.app.test_client()
    query = _start(client, idp)
    response = client.get('/admin/api/auth/oidc/main/callback?' + urllib.parse.urlencode(
        {'error': 'access_denied', 'state': query['state']}))
    assert 'cancelled or denied' in _fragment(response)['oidc_error']

    provider.enabled = False
    db_session.commit()
    assert 'not available' in _fragment(client.get('/admin/api/auth/oidc/main/start'))['oidc_error']
    assert client.get('/admin/api/auth/providers').get_json() == {'providers': []}


def test_deactivated_account_cannot_log_in(flask_app, db_session, idp, provider):
    client = flask_app.app.test_client()
    _sso_login(client, idp)
    user = _user(db_session, 'anna')
    user.is_active = False
    db_session.commit()
    fragment = _fragment(_callback(client, _start(client, idp)))
    assert fragment['oidc_error'] == 'This account has been deactivated'


def test_sso_session_ignores_password_reset_flag(flask_app, db_session, idp, provider):
    client = flask_app.app.test_client()
    _sso_login(client, idp)
    user = _user(db_session, 'anna')
    user.must_change_password = True
    db_session.commit()
    token = _sso_login(client, idp)['token']
    assert user_from_token(flask_app.app, flask_app.db, token) is not None


def test_password_login_refused_without_password_login_allowed(flask_app, db_session, make_user):
    user = make_user(username='local-user')
    client = flask_app.app.test_client()
    assert client.post('/admin/api/auth/login', json={'username': 'local-user', 'password': 'testpass123'}).status_code == 200
    user.password_login_allowed = False
    db_session.commit()
    response = client.post('/admin/api/auth/login', json={'username': 'local-user', 'password': 'testpass123'})
    assert response.status_code == 401
    assert response.get_json()['error'] == 'Invalid username or password'


# --- Account management over the socket ----------------------------------------


@pytest.fixture()
def admin_socket(flask_app, db_session, make_user):
    """A socket client logged in as a fresh Superadmin (with password login),
    after taking the startup bootstrap admin out of the break-glass count so
    tests control exactly who still has password login."""
    from application.models import AdminUser, Group, UserGroup
    from application.auth import create_token

    for other in db_session.query(AdminUser).all():
        other.password_login_allowed = False
    admin = make_user(username='root')
    superadmins = db_session.query(Group).filter_by(is_superadmin=True).one()
    db_session.add(UserGroup(user_id=admin.id, group_id=superadmins.id))
    db_session.commit()

    client = flask_app.socketio.test_client(flask_app.app, auth={'token': create_token(flask_app.app, admin)})
    assert client.is_connected()
    client.admin = admin
    client.superadmins = superadmins
    yield client
    client.disconnect()


def _emit(client, event, data):
    return client.emit(f'displayhive:admin:{event}', data, callback=True)


def test_last_password_superadmin_cannot_lose_password_login(db_session, admin_socket):
    admin = admin_socket.admin
    for event, data in [
        ('users:cts:update_user', {'id': admin.id, 'password_login_allowed': False}),
        ('users:cts:set_active', {'id': admin.id, 'is_active': False}),
        ('rights:cts:set_user_groups', {'user_id': admin.id, 'group_ids': []}),
    ]:
        result = _emit(admin_socket, event, data)
        assert result['success'] is False, event
        assert 'password login' in result['error']
    db_session.refresh(admin)
    assert admin.password_login_allowed is True and admin.is_active is True


def test_second_password_superadmin_makes_the_change_possible(db_session, admin_socket, make_user):
    from application.models import UserGroup
    backup = make_user(username='backup-root')
    db_session.add(UserGroup(user_id=backup.id, group_id=admin_socket.superadmins.id))
    db_session.commit()
    result = _emit(admin_socket, 'users:cts:update_user', {'id': admin_socket.admin.id, 'password_login_allowed': False})
    assert result == {'success': True}


def test_password_login_needs_a_password(db_session, admin_socket, idp, provider, flask_app):
    _sso_login(flask_app.app.test_client(), idp)
    sso_user = _user(db_session, 'anna')

    result = _emit(admin_socket, 'users:cts:update_user', {'id': sso_user.id, 'password_login_allowed': True})
    assert result['success'] is False and 'Set a password' in result['error']
    result = _emit(admin_socket, 'users:cts:update_user', {'id': sso_user.id, 'must_change_password': True})
    assert result['success'] is False

    # Setting a password switches password login on.
    result = _emit(admin_socket, 'users:cts:update_user', {'id': sso_user.id, 'password': 'a-new-password'})
    assert result == {'success': True}
    db_session.refresh(sso_user)
    assert sso_user.password_login_allowed is True


def test_merge_moves_sso_identity_onto_existing_account(flask_app, db_session, admin_socket, idp, provider, make_user):
    from application.models import AdminUser

    existing = make_user(username='anna.local')
    client = flask_app.app.test_client()
    _sso_login(client, idp)
    created = _user(db_session, 'anna')

    result = _emit(admin_socket, 'users:cts:merge_user', {'source_id': created.id, 'target_id': existing.id})
    assert result == {'success': True}
    db_session.expire_all()
    assert db_session.get(AdminUser, created.id) is None
    assert [i.subject for i in db_session.get(AdminUser, existing.id).identities] == ['user-123']

    # From now on the SSO login lands in the existing account.
    assert _sso_login(client, idp)['username'] == 'anna.local'


def test_merge_refuses_local_accounts_with_a_password(flask_app, db_session, admin_socket, idp, provider, make_user):
    from application.models import AdminUserIdentity
    _sso_login(flask_app.app.test_client(), idp)
    sso_user = _user(db_session, 'anna')
    local = make_user(username='has-password')
    other = make_user()
    sso_user.identities[0].user = local
    db_session.commit()
    result = _emit(admin_socket, 'users:cts:merge_user', {'source_id': local.id, 'target_id': other.id})
    assert result['success'] is False and 'without a password' in result['error']
    assert db_session.query(AdminUserIdentity).filter_by(user_id=local.id).count() == 1


def test_merge_refuses_accounts_without_sso_and_self(db_session, admin_socket, make_user):
    other = make_user()
    result = _emit(admin_socket, 'users:cts:merge_user', {'source_id': other.id, 'target_id': admin_socket.admin.id})
    assert result['success'] is False and 'no SSO login' in result['error']
    result = _emit(admin_socket, 'users:cts:merge_user', {'source_id': admin_socket.admin.id, 'target_id': other.id})
    assert result['success'] is False


def test_unlink_identity_makes_next_login_create_a_new_account(flask_app, db_session, admin_socket, idp, provider):
    client = flask_app.app.test_client()
    _sso_login(client, idp)
    user = _user(db_session, 'anna')
    result = _emit(admin_socket, 'users:cts:unlink_identity', {'id': user.identities[0].id})
    assert result == {'success': True}
    assert _sso_login(client, idp)['username'] == 'anna-2'


def test_provider_admin_never_returns_the_secret(db_session, admin_socket):
    result = _emit(admin_socket, 'authproviders:cts:save_provider', {
        'slug': 'corp', 'name': 'Corp SSO', 'issuer': 'https://sso.corp.example',
        'client_id': 'dh', 'client_secret': 'top-secret', 'scopes': 'profile email',
    })
    assert result['success'] is True
    saved = next(p for p in result['providers'] if p['slug'] == 'corp')
    assert saved['has_client_secret'] is True
    assert saved['scopes'] == 'openid profile email'
    assert 'top-secret' not in repr(result)

    # Saving without a secret keeps the stored one.
    result = _emit(admin_socket, 'authproviders:cts:save_provider', {
        'id': saved['id'], 'name': 'Corp', 'issuer': 'https://sso.corp.example', 'client_id': 'dh', 'scopes': 'openid',
    })
    assert next(p for p in result['providers'] if p['slug'] == 'corp')['has_client_secret'] is True


@pytest.mark.parametrize('issuer', ['http://sso.corp.example', 'not a url', 'https://sso.corp.example?x=1'])
def test_provider_admin_rejects_bad_issuers(db_session, admin_socket, issuer):
    result = _emit(admin_socket, 'authproviders:cts:save_provider', {
        'slug': 'bad', 'name': 'Bad', 'issuer': issuer, 'client_id': 'dh',
    })
    assert result['success'] is False
