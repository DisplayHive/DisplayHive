"""Passkeys (WebAuthn): registering one and signing in with it (application/security/passkeys.py).

A small software authenticator (an ES256 key, "none" attestation) plays the browser's device, so the
whole round trip — options, the device's answer, verification, session — runs against the real routes.
"""

import base64
import hashlib
import json
import struct

import cbor2
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from application.security import passkeys

PASSWORD = 'a-long-enough-password'
ORIGIN = 'http://localhost'
RP_ID = 'localhost'
HEADERS = {'Origin': ORIGIN, 'X-DisplayHive-Request': '1'}


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


class Device:
    """A software authenticator: one credential, user verification always on."""

    def __init__(self, rp_id=RP_ID, origin=ORIGIN):
        self.rp_id, self.origin = rp_id, origin
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = hashlib.sha256(struct.pack('>Q', id(self))).digest()
        self.counter = 0
        self.user_handle = None

    def _cose_key(self) -> bytes:
        numbers = self.key.public_key().public_numbers()
        return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, 'big'), -3: numbers.y.to_bytes(32, 'big')})

    def _client_data(self, kind, challenge_b64, origin=None) -> bytes:
        return json.dumps({'type': kind, 'challenge': challenge_b64, 'origin': origin or self.origin, 'crossOrigin': False}).encode()

    def create(self, options, origin=None, rp_id=None):
        """The browser's answer to ``navigator.credentials.create``."""
        self.user_handle = unb64(options['user']['id'])
        rp_hash = hashlib.sha256((rp_id or self.rp_id).encode()).digest()
        cred = self.credential_id
        auth_data = rp_hash + bytes([0x45]) + struct.pack('>I', self.counter) + bytes(16) + struct.pack('>H', len(cred)) + cred + self._cose_key()
        attestation = cbor2.dumps({'fmt': 'none', 'attStmt': {}, 'authData': auth_data})
        return {
            'id': b64(cred), 'rawId': b64(cred), 'type': 'public-key', 'clientExtensionResults': {},
            'response': {
                'clientDataJSON': b64(self._client_data('webauthn.create', options['challenge'], origin)),
                'attestationObject': b64(attestation), 'transports': ['internal'],
            },
        }

    def get(self, options, origin=None, rp_id=None, user_handle=True):
        """The browser's answer to ``navigator.credentials.get``."""
        self.counter += 1
        rp_hash = hashlib.sha256((rp_id or self.rp_id).encode()).digest()
        auth_data = rp_hash + bytes([0x05]) + struct.pack('>I', self.counter)
        client_data = self._client_data('webauthn.get', options['challenge'], origin)
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        response = {'clientDataJSON': b64(client_data), 'authenticatorData': b64(auth_data), 'signature': b64(signature)}
        if user_handle and self.user_handle:
            response['userHandle'] = b64(self.user_handle)
        return {'id': b64(self.credential_id), 'rawId': b64(self.credential_id), 'type': 'public-key',
                'clientExtensionResults': {}, 'response': response}


@pytest.fixture()
def client(flask_app):
    passkeys.clear_pending()
    return flask_app.app.test_client()


@pytest.fixture()
def user(make_user):
    return make_user(username='passkey-user', password=PASSWORD)


def _bearer(client, username='passkey-user'):
    token = client.post('/admin/api/auth/login', json={'username': username, 'password': PASSWORD}).get_json()['token']
    return {'Authorization': f'Bearer {token}', **HEADERS}


def _register(client, headers, device, name='My laptop'):
    options = client.post('/admin/api/auth/me/passkeys/options', headers=headers).get_json()
    assert options['success'], options
    return client.post('/admin/api/auth/me/passkeys/verify', headers=headers, json={
        'challenge_id': options['challenge_id'], 'credential': device.create(options['options']), 'name': name,
    })


def _sign_in(client, device, **kwargs):
    options = client.post('/admin/api/auth/passkey/login/options', headers=HEADERS).get_json()
    assert options['success'], options
    return client.post('/admin/api/auth/passkey/login/verify', headers=HEADERS, json={
        'challenge_id': options['challenge_id'], 'credential': device.get(options['options'], **kwargs),
    })


def test_register_a_passkey_then_sign_in_without_a_username(client, user):
    device = Device()
    registered = _register(client, _bearer(client), device).get_json()
    assert registered['success'] and registered['passkey']['name'] == 'My laptop'

    response = _sign_in(client, device)
    body = response.get_json()
    assert response.status_code == 200 and body['success'] and body['username'] == 'passkey-user'
    assert body['token'] and body['must_change_password'] is False

    # the session works like any other
    me = client.get('/admin/api/auth/me', headers={'Authorization': f"Bearer {body['token']}"})
    assert me.get_json()['username'] == 'passkey-user'


def test_a_passkey_session_is_not_stopped_by_a_forced_password_change(client, user, db_session):
    device = Device()
    _register(client, _bearer(client), device)
    user.must_change_password = True
    db_session.commit()
    body = _sign_in(client, device).get_json()
    assert body['success'] and body['must_change_password'] is False
    # a protected route that a password session would have been refused on
    assert client.get('/admin/api/auth/me/passkeys', headers={'Authorization': f"Bearer {body['token']}", **HEADERS}).status_code == 200


def test_the_challenge_can_only_be_used_once(client, user):
    device = Device()
    _register(client, _bearer(client), device)
    options = client.post('/admin/api/auth/passkey/login/options', headers=HEADERS).get_json()
    credential = device.get(options['options'])
    payload = {'challenge_id': options['challenge_id'], 'credential': credential}
    assert client.post('/admin/api/auth/passkey/login/verify', headers=HEADERS, json=payload).status_code == 200
    again = client.post('/admin/api/auth/passkey/login/verify', headers=HEADERS, json=payload)
    assert again.status_code == 401


