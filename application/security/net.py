"""Outgoing HTTP requests to addresses an administrator typed in (SSRF protection).

Pretalx API URLs and SSO providers are configured in the admin panel, and the
server then fetches them. Without a check, whoever can configure one can make the
server talk to things only the server can reach: the cloud metadata service
(169.254.169.254), a database admin page on 127.0.0.1, other machines in the
internal network. Everything that fetches such a URL goes through ``get`` /
``post`` here instead of ``requests``:

* only http and https;
* the host is resolved, and **every** address it resolves to must be allowed — a
  name with one public and one internal record is refused;
* the connection is made to exactly the address that was checked (the check is in
  the connect itself, so DNS rebinding — a second answer after the check — cannot
  slip an internal address in);
* redirects are followed by hand (GET only), each hop checked again;
* the answer is read up to a size limit.

What counts as allowed: public addresses always. Private networks (10.x,
192.168.x, 172.16/12, fc00::/7, 100.64/10, loopback …) only if "Allow requests to
private networks" is switched on in the admin Settings (a Superadmin's choice) or
``OUTBOUND_ALLOW_PRIVATE=1`` is set. Link-local (the metadata service), multicast,
unspecified and reserved addresses are refused either way.

A configured outbound proxy (HTTP_PROXY / HTTPS_PROXY) is honoured, but then the
connection goes to the proxy: only the destination's address is checked beforehand,
not pinned.
"""

import ipaddress
import logging
import os
import socket
import threading
import time
from typing import Callable, Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import ConnectTimeoutError, NameResolutionError, NewConnectionError
from urllib3.util import parse_url

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10
DEFAULT_MAX_BYTES = 20 * 1024 * 1024
MAX_REDIRECTS = 5
SETTING_KEY = 'outbound_allow_private'
_REDIRECT_STATUSES = (301, 302, 303, 307, 308)


class OutboundError(requests.RequestException):
    """A request was not made or not accepted; the message is meant for the admin."""


class OutboundBlocked(OutboundError):
    """The destination is an address DisplayHive does not connect to."""


# --- the policy ----------------------------------------------------------------------

_provider: Optional[Callable[[], bool]] = None
_cache = {'at': 0.0, 'value': False}
_cache_lock = threading.Lock()
_CACHE_SECONDS = 15


def configure(provider: Optional[Callable[[], bool]]) -> None:
    """Where the Settings switch is read from (the app registers it at start-up)."""
    global _provider
    _provider = provider
    invalidate()


def register_policy(app, db) -> None:
    """Read the Settings switch from this app's database. The first app built wins
    (the default one); later ones (tests, maintenance commands next to it) keep it."""
    if _provider is not None:
        return

    def read() -> bool:
        from application.models import SystemSetting
        with app.app_context():
            row = db.session.execute(db.select(SystemSetting).where(SystemSetting.key == SETTING_KEY)).scalar_one_or_none()
        return bool(row and (row.value or '').strip().lower() in ('1', 'true', 'yes', 'on'))

    configure(read)


def invalidate() -> None:
    with _cache_lock:
        _cache['at'] = 0.0


def env_allows_private() -> bool:
    return (os.environ.get('OUTBOUND_ALLOW_PRIVATE') or '').strip().lower() in ('1', 'true', 'yes', 'on')


def private_allowed() -> bool:
    if env_allows_private():
        return True
    if _provider is None:
        return False
    with _cache_lock:
        if time.monotonic() - _cache['at'] < _CACHE_SECONDS:
            return _cache['value']
    try:
        value = bool(_provider())
    except Exception:
        logger.warning('Could not read the outbound policy setting; private networks stay blocked', exc_info=True)
        value = False
    with _cache_lock:
        _cache.update(at=time.monotonic(), value=value)
    return value


_NAT64 = ipaddress.ip_network('64:ff9b::/96')


def _embedded_ipv4(ip):
    """The IPv4 address hidden inside an IPv6 one (::ffff:10.0.0.1, 64:ff9b::a00:1,
    6to4), or None — checking the wrapper alone would let those through."""
    if ip.version != 6:
        return None
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip in _NAT64:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if ip.sixtofour is not None:
        return ip.sixtofour
    return None


def blocked_reason(ip, allow_private: Optional[bool] = None) -> Optional[str]:
    """Why DisplayHive refuses to connect to *ip*, or None if it may."""
    ip = ipaddress.ip_address(ip) if not hasattr(ip, 'version') else ip
    inner = _embedded_ipv4(ip)
    if inner is not None:
        return blocked_reason(inner, allow_private)
    # (IPv6 ::1 is inside Python's "reserved" ::/8; loopback is a private address, decided below.)
    if ip.is_link_local or ip.is_multicast or ip.is_unspecified or (ip.is_reserved and not ip.is_loopback):
        return 'a special-purpose address (link-local, multicast or reserved — this includes the cloud metadata service)'
    if ip.is_global:
        return None
    if allow_private is None:
        allow_private = private_allowed()
    if allow_private:
        return None
    return 'an address inside a private or internal network'


def _refusal(host, ip, reason) -> OutboundBlocked:
    hint = ''
    if 'private' in reason:
        hint = (" DisplayHive connects to such addresses only if \"Allow requests to private networks\" is switched on "
                "in Settings (Superadmin) or OUTBOUND_ALLOW_PRIVATE=1 is set.")
    return OutboundBlocked(f'{host} resolves to {ip}, {reason}.{hint}')


def _resolve(host, port):
    try:
        infos = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise OutboundError(f'The host name {host!r} could not be resolved: {exc.strerror or exc}') from exc
    if not infos:
        raise OutboundError(f'The host name {host!r} could not be resolved.')
    return infos


