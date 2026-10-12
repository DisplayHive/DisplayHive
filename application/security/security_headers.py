"""Security response headers, including the Content-Security-Policy.

Three kinds of HTML documents get different policies:

* **Admin panel** (``/admin/…``) — strict: only the bundled scripts may run
  (``script-src 'self'``, no inline script, no eval). Mode via ``ADMIN_CSP``:
  ``enforce`` (default), ``report`` (Report-Only) or ``off``.
* **Preview frame** (``/admin/preview-frame.html``) — the sandboxed page the
  admin's content/design previews render in. Design HTML, raw-HTML fields and
  background effects legitimately carry inline scripts, so this one allows
  inline script. It is loaded with ``sandbox="allow-scripts"`` (opaque origin),
  so whatever runs there can't reach the admin session. Always enforced.
* **Screen page** (``/``) — Report-Only by default (``SCREEN_CSP``): designs
  and raw-HTML content can contain anything, so this only *observes* for now.

Violations are POSTed by browsers to ``/csp-report`` and logged (deduplicated,
size-limited); nothing is stored.
"""

import json
import logging
import os
from collections import OrderedDict

from flask import request

logger = logging.getLogger(__name__)

REPORT_PATH = '/csp-report'
PREVIEW_FRAME_PATH = '/admin/preview-frame.html'
_MAX_REPORT_BYTES = 32 * 1024
_SEEN_LIMIT = 500


def _policy(directives: dict) -> str:
    return '; '.join(f'{k} {v}'.strip() for k, v in directives.items())


ADMIN_POLICY = _policy({
    'default-src': "'self'",
    'script-src': "'self'",
    # PrimeVue / CodeMirror inject <style> elements and style attributes.
    'style-src': "'self' 'unsafe-inline'",
    'img-src': "'self' data: blob: https:",
    'font-src': "'self' data:",
    'media-src': "'self' data: blob:",
    'connect-src': "'self'",
    'frame-src': "'self'",
    'worker-src': "'self' blob:",
    'object-src': "'none'",
    'base-uri': "'self'",
    'form-action': "'self'",
    'frame-ancestors': "'self'",
    'report-uri': REPORT_PATH,
})

PREVIEW_POLICY = _policy({
    'default-src': "'self'",
    'script-src': "'self' 'unsafe-inline'",
    'style-src': "'self' 'unsafe-inline'",
    'img-src': "'self' data: blob: https:",
    'font-src': "'self' data: https:",
    'media-src': "'self' data: blob: https:",
    'connect-src': "'self'",
    'frame-src': "'self' https:",
    'object-src': "'none'",
    'base-uri': "'self'",
    'form-action': "'none'",
    'frame-ancestors': "'self'",
    'report-uri': REPORT_PATH,
})

SCREEN_POLICY = _policy({
    'default-src': "'self'",
    'script-src': "'self' 'unsafe-inline'",
    'style-src': "'self' 'unsafe-inline'",
    'img-src': "'self' data: blob: https:",
    'font-src': "'self' data: https:",
    'media-src': "'self' data: blob: https:",
    'connect-src': "'self'",
    'frame-src': "'self' https:",
    'object-src': "'none'",
    'base-uri': "'self'",
    'form-action': "'self'",
    'frame-ancestors': "'self'",
    'report-uri': REPORT_PATH,
})

_MODES = ('enforce', 'report', 'off')


def _mode(env_name: str, default: str) -> str:
    value = (os.environ.get(env_name) or default).strip().lower()
    return value if value in _MODES else default


def csp_for(path: str, admin_mode: str, screen_mode: str, screen_dev_server: bool):
    """(header name, policy) for an HTML response at *path*, or None."""
    if path == PREVIEW_FRAME_PATH:
        return 'Content-Security-Policy', PREVIEW_POLICY
    if path == '/admin' or path.startswith('/admin/'):
        mode = admin_mode
        policy = ADMIN_POLICY
    elif path == '/':
        # The Vite dev server serves the screen bundle from another origin.
        if screen_dev_server:
            return None
        mode = screen_mode
        policy = SCREEN_POLICY
    else:
        return None
    if mode == 'enforce':
        return 'Content-Security-Policy', policy
    if mode == 'report':
        return 'Content-Security-Policy-Report-Only', policy
    return None


def _summarize(report: dict) -> tuple:
    """(directive, blocked, document path) from either report format."""
    body = report.get('csp-report') or report.get('body') or report
    directive = body.get('effective-directive') or body.get('effectiveDirective') \
        or body.get('violated-directive') or ''
    blocked = body.get('blocked-uri') or body.get('blockedURL') or ''
    document = body.get('document-uri') or body.get('documentURL') or ''
    disposition = body.get('disposition') or ''
    return (str(directive)[:80], str(blocked)[:200], str(document)[:200], str(disposition)[:20])


def register_security_headers(app) -> None:
    """Install the after-request header hook and the /csp-report endpoint."""
    admin_mode = _mode('ADMIN_CSP', 'enforce')
    screen_mode = _mode('SCREEN_CSP', 'report')
    seen: 'OrderedDict[tuple, int]' = OrderedDict()

    @app.after_request
    def _set_security_headers(resp):
        resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
        resp.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        # camera=(self): the Devices page scans adoption QR codes with the camera.
        resp.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=(self)')
        if resp.mimetype == 'text/html':
            csp = csp_for(request.path, admin_mode, screen_mode, bool(app.config.get('SCREEN_DEV_SERVER')))
            if csp:
                resp.headers.setdefault(*csp)
        return resp

    @app.route(REPORT_PATH, methods=['POST'])
    def csp_report():
        """Log a browser's CSP violation report (no auth: browsers send these
        anonymously). Bounded in size and deduplicated so it can't flood logs."""
        if (request.content_length or 0) > _MAX_REPORT_BYTES:
            return '', 413
        try:
            payload = json.loads(request.get_data(cache=False, as_text=True) or 'null')
        except (ValueError, UnicodeDecodeError):
            return '', 400
        reports = payload if isinstance(payload, list) else [payload]
        for report in reports[:20]:
            if not isinstance(report, dict):
                continue
            key = _summarize(report)
            if key in seen:
                seen[key] += 1
                seen.move_to_end(key)
                continue
            seen[key] = 1
            if len(seen) > _SEEN_LIMIT:
                seen.popitem(last=False)
            directive, blocked, document, disposition = key
            logger.warning(
                'CSP violation%s: %s blocked %s on %s',
                ' (report-only)' if disposition == 'report' else '', directive or '?', blocked or '?', document or '?',
            )
        return '', 204

    logger.info('Content-Security-Policy: admin=%s, screen=%s', admin_mode, screen_mode)
