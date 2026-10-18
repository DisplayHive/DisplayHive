"""Passkeys (WebAuthn): signing in to the admin with a device-held key instead of a password.

A passkey is a key pair the person's device creates for this site. The server keeps the public
half (``AdminUserPasskey``); signing in means the device signs a fresh, single-use challenge, which
``webauthn`` verifies against that public half, the site's origin and its relying-party id. Nothing
secret is stored on the server, and the passkey only works on the address it was made for.

Both ceremonies take two requests — ``begin_*`` hands the browser its options plus a challenge id,
``finish_*`` checks the browser's answer. Challenges live in memory (like the login rate limiter and
the SSO handoff codes: the app runs as one worker, and a restart just means an in-flight sign-in has
to be started again), are single-use and expire after ``CHALLENGE_TTL_SECONDS``.

Passkeys are *discoverable* ("resident"): the device knows which account a passkey is for, so signing
in needs no username. User verification (a PIN, fingerprint or face) is always required, so a stolen
device alone is not enough.

The relying-party id and the expected origin come from ``PUBLIC_URL``. Without it, only ``localhost``
(development) works, and the origin is taken from the request — see ``relying_party``.
"""

import json
import logging
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urlsplit

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse, WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from application.core.timeutil import utcnow_naive

logger = logging.getLogger(__name__)

RP_NAME = 'DisplayHive'
CHALLENGE_TTL_SECONDS = 300
MAX_PENDING = 10_000          # memory bound: the sign-in options are public
MAX_PASSKEYS_PER_USER = 20
MAX_NAME_LENGTH = 80


class PasskeyError(Exception):
    """A ceremony failed. ``str(e)`` is safe to show the person."""


@dataclass(frozen=True)
class RelyingParty:
    rp_id: str
    origin: str


def relying_party(app, request) -> Optional[RelyingParty]:
    """Who the passkeys are for, or ``None`` when this address cannot have passkeys.

    With ``PUBLIC_URL`` set, its host is the relying-party id and its origin the only accepted one.
    Without it only ``localhost`` is allowed (the dev servers), with the origin the browser sent.
    A bare IP address can never be a relying-party id.
    """
    public = (app.config.get('PUBLIC_URL') or '').strip()
    if public:
        parts = urlsplit(public)
        host = parts.hostname or ''
        if not host or _is_ip(host):
            return None
        return RelyingParty(rp_id=host.lower(), origin=f'{parts.scheme}://{parts.netloc}'.lower())
    # A page's POST always names its origin; a plain GET (is passkey sign-in on offer?) may not.
    origin = (request.headers.get('Origin') or request.host_url or '').strip().rstrip('/').lower()
    parts = urlsplit(origin)
    if parts.hostname == 'localhost':
        return RelyingParty(rp_id='localhost', origin=origin)
    return None


def _is_ip(host: str) -> bool:
    import ipaddress
    try:
        ipaddress.ip_address(host.strip('[]'))
        return True
    except ValueError:
        return False


# --- Pending challenges ----------------------------------------------------

@dataclass
class _Pending:
    challenge: bytes
    purpose: str            # 'register' or 'login'
    user_id: Optional[int]
    created_at: float


_pending: dict[str, _Pending] = {}
_lock = threading.Lock()


def _store(challenge: bytes, purpose: str, user_id: Optional[int]) -> str:
    now = time.time()
    token = secrets.token_urlsafe(24)
    with _lock:
        for key in [k for k, p in _pending.items() if now - p.created_at >= CHALLENGE_TTL_SECONDS]:
            del _pending[key]
        excess = len(_pending) - MAX_PENDING + 1
        if excess > 0:
            for key in list(_pending)[:excess]:
                del _pending[key]
        _pending[token] = _Pending(challenge, purpose, user_id, now)
    return token


def _take(token: str, purpose: str, user_id: Optional[int]) -> bytes:
    """The challenge for *token*, removed (single-use); ``PasskeyError`` if unknown, expired or not ours."""
    with _lock:
        pending = _pending.pop(str(token or ''), None)
    expired = pending is not None and time.time() - pending.created_at >= CHALLENGE_TTL_SECONDS
    if pending is None or expired or pending.purpose != purpose or pending.user_id != user_id:
        raise PasskeyError('This request has expired. Please try again.')
    return pending.challenge


def clear_pending() -> None:
    """Forget every pending challenge (tests)."""
    with _lock:
        _pending.clear()


# --- Helpers ---------------------------------------------------------------

def user_handle(user) -> bytes:
    """The stable, opaque id the device files a passkey under (not the username)."""
    return int(user.id).to_bytes(8, 'big')


