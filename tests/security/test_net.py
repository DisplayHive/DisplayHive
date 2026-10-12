"""application/net.py: admin-supplied URLs must not reach internal addresses."""

import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import requests

from application import net


# --- which addresses ---------------------------------------------------------------------


@pytest.mark.parametrize('ip', ['8.8.8.8', '93.184.216.34', '2606:4700:4700::1111'])
def test_public_addresses_are_allowed(ip):
    assert net.blocked_reason(ip, allow_private=False) is None


@pytest.mark.parametrize('ip', [
    '10.0.0.1', '172.16.0.5', '192.168.1.1', '127.0.0.1', '100.64.0.1', 'fc00::1', 'fd12:3456::1', '::1',
    '::ffff:10.0.0.1',          # IPv4 hidden in IPv6
    '64:ff9b::a00:1',           # NAT64 of 10.0.0.1
    '2002:0a00:0001::1',        # 6to4 of 10.0.0.1
])
def test_private_addresses_need_the_switch(ip):
    assert 'private' in net.blocked_reason(ip, allow_private=False)
    assert net.blocked_reason(ip, allow_private=True) is None


@pytest.mark.parametrize('ip', [
    '169.254.169.254', '169.254.0.1', 'fe80::1', 'fd00:ec2::254'.replace('fd00:ec2::254', 'fe80::a9fe:a9fe'),
    '224.0.0.1', 'ff02::1', '0.0.0.0', '::', '240.0.0.1', '::ffff:169.254.169.254',
])
def test_special_addresses_are_refused_even_when_private_networks_are_allowed(ip):
    assert 'special-purpose' in net.blocked_reason(ip, allow_private=False)
    assert 'special-purpose' in net.blocked_reason(ip, allow_private=True)


# --- the switch -------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_policy(monkeypatch):
    monkeypatch.delenv('OUTBOUND_ALLOW_PRIVATE', raising=False)
    saved = net._provider            # the default app's own (reads the Settings switch)
    net.configure(None)
    yield
    net.configure(saved)


def test_the_policy_comes_from_the_environment_or_the_setting(monkeypatch):
    assert net.private_allowed() is False
    net.configure(lambda: True)
    assert net.private_allowed() is True
    net.configure(lambda: False)
    assert net.private_allowed() is False
    monkeypatch.setenv('OUTBOUND_ALLOW_PRIVATE', '1')
    assert net.private_allowed() is True


def test_an_unreadable_setting_means_blocked():
    def broken():
        raise RuntimeError('database is down')
    net.configure(broken)
    assert net.private_allowed() is False


# --- a real (loopback) server ---------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status, body=b'{"ok": true}', headers=()):
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/ok':
            self._send(200)
        elif self.path == '/to-ok':
            self._send(302, headers=[('Location', '/ok')])
        elif self.path == '/to-metadata':
            self._send(302, headers=[('Location', 'http://169.254.169.254/latest/meta-data/')])
        elif self.path == '/loop':
            self._send(302, headers=[('Location', '/loop')])
        elif self.path == '/big':
            self._send(200, body=b'x' * 200_000)
        else:
            self._send(404, body=b'{}')

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length') or 0))
        self._send(302, headers=[('Location', '/ok')])


@pytest.fixture()
def server():
    httpd = HTTPServer(('127.0.0.1', 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{httpd.server_port}'
    httpd.shutdown()
    httpd.server_close()


def test_a_loopback_address_is_refused_by_default_with_a_message_that_says_why(server):
    with pytest.raises(net.OutboundBlocked) as error:
        net.get(f'{server}/ok')
    message = str(error.value)
    assert '127.0.0.1' in message and 'private' in message and 'Settings' in message
    assert isinstance(error.value, requests.RequestException)     # existing `except RequestException` keeps working


def test_it_connects_once_private_networks_are_allowed(server, monkeypatch):
    monkeypatch.setenv('OUTBOUND_ALLOW_PRIVATE', '1')
    response = net.get(f'{server}/ok')
    assert response.status_code == 200 and response.json() == {'ok': True}


def test_the_switch_from_the_setting_works_too(server):
    net.configure(lambda: True)
    assert net.get(f'{server}/ok').status_code == 200


def test_redirects_are_followed_and_checked(server, monkeypatch):
    monkeypatch.setenv('OUTBOUND_ALLOW_PRIVATE', '1')
    assert net.get(f'{server}/to-ok').json() == {'ok': True}
    with pytest.raises(net.OutboundBlocked, match='special-purpose'):     # to the metadata service: never
        net.get(f'{server}/to-metadata')
    with pytest.raises(net.OutboundError, match='redirects too often'):
        net.get(f'{server}/loop')


def test_post_does_not_follow_redirects(server, monkeypatch):
    monkeypatch.setenv('OUTBOUND_ALLOW_PRIVATE', '1')
    response = net.post(f'{server}/anything', data={'a': 'b'})
    assert response.status_code == 302


def test_the_answer_size_is_limited(server, monkeypatch):
    monkeypatch.setenv('OUTBOUND_ALLOW_PRIVATE', '1')
    assert len(net.get(f'{server}/big').content) == 200_000
    with pytest.raises(net.OutboundError, match='larger than'):
        net.get(f'{server}/big', max_bytes=1000)


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'ftp://example.com/x', 'gopher://example.com', '/relative', 'http://', ''])
def test_only_http_and_https_with_a_host(url):
    with pytest.raises(net.OutboundError):
        net.get(url)


# --- names and DNS -----------------------------------------------------------------------------


def _fake_dns(monkeypatch, *answers):
    """getaddrinfo answers with the next entry on every call; the last one repeats."""
    calls = []

    def fake(host, port, *args, **kwargs):
        addresses = answers[min(len(calls), len(answers) - 1)]
        calls.append(addresses)
        return [(socket.AF_INET6 if ':' in a else socket.AF_INET, socket.SOCK_STREAM, 6, '', (a, port)) for a in addresses]
    monkeypatch.setattr(socket, 'getaddrinfo', fake)
    return calls


def test_a_name_with_one_internal_address_is_refused(monkeypatch):
    _fake_dns(monkeypatch, ['93.184.216.34', '10.1.2.3'])
    with pytest.raises(net.OutboundBlocked, match=r'10\.1\.2\.3'):
        net.get('http://pretalx.example.com/api')


def test_a_name_that_changes_its_answer_after_the_check_is_still_refused(monkeypatch):
    """DNS rebinding: public for the check, the internal address for the connection."""
    calls = _fake_dns(monkeypatch, ['93.184.216.34'], ['127.0.0.1'])
    with pytest.raises(net.OutboundBlocked, match=r'127\.0\.0\.1'):
        net.get('http://rebind.example.com/api')
    assert len(calls) >= 2      # it was resolved again when connecting, and that answer was the one used


def test_an_unresolvable_name_is_reported_clearly(monkeypatch):
    def fail(*args, **kwargs):
        raise socket.gaierror(-2, 'Name or service not known')
    monkeypatch.setattr(socket, 'getaddrinfo', fail)
    with pytest.raises(net.OutboundError, match='could not be resolved'):
        net.get('http://no-such-host.invalid/')
