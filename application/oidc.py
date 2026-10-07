"""OpenID Connect login: the Authorization Code flow with PKCE, run by the backend.

The backend is the OIDC client. It sends the browser to the provider, takes
the authorization code on the callback, swaps it for an ID token at the
provider's token endpoint, verifies that token, and maps its (issuer, sub)
onto an AdminUser — creating one on first login. After that the person holds
exactly the same DisplayHive JWT a password login produces (see
application/auth.py), so sockets, rights, impersonation and token_version
revocation need no SSO awareness at all.

The JWT reaches the SPA through a short-lived single-use handoff code in the
redirect URL's fragment, swapped via POST — never the JWT itself in a URL,
where proxy logs and browser history would keep it.

Pending logins and handoff codes are in-memory, like the login rate limiter
(see the note there): the app runs as a single worker, and a restart just
means an in-flight login has to be started again.

Plain `requests` + PyJWT (with `cryptography` for RS/ES/PS keys) rather than a
full OAuth library: the code flow is a handful of HTTP calls, and PyJWT's
JWKS client and claim checks cover the security-relevant part.
"""

import base64
import hashlib
import logging
import re
import secrets
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone

import jwt
import requests

logger = logging.getLogger(__name__)

HTTP_TIMEOUT_SECONDS = 10
DISCOVERY_TTL_SECONDS = 3600
PENDING_TTL_SECONDS = 600       # time to finish logging in at the provider
HANDOFF_TTL_SECONDS = 60        # time for the SPA to swap its handoff code
MAX_PENDING = 10_000            # memory bound: /start is unauthenticated
CLOCK_SKEW_SECONDS = 60
# Asymmetric algorithms only: an HS* ID token would be verified with the
# client secret, which turns every secret leak into token forgery.
ALLOWED_ID_TOKEN_ALGS = ['RS256', 'RS384', 'RS512', 'PS256', 'PS384', 'PS512', 'ES256', 'ES384', 'ES512', 'EdDSA']

SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')


class OidcError(Exception):
    """A login failure. `str(e)` is safe to show the person logging in."""


# --- Provider metadata -----------------------------------------------------

_discovery_cache: dict[str, tuple[float, dict]] = {}
_jwks_clients: dict[str, jwt.PyJWKClient] = {}


def discover(issuer: str, *, force: bool = False) -> dict:
    """Fetch (and cache) the provider's OpenID configuration for *issuer*."""
    issuer = issuer.strip()
    cached = _discovery_cache.get(issuer)
    if cached and not force and time.time() - cached[0] < DISCOVERY_TTL_SECONDS:
        return cached[1]
    url = issuer.rstrip('/') + '/.well-known/openid-configuration'
    try:
        response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        doc = response.json()
    except (requests.RequestException, ValueError) as e:
        raise OidcError(f'Could not load the provider configuration from {url}') from e
    if not isinstance(doc, dict):
        raise OidcError(f'Invalid provider configuration at {url}')
    # The spec requires an exact match; tolerate only a trailing-slash
    # difference in what the admin typed. doc['issuer'] is what ID tokens carry.
    if str(doc.get('issuer', '')).rstrip('/') != issuer.rstrip('/'):
        raise OidcError(f"The provider reports issuer {doc.get('issuer')!r}, not {issuer!r}")
    for key in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
        if not doc.get(key):
            raise OidcError(f'The provider configuration has no {key}')
    _discovery_cache[issuer] = (time.time(), doc)
    return doc


def _jwks_client(jwks_uri: str) -> jwt.PyJWKClient:
    client = _jwks_clients.get(jwks_uri)
    if client is None:
        client = jwt.PyJWKClient(jwks_uri, cache_keys=True, lifespan=DISCOVERY_TTL_SECONDS, timeout=HTTP_TIMEOUT_SECONDS)
        _jwks_clients[jwks_uri] = client
    return client


# --- Pending logins (state → what the callback needs) ----------------------

@dataclass
class PendingLogin:
    provider_id: int
    nonce: str
    code_verifier: str
    redirect_uri: str
    browser_binding: str
    created_at: float = field(default_factory=time.time)


_pending: dict[str, PendingLogin] = {}
# Guards _pending and _handoffs: requests run in parallel threads, and the
# pruning below iterates the dicts while other logins insert into them.
# (_discovery_cache/_jwks_clients need none: a race there only means one
# extra fetch.)
_state_lock = threading.Lock()


