"""Where an admin request's token comes from, and the cookie it can travel in.

The session is the same signed JWT as ever (application/auth.py). It reaches the
server in one of two ways:

* ``Authorization: Bearer <jwt>`` — scripts, the CLI, tests. The caller holds the
  token and presents it on purpose, so there is nothing to forge from another site.
* A **cookie** (``dh_session``, or ``__Host-dh_session`` over https) — the admin
  panel in a browser. It is ``HttpOnly`` (JavaScript, and so an XSS bug, cannot read
  it), ``SameSite=Strict`` (not sent on requests started by other sites) and
  ``Secure`` over https. Because a browser attaches cookies by itself, requests that
  change something and arrive with a cookie must also prove they come from our own
  page: an ``Origin`` that is ours and the header ``X-DisplayHive-Request: 1`` (a
  header other sites cannot add without a CORS pre-flight). Both are checked in
  ``csrf_problem``.

Screens do not use any of this: they authenticate with their device key, and some
kiosk browsers do not keep cookies at all.

A second cookie, ``dh_original``, holds the administrator's own session while they
are impersonating someone (so "stop impersonating" needs no new login).
"""

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlsplit

from application.auth import TOKEN_TTL, decode_token

SESSION_COOKIE = 'dh_session'
ORIGINAL_COOKIE = 'dh_original'
HOST_PREFIX = '__Host-'
CSRF_HEADER = 'X-DisplayHive-Request'
SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


def is_secure(app, request) -> bool:
    """Whether to mark cookies Secure: the request came over https (behind a proxy this
    needs TRUSTED_PROXY_COUNT), or PUBLIC_URL says the site is https."""
    public = app.config.get('PUBLIC_URL') or ''
    return bool(request.is_secure or public.startswith('https://'))


def _names(base: str):
    return (HOST_PREFIX + base, base)


def token_from_request(request, base: str = SESSION_COOKIE):
    """``(token, source)`` — source is 'bearer', 'cookie' or None. A Bearer header wins."""
    header = request.headers.get('Authorization', '')
    if base == SESSION_COOKIE and header.startswith('Bearer ') and header[7:]:
        return header[7:], 'bearer'
    for name in _names(base):
        value = request.cookies.get(name)
        if value:
            return value, 'cookie'
    return None, None


def _own_origin_ok(origin: str, request) -> bool:
    return urlsplit(origin).netloc.lower() == (request.host or '').lower()


def origin_allowed(app, request, origin: Optional[str]) -> bool:
    """Is *origin* (an Origin header) one of ours: this host, PUBLIC_URL's, or an
    explicitly configured CORS origin? ``*`` in CORS_ALLOWED_ORIGINS adds nothing
    here — a cookie must never be accepted from "any origin"."""
    if not origin or origin == 'null':
        return False
    normalised = origin.rstrip('/').lower()
    if _own_origin_ok(normalised, request):
        return True
    public = (app.config.get('PUBLIC_URL') or '').rstrip('/').lower()
    if public:
        parts = urlsplit(public)
        if normalised == f'{parts.scheme}://{parts.netloc}':
            return True
    configured = app.config.get('CORS_ORIGINS')
    if isinstance(configured, (list, tuple)):
        return normalised in {str(o).rstrip('/').lower() for o in configured}
    return False


def csrf_problem(app, request, source: Optional[str]) -> Optional[str]:
    """Why a cookie-authenticated request must be refused (cross-site request forgery
    protection), or None. Only cookie sessions on state-changing methods are checked."""
    if source != 'cookie' or request.method in SAFE_METHODS:
        return None
    origin = request.headers.get('Origin')
    if origin and not origin_allowed(app, request, origin):
        return 'Cross-origin request refused'
    if request.headers.get(CSRF_HEADER) != '1':
        return f'Missing {CSRF_HEADER} header'
    return None


def expires_at(app, token: str) -> Optional[str]:
    """When *token* stops being valid (ISO 8601, UTC), for the page's auto-logout."""
    payload = decode_token(app, token) or {}
    exp = payload.get('exp')
    return datetime.fromtimestamp(exp, tz=timezone.utc).isoformat() if exp else None


def set_cookie(response, app, request, token: str, base: str = SESSION_COOKIE) -> None:
    secure = is_secure(app, request)
    name = (HOST_PREFIX if secure else '') + base
    response.set_cookie(name, token, max_age=int(TOKEN_TTL.total_seconds()), path='/',
                        httponly=True, secure=secure, samesite='Strict')
    # A cookie from before the site moved to https must not linger next to the new one.
    if secure and request.cookies.get(base):
        response.delete_cookie(base, path='/', samesite='Strict')


def clear_cookies(response, *bases: str) -> None:
    for base in bases or (SESSION_COOKIE, ORIGINAL_COOKIE):
        for name in _names(base):
            # (A __Host- cookie can only be removed by a Secure Set-Cookie.)
            response.delete_cookie(name, path='/', secure=name.startswith(HOST_PREFIX), samesite='Strict')
