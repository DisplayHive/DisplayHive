"""The HTTP route table is part of the app's contract (gunicorn, the reverse
proxy, the admin SPA, installed screens). This pins it, so splitting
`app.py` into modules/blueprints can't silently drop or rename a route.

Socket.IO events are not in the URL map; they are covered by their own tests.
"""

EXPECTED_ROUTES = [
    ('/', 'GET'),
    ('/admin', 'GET'),
    ('/admin/', 'GET'),
    ('/admin/<path:filename>', 'GET'),
    ('/admin/api/auth/login', 'POST'),
    ('/admin/api/auth/me', 'GET'),
    ('/admin/api/auth/me/password', 'POST'),
    ('/admin/api/auth/me/preferences', 'PATCH'),
    ('/admin/api/auth/oidc/<slug>/callback', 'GET'),
    ('/admin/api/auth/oidc/<slug>/start', 'GET'),
    ('/admin/api/auth/oidc/exchange', 'POST'),
    ('/admin/api/auth/providers', 'GET'),
    ('/admin/api/media/upload', 'POST'),
    ('/admin/demo/import', 'POST'),
    ('/admin/demo/list', 'GET'),
    ('/admin/export/download', 'POST'),
    ('/admin/export/tree', 'GET'),
    ('/admin/import/confirm', 'POST'),
    ('/admin/import/preview', 'POST'),
    ('/apple-touch-icon.png', 'GET'),
    ('/csp-report', 'POST'),
    ('/dist/screen/<path:filename>', 'GET'),
    ('/favicon-16x16.png', 'GET'),
    ('/favicon-32x32.png', 'GET'),
    ('/favicon.ico', 'GET'),
    ('/healthz', 'GET'),
    ('/logo_bl.png', 'GET'),
    ('/logo_wh.png', 'GET'),
    ('/readyz', 'GET'),
    ('/screen/assets/<path:filename>', 'GET'),
    ('/static/<path:filename>', 'GET'),
    ('/static/media/<path:filename>', 'GET'),
    ('/static/media_previews/<path:filename>', 'GET'),
    ('/static/media_renditions/<path:filename>', 'GET'),
]


def _routes(app):
    return sorted(
        (r.rule, ','.join(sorted(r.methods - {'HEAD', 'OPTIONS'})))
        for r in app.url_map.iter_rules()
    )


def test_route_table_is_unchanged(flask_app):
    assert _routes(flask_app.app) == sorted(EXPECTED_ROUTES)


def test_no_route_is_registered_twice(flask_app):
    rules = [r.rule + ' ' + ','.join(sorted(r.methods - {'HEAD', 'OPTIONS'})) for r in flask_app.app.url_map.iter_rules()]
    assert len(rules) == len(set(rules))