def _prune_pending(now: float) -> None:
    """Drop expired pending logins and enforce MAX_PENDING. Caller holds _state_lock."""
    for state in [s for s, p in _pending.items() if now - p.created_at >= PENDING_TTL_SECONDS]:
        del _pending[state]
    excess = len(_pending) - MAX_PENDING + 1
    if excess > 0:
        # Oldest first; dicts keep insertion order.
        for state in list(_pending)[:excess]:
            del _pending[state]


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def begin_login(provider, redirect_uri: str) -> tuple[str, str]:
    """Start a login with *provider* (an AuthProvider).

    Returns ``(authorization_url, browser_binding)``. The caller must set
    *browser_binding* as a cookie on the redirect: the callback only accepts
    the state back from the same browser, so nobody can log someone else in
    by getting them to open a callback URL from the attacker's own login.
    """
    doc = discover(provider.issuer)
    now = time.time()

    state = secrets.token_urlsafe(32)
    pending = PendingLogin(
        provider_id=provider.id,
        nonce=secrets.token_urlsafe(32),
        code_verifier=secrets.token_urlsafe(64),
        redirect_uri=redirect_uri,
        browser_binding=secrets.token_urlsafe(32),
        created_at=now,
    )
    with _state_lock:
        _prune_pending(now)
        _pending[state] = pending

    params = {
        'response_type': 'code',
        'client_id': provider.client_id,
        'redirect_uri': redirect_uri,
        'scope': provider.scopes or 'openid',
        'state': state,
        'nonce': pending.nonce,
        'code_challenge': _b64url(hashlib.sha256(pending.code_verifier.encode('ascii')).digest()),
        'code_challenge_method': 'S256',
    }
    endpoint = doc['authorization_endpoint']
    separator = '&' if '?' in endpoint else '?'
    return endpoint + separator + urllib.parse.urlencode(params), pending.browser_binding


def take_pending(state: str, browser_binding: str | None) -> PendingLogin:
    """Look up and consume the pending login for *state* (single use)."""
    with _state_lock:
        pending = _pending.pop(state or '', None)
    if pending is None or time.time() - pending.created_at >= PENDING_TTL_SECONDS:
        raise OidcError('This login attempt has expired or was already used. Please try again.')
    if not browser_binding or not secrets.compare_digest(pending.browser_binding, browser_binding):
        raise OidcError('This login was started in a different browser. Please try again.')
    return pending


# --- Code exchange + ID token verification --------------------------------

def exchange_code(provider, pending: PendingLogin, code: str) -> dict:
    """Swap the authorization *code* for tokens and return the verified ID token's claims."""
    doc = discover(provider.issuer)
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': pending.redirect_uri,
        'code_verifier': pending.code_verifier,
    }
    auth = None
    if provider.client_secret:
        methods = doc.get('token_endpoint_auth_methods_supported') or ['client_secret_basic']
        if 'client_secret_basic' in methods:
            # RFC 6749 §2.3.1: form-encode both parts before Basic auth.
            auth = (urllib.parse.quote(provider.client_id, safe=''), urllib.parse.quote(provider.client_secret, safe=''))
        else:
            data['client_id'] = provider.client_id
            data['client_secret'] = provider.client_secret
    else:
        data['client_id'] = provider.client_id  # public client, PKCE only

    try:
        response = requests.post(
            doc['token_endpoint'], data=data, auth=auth,
            headers={'Accept': 'application/json'}, timeout=HTTP_TIMEOUT_SECONDS,
        )
        body = response.json()
    except (requests.RequestException, ValueError) as e:
        raise OidcError('The provider could not be reached to complete the login.') from e
    if response.status_code != 200 or not isinstance(body, dict) or not body.get('id_token'):
        logger.warning('OIDC token exchange with %s failed: HTTP %s %s', provider.issuer, response.status_code,
                       body.get('error') if isinstance(body, dict) else '')
        raise OidcError('The provider rejected the login. Check the client ID, secret and redirect URI.')

    return verify_id_token(body['id_token'], doc, provider.client_id, pending.nonce)


