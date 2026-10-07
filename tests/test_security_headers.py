"""Security headers and Content-Security-Policy per page type, plus /csp-report."""

import json

import pytest

from application.security_headers import (
    ADMIN_POLICY, PREVIEW_FRAME_PATH, PREVIEW_POLICY, SCREEN_POLICY, csp_for,
)


@pytest.fixture()
def client(flask_app):
    return flask_app.app.test_client()


def _directives(policy: str) -> dict:
    out = {}
    for part in policy.split(';'):
        name, _, value = part.strip().partition(' ')
        out[name] = value
    return out


# --- policy choice per page --------------------------------------------------------

def test_admin_is_enforced_and_strict_by_default():
    header, policy = csp_for('/admin/', 'enforce', 'report', False)
    assert header == 'Content-Security-Policy'
    d = _directives(policy)
    assert d['script-src'] == "'self'"          # no inline script, no eval
    assert d['object-src'] == "'none'"
    assert d['frame-ancestors'] == "'self'"
    assert 'unsafe-inline' not in d['script-src']


def test_preview_frame_allows_inline_script_and_is_always_enforced():
    for admin_mode in ('enforce', 'report', 'off'):
        header, policy = csp_for(PREVIEW_FRAME_PATH, admin_mode, 'off', False)
        assert header == 'Content-Security-Policy'
        assert "'unsafe-inline'" in _directives(policy)['script-src']


def test_screen_is_report_only_by_default_and_skipped_with_dev_server():
    assert csp_for('/', 'enforce', 'report', False) == ('Content-Security-Policy-Report-Only', SCREEN_POLICY)
    assert csp_for('/', 'enforce', 'enforce', False) == ('Content-Security-Policy', SCREEN_POLICY)
    assert csp_for('/', 'enforce', 'report', True) is None


def test_modes_can_be_switched_off_or_to_report_only():
    assert csp_for('/admin/', 'off', 'report', False) is None
    assert csp_for('/admin/x', 'report', 'report', False) == ('Content-Security-Policy-Report-Only', ADMIN_POLICY)
    assert csp_for('/screen/assets/x.css', 'enforce', 'enforce', False) is None


def test_all_policies_report_violations():
    for policy in (ADMIN_POLICY, PREVIEW_POLICY, SCREEN_POLICY):
        assert _directives(policy)['report-uri'] == '/csp-report'


# --- real responses ------------------------------------------------------------------

def test_admin_html_response_carries_the_csp(client):
    resp = client.get('/admin/')
    assert resp.mimetype == 'text/html'
    assert resp.headers['Content-Security-Policy'] == ADMIN_POLICY


def test_preview_frame_response_carries_the_relaxed_policy(client):
    resp = client.get(PREVIEW_FRAME_PATH)
    assert resp.headers['Content-Security-Policy'] == PREVIEW_POLICY


def test_screen_page_is_report_only(client):
    resp = client.get('/')
    assert resp.headers.get('Content-Security-Policy-Report-Only') == SCREEN_POLICY
    assert 'Content-Security-Policy' not in resp.headers


def test_baseline_headers_and_camera_for_self(client):
    resp = client.get('/admin/')
    assert resp.headers['X-Content-Type-Options'] == 'nosniff'
    assert resp.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert 'camera=(self)' in resp.headers['Permissions-Policy']


# --- /csp-report ---------------------------------------------------------------------

def test_csp_report_accepts_both_report_formats(client, caplog):
    classic = {'csp-report': {'document-uri': 'https://x/admin/', 'effective-directive': 'script-src-elem',
                              'blocked-uri': 'inline', 'disposition': 'enforce'}}
    reporting_api = [{'type': 'csp-violation', 'body': {'documentURL': 'https://x/', 'effectiveDirective': 'img-src',
                                                        'blockedURL': 'https://evil.example/p.png',
                                                        'disposition': 'report'}}]
    with caplog.at_level('WARNING'):
        assert client.post('/csp-report', data=json.dumps(classic), content_type='application/csp-report').status_code == 204
        assert client.post('/csp-report', data=json.dumps(reporting_api), content_type='application/reports+json').status_code == 204
    text = caplog.text
    assert 'script-src-elem blocked inline' in text
    assert 'img-src blocked https://evil.example/p.png' in text and '(report-only)' in text


def test_csp_report_is_deduplicated(client, caplog):
    report = {'csp-report': {'document-uri': 'https://x/dedupe', 'effective-directive': 'font-src',
                             'blocked-uri': 'https://fonts.example/a.woff2'}}
    with caplog.at_level('WARNING'):
        for _ in range(3):
            client.post('/csp-report', data=json.dumps(report), content_type='application/csp-report')
    assert caplog.text.count('https://fonts.example/a.woff2') == 1


def test_csp_report_rejects_garbage_and_oversized_bodies(client):
    assert client.post('/csp-report', data='not json', content_type='application/csp-report').status_code == 400
    big = json.dumps({'csp-report': {'blocked-uri': 'x' * 40000}})
    assert client.post('/csp-report', data=big, content_type='application/csp-report').status_code == 413