def test_a_replayed_signature_with_a_stale_counter_is_refused(client, user):
    device = Device()
    _register(client, _bearer(client), device)
    assert _sign_in(client, device).status_code == 200
    device.counter = 0          # a cloned authenticator that counts again from the start
    assert _sign_in(client, device).status_code == 401


def test_the_answer_from_another_origin_is_refused(client, user):
    device = Device()
    _register(client, _bearer(client), device)
    assert _sign_in(client, device, origin='https://evil.example').status_code == 401


def test_a_passkey_made_for_another_site_is_refused(client, user):
    device = Device(rp_id='evil.example')
    registered = _register(client, _bearer(client), device)
    assert registered.status_code == 400 and not registered.get_json()['success']


def test_an_unknown_passkey_is_refused(client, user):
    assert _sign_in(client, Device()).status_code == 401


def test_a_deactivated_account_cannot_sign_in(client, user, db_session):
    device = Device()
    _register(client, _bearer(client), device)
    user.is_active = False
    db_session.commit()
    assert _sign_in(client, device).status_code == 403


def test_a_passkey_of_one_account_does_not_sign_in_another(client, user, make_user):
    other = make_user(username='someone-else', password=PASSWORD)
    device = Device()
    _register(client, _bearer(client), device)
    forged = Device()
    forged.credential_id = device.credential_id          # same credential id, different key
    assert _sign_in(client, forged).status_code == 401
    assert other.id != user.id


def test_manage_own_passkeys_only(client, user, make_user):
    headers = _bearer(client)
    device = Device()
    passkey = _register(client, headers, device).get_json()['passkey']
    listed = client.get('/admin/api/auth/me/passkeys', headers=headers).get_json()
    assert listed['available'] is True and [p['id'] for p in listed['passkeys']] == [passkey['id']]

    renamed = client.patch(f"/admin/api/auth/me/passkeys/{passkey['id']}", headers=headers, json={'name': '  Work   phone '})
    assert renamed.get_json()['passkey']['name'] == 'Work phone'

    make_user(username='intruder', password=PASSWORD)
    other = _bearer(client, 'intruder')
    assert client.delete(f"/admin/api/auth/me/passkeys/{passkey['id']}", headers=other).status_code == 404
    assert client.delete(f"/admin/api/auth/me/passkeys/{passkey['id']}", headers=headers).get_json()['success'] is True
    assert client.get('/admin/api/auth/me/passkeys', headers=headers).get_json()['passkeys'] == []


def test_the_same_passkey_cannot_be_registered_twice(client, user):
    headers = _bearer(client)
    device = Device()
    assert _register(client, headers, device).get_json()['success']
    again = _register(client, headers, device)
    assert again.status_code == 400


def test_passkeys_are_not_offered_where_they_cannot_work(client, flask_app):
    # An IP address can never be a relying-party id; a plain host that is not localhost needs PUBLIC_URL.
    for origin in ('http://127.0.0.1:5000', 'https://signage.example.com'):
        response = client.post('/admin/api/auth/passkey/login/options', headers={'Origin': origin})
        assert response.status_code == 400
    providers = client.get('/admin/api/auth/providers', base_url='http://signage.example.com').get_json()
    assert providers['passkeys'] is False
    assert client.get('/admin/api/auth/providers', base_url='http://localhost').get_json()['passkeys'] is True


def test_public_url_decides_the_relying_party(flask_app, client, monkeypatch):
    monkeypatch.setitem(flask_app.app.config, 'PUBLIC_URL', 'https://signage.example.com')
    from flask import request
    with flask_app.app.test_request_context('/', headers={'Origin': 'http://attacker.example'}):
        rp = passkeys.relying_party(flask_app.app, request)
    assert (rp.rp_id, rp.origin) == ('signage.example.com', 'https://signage.example.com')


def test_an_impersonation_session_cannot_change_passkeys(client, user, make_user, flask_app):
    from application.security.auth import create_token
    admin = make_user(username='boss', password=PASSWORD)
    token = create_token(flask_app.app, user, impersonator_id=admin.id)
    response = client.post('/admin/api/auth/me/passkeys/options', headers={'Authorization': f'Bearer {token}', **HEADERS})
    assert response.status_code == 403


def test_the_users_page_sees_a_users_passkeys_and_they_go_with_the_account(client, user, db_session):
    from application.models import AdminUser, AdminUserPasskey
    device = Device()
    _register(client, _bearer(client), device, name='Phone')
    db_session.refresh(user)
    shown = user.to_dict()['passkeys']
    assert [p['name'] for p in shown] == ['Phone']
    assert 'public_key' not in shown[0] and 'credential_id' not in shown[0]

    user_id = user.id
    db_session.delete(user)
    db_session.commit()
    assert db_session.get(AdminUser, user_id) is None
    assert db_session.execute(db_session.query(AdminUserPasskey).filter_by(user_id=user_id).statement).first() is None


def test_me_tells_whether_the_account_has_a_password_to_change(client, user, db_session):
    headers = _bearer(client)
    assert client.get('/admin/api/auth/me', headers=headers).get_json()['password_login_allowed'] is True
    user.password_login_allowed = False
    db_session.commit()
    assert client.get('/admin/api/auth/me', headers=headers).get_json()['password_login_allowed'] is False