def verify_id_token(id_token: str, doc: dict, client_id: str, nonce: str) -> dict:
    """Verify *id_token*'s signature and claims (OIDC Core §3.1.3.7)."""
    supported = doc.get('id_token_signing_alg_values_supported') or ['RS256']
    algorithms = [a for a in supported if a in ALLOWED_ID_TOKEN_ALGS]
    if not algorithms:
        raise OidcError('The provider signs ID tokens only with algorithms DisplayHive does not accept.')
    try:
        signing_key = _jwks_client(doc['jwks_uri']).get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=algorithms,
            audience=client_id,
            issuer=doc['issuer'],
            leeway=CLOCK_SKEW_SECONDS,
            options={'require': ['iss', 'sub', 'aud', 'exp', 'iat']},
        )
    except jwt.PyJWTError as e:
        logger.warning('OIDC ID token from %s rejected: %s', doc.get('issuer'), e)
        raise OidcError('The provider returned an ID token that could not be verified.') from e

    audiences = claims['aud'] if isinstance(claims['aud'], list) else [claims['aud']]
    if len(audiences) > 1 and claims.get('azp') != client_id:
        raise OidcError('The provider returned an ID token meant for another application.')
    if not secrets.compare_digest(str(claims.get('nonce', '')), nonce):
        raise OidcError('The provider returned an ID token for a different login attempt.')
    if not str(claims.get('sub', '')).strip():
        raise OidcError('The provider returned an ID token without a subject.')
    return claims


# --- Mapping claims onto an AdminUser --------------------------------------

def _display_name(claims: dict) -> str | None:
    for key in ('email', 'preferred_username', 'name'):
        value = str(claims.get(key) or '').strip()
        if value:
            return value[:255]
    return None


def _unique_username(db, AdminUser, claims: dict, provider) -> str:
    base = ''
    for key in ('preferred_username', 'email', 'name'):
        base = re.sub(r'\s+', ' ', str(claims.get(key) or '')).strip()
        if base:
            break
    if not base:
        base = f"{provider.slug}-{str(claims['sub'])[:12]}"
    base = base[:72]
    candidate, n = base, 1
    while db.session.execute(db.select(AdminUser.id).where(AdminUser.username == candidate)).first():
        n += 1
        candidate = f'{base}-{n}'
    return candidate


def resolve_user(db, provider, claims: dict):
    """Return the AdminUser for these verified *claims*, creating it on first login.

    Matched on (issuer, sub) only. A new account gets no groups (so no
    rights) and no password: an admin assigns groups — or merges it into an
    existing account — on the Users page.
    """
    from application.models import AdminUser, AdminUserIdentity

    issuer, subject = claims['iss'], str(claims['sub'])
    now = datetime.now(timezone.utc)
    identity = db.session.execute(
        db.select(AdminUserIdentity).where(
            AdminUserIdentity.issuer == issuer, AdminUserIdentity.subject == subject,
        )
    ).scalar_one_or_none()

    if identity is None:
        user = AdminUser(
            username=_unique_username(db, AdminUser, claims, provider),
            password_hash='',
            password_login_allowed=False,
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()
        identity = AdminUserIdentity(user_id=user.id, issuer=issuer, subject=subject)
        db.session.add(identity)
        logger.info("Created admin user '%s' on first SSO login via '%s'", user.username, provider.name)
    else:
        user = identity.user

    identity.provider_id = provider.id
    identity.display_name = _display_name(claims) or identity.display_name
    identity.last_login_at = now
    return user


# --- Handoff codes (callback → SPA) ---------------------------------------

@dataclass
class _Handoff:
    user_id: int
    created_at: float


_handoffs: dict[str, _Handoff] = {}


def create_handoff(user_id: int) -> str:
    now = time.time()
    code = secrets.token_urlsafe(32)
    with _state_lock:
        for old in [c for c, h in _handoffs.items() if now - h.created_at >= HANDOFF_TTL_SECONDS]:
            del _handoffs[old]
        _handoffs[code] = _Handoff(user_id=user_id, created_at=now)
    return code


def redeem_handoff(code: str) -> int | None:
    """Consume a handoff *code*; returns its user id, or None if unknown/expired/used."""
    with _state_lock:
        handoff = _handoffs.pop(code or '', None)
    if handoff is None or time.time() - handoff.created_at >= HANDOFF_TTL_SECONDS:
        return None
    return handoff.user_id