def _descriptor(passkey) -> PublicKeyCredentialDescriptor:
    return PublicKeyCredentialDescriptor(id=base64url_to_bytes(passkey.credential_id))


def clean_name(name) -> str:
    text = ' '.join(str(name or '').split())[:MAX_NAME_LENGTH]
    return text or 'Passkey'


# --- Registration ----------------------------------------------------------

def begin_registration(db, rp: RelyingParty, user) -> dict:
    """Options for ``navigator.credentials.create`` plus the id of the challenge to send back."""
    from application.models import AdminUserPasskey
    existing = db.session.execute(db.select(AdminUserPasskey).where(AdminUserPasskey.user_id == user.id)).scalars().all()
    if len(existing) >= MAX_PASSKEYS_PER_USER:
        raise PasskeyError(f'At most {MAX_PASSKEYS_PER_USER} passkeys per account. Remove one first.')
    options = generate_registration_options(
        rp_id=rp.rp_id,
        rp_name=RP_NAME,
        user_id=user_handle(user),
        user_name=user.username,
        user_display_name=user.username,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[_descriptor(p) for p in existing],
    )
    return {'options': json.loads(options_to_json(options)), 'challenge_id': _store(options.challenge, 'register', user.id)}


def finish_registration(db, rp: RelyingParty, user, challenge_id: str, credential, name) -> 'AdminUserPasskey':
    """Check the browser's answer and store the new passkey (committed)."""
    from application.models import AdminUserPasskey
    challenge = _take(challenge_id, 'register', user.id)
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=rp.rp_id,
            expected_origin=rp.origin,
            require_user_verification=True,
        )
    except (InvalidRegistrationResponse, WebAuthnException, ValueError, KeyError, TypeError) as problem:
        logger.info('Passkey registration for %s refused: %s', user.username, problem)
        raise PasskeyError('The passkey could not be verified. Please try again.') from None
    credential_id = bytes_to_base64url(verified.credential_id)
    if db.session.execute(db.select(AdminUserPasskey.id).where(AdminUserPasskey.credential_id == credential_id)).first():
        raise PasskeyError('This passkey is already registered.')
    transports = None
    try:
        reported = credential.get('response', {}).get('transports') if isinstance(credential, dict) else None
        if isinstance(reported, list):
            transports = json.dumps([str(t) for t in reported][:8])
    except Exception:
        transports = None
    passkey = AdminUserPasskey(
        user_id=user.id,
        credential_id=credential_id,
        public_key=bytes_to_base64url(verified.credential_public_key),
        sign_count=int(verified.sign_count or 0),
        transports=transports,
        synced=str(getattr(verified.credential_device_type, 'value', verified.credential_device_type)) == 'multi_device',
        name=clean_name(name),
    )
    db.session.add(passkey)
    db.session.commit()
    return passkey


# --- Sign-in ---------------------------------------------------------------

def begin_login(rp: RelyingParty) -> dict:
    """Options for ``navigator.credentials.get`` (no username: the device offers its passkeys)."""
    options = generate_authentication_options(
        rp_id=rp.rp_id,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return {'options': json.loads(options_to_json(options)), 'challenge_id': _store(options.challenge, 'login', None)}


def finish_login(db, rp: RelyingParty, challenge_id: str, credential):
    """Check the browser's answer. Returns the ``AdminUser`` it proves; raises ``PasskeyError``.

    The sign-in is not recorded here, and an inactive account is not refused here: the route does both
    (it knows about the rate limiter and the login history).
    """
    from application.models import AdminUser, AdminUserPasskey
    challenge = _take(challenge_id, 'login', None)
    try:
        raw_id = credential['id']
        passkey = db.session.execute(
            db.select(AdminUserPasskey).where(AdminUserPasskey.credential_id == str(raw_id))
        ).scalar_one_or_none()
        if passkey is None:
            raise PasskeyError('This passkey is not registered here.')
        user = db.session.get(AdminUser, passkey.user_id)
        handle = (credential.get('response') or {}).get('userHandle')
        if handle and base64url_to_bytes(handle) != user_handle(user):
            raise PasskeyError('This passkey does not belong to the account it names.')
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=rp.rp_id,
            expected_origin=rp.origin,
            credential_public_key=base64url_to_bytes(passkey.public_key),
            credential_current_sign_count=int(passkey.sign_count or 0),
            require_user_verification=True,
        )
    except PasskeyError:
        raise
    except (InvalidAuthenticationResponse, WebAuthnException, ValueError, KeyError, TypeError) as problem:
        logger.info('Passkey sign-in refused: %s', problem)
        raise PasskeyError('The passkey could not be verified.') from None
    passkey.sign_count = int(verified.new_sign_count or 0)
    passkey.last_used_at = utcnow_naive()
    return user