def _check_destination(host, port) -> None:
    """Refuse unless every address *host* resolves to is allowed."""
    allow_private = private_allowed()
    for _family, _type, _proto, _canon, sockaddr in _resolve(host, port):
        ip = ipaddress.ip_address(sockaddr[0].split('%')[0])
        reason = blocked_reason(ip, allow_private)
        if reason:
            raise _refusal(host, ip, reason)


# --- the guarded connection --------------------------------------------------------------


def _create_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, socket_options=None):
    """urllib3's create_connection, with the check inside it: resolve, validate every
    address, connect to one of exactly those."""
    host, port = address
    host = host.strip('[]')
    allow_private = private_allowed()
    candidates = _resolve(host, port)
    for _family, _type, _proto, _canon, sockaddr in candidates:
        ip = ipaddress.ip_address(sockaddr[0].split('%')[0])
        reason = blocked_reason(ip, allow_private)
        if reason:
            raise _refusal(host, ip, reason)
    error = None
    for family, socktype, proto, _canon, sockaddr in candidates:
        sock = None
        try:
            sock = socket.socket(family, socktype, proto)
            for option in socket_options or ():
                sock.setsockopt(*option)
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            error = exc
            if sock is not None:
                sock.close()
    raise error or OSError('no address to connect to')


def _guarded_new_conn(self):
    try:
        return _create_connection((self._dns_host, self.port), self.timeout,
                                  source_address=self.source_address, socket_options=self.socket_options)
    except OutboundError:
        raise
    except socket.gaierror as exc:
        raise NameResolutionError(self.host, self, exc) from exc
    except socket.timeout as exc:
        raise ConnectTimeoutError(self, f'Connection to {self.host} timed out. (connect timeout={self.timeout})') from exc
    except OSError as exc:
        raise NewConnectionError(self, f'Failed to establish a new connection: {exc}') from exc


class _GuardedHTTPConnection(HTTPConnection):
    _new_conn = _guarded_new_conn


class _GuardedHTTPSConnection(HTTPSConnection):
    _new_conn = _guarded_new_conn


class _GuardedHTTPPool(HTTPConnectionPool):
    ConnectionCls = _GuardedHTTPConnection


class _GuardedHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _GuardedHTTPSConnection


class _GuardedAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        super().init_poolmanager(connections, maxsize, block, **pool_kwargs)
        self.poolmanager.pool_classes_by_scheme = {'http': _GuardedHTTPPool, 'https': _GuardedHTTPSPool}


def _session(url) -> requests.Session:
    session = requests.Session()
    if requests.utils.select_proxy(url, requests.utils.get_environ_proxies(url)):
        return session   # via a configured proxy: only the destination was checked beforehand
    session.trust_env = False
    session.mount('http://', _GuardedAdapter(max_retries=0))
    session.mount('https://', _GuardedAdapter(max_retries=0))
    return session


# --- requests --------------------------------------------------------------------------------


def _unwrap(exc: BaseException) -> Optional[OutboundError]:
    """A refusal raised while connecting comes back wrapped in requests' ConnectionError."""
    seen = set()
    stack = [exc]
    while stack:
        current = stack.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, OutboundError):
            return current
        stack += [getattr(current, 'reason', None), current.__cause__, current.__context__]
        stack += [arg for arg in getattr(current, 'args', ()) if isinstance(arg, BaseException)]
    return None


def _check_url(url: str) -> None:
    parsed = parse_url(url)   # urllib3 parses it the way it will connect, so there is no second reading to trick
    if parsed.scheme not in ('http', 'https'):
        raise OutboundError(f'Only http:// and https:// addresses are allowed, not {parsed.scheme or "a relative"} URL {url!r}.')
    if not parsed.host:
        raise OutboundError(f'The address {url!r} has no host name.')
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    _check_destination(parsed.host.strip('[]'), port)


def request(method: str, url: str, *, timeout: float = DEFAULT_TIMEOUT, max_bytes: int = DEFAULT_MAX_BYTES,
            follow_redirects: Optional[bool] = None, **kwargs) -> requests.Response:
    """``requests.request`` for admin-supplied URLs; see the module docstring.
    Raises OutboundError (OutboundBlocked for a refused address), which is a
    ``requests.RequestException``, so existing handlers keep working."""
    method = method.upper()
    if follow_redirects is None:
        follow_redirects = method in ('GET', 'HEAD')
    original_host = parse_url(url).host
    for _hop in range(MAX_REDIRECTS + 1):
        _check_url(url)
        session = _session(url)
        try:
            response = session.request(method, url, timeout=timeout, allow_redirects=False, stream=True, **kwargs)
        except requests.RequestException as exc:
            refusal = _unwrap(exc)
            if refusal is not None:
                raise refusal from None
            raise
        if follow_redirects and response.status_code in _REDIRECT_STATUSES and response.headers.get('Location'):
            response.close()
            url = urljoin(url, response.headers['Location'])
            if parse_url(url).host != original_host:
                kwargs.pop('auth', None)   # credentials were for the first host
                headers = dict(kwargs.get('headers') or {})
                for name in [h for h in headers if h.lower() in ('authorization', 'cookie')]:
                    headers.pop(name)
                kwargs['headers'] = headers
            continue
        body = bytearray()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body) > max_bytes:
                response.close()
                raise OutboundError(f'The answer from {url} is larger than {max_bytes // 1024 // 1024} MB; not reading it.')
        response._content = bytes(body)
        response._content_consumed = True
        return response
    raise OutboundError(f'{url} redirects too often (more than {MAX_REDIRECTS} times).')


def get(url: str, **kwargs) -> requests.Response:
    return request('GET', url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    return request('POST', url, **kwargs)
