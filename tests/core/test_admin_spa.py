"""The admin SPA route (application/web/admin_spa.py): only a missing file is a 404."""

import pytest

from application.web import admin_spa


@pytest.fixture()
def dist(tmp_path, monkeypatch):
    (tmp_path / 'index.html').write_text('<html>admin</html>')
    (tmp_path / 'app.js').write_text('console.log(1)')
    monkeypatch.setattr(admin_spa, '_DIST_ADMIN', str(tmp_path))
    return tmp_path


def test_files_and_client_side_routes_are_served(flask_app, dist):
    client = flask_app.app.test_client()
    assert client.get('/admin/').status_code == 200
    assert client.get('/admin/app.js').status_code == 200
    assert b'admin' in client.get('/admin/some/client/route').data     # index.html for the SPA router


def test_a_missing_asset_is_a_404(flask_app, dist):
    assert flask_app.app.test_client().get('/admin/missing.js').status_code == 404


def test_a_real_error_is_not_turned_into_a_404(flask_app, dist, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError('disk exploded')

    monkeypatch.setattr(admin_spa, 'send_from_directory', broken)
    response = flask_app.app.test_client().get('/admin/app.js')
    assert response.status_code == 500
