"""application/version.py: release, build revision, asset cache-busting version."""

import pytest

from application import version


@pytest.fixture(autouse=True)
def fresh_caches():
    version.release.cache_clear()
    version.revision.cache_clear()
    yield
    version.release.cache_clear()
    version.revision.cache_clear()


def test_release_comes_from_the_version_file(tmp_path, monkeypatch):
    (tmp_path / 'VERSION').write_text('2.3.4\n')
    monkeypatch.setattr(version, 'ROOT', tmp_path)
    assert version.release() == '2.3.4'


def test_release_without_a_version_file_is_a_placeholder(tmp_path, monkeypatch):
    monkeypatch.setattr(version, 'ROOT', tmp_path)
    assert version.release() == '0.0.0'


def test_the_repository_has_a_version_file():
    assert version.release() != '0.0.0'


def test_revision_prefers_the_environment_and_shortens_a_full_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(version, 'ROOT', tmp_path)
    (tmp_path / 'REVISION').write_text('filefile')
    monkeypatch.setenv('DISPLAYHIVE_REVISION', '0123456789abcdef0123456789abcdef01234567')
    assert version.revision() == '0123456'


def test_revision_falls_back_to_the_revision_file(tmp_path, monkeypatch):
    monkeypatch.setattr(version, 'ROOT', tmp_path)
    monkeypatch.delenv('DISPLAYHIVE_REVISION', raising=False)
    (tmp_path / 'REVISION').write_text('abc1234\n')
    assert version.revision() == 'abc1234'


def test_revision_is_unknown_without_any_source(tmp_path, monkeypatch):
    monkeypatch.setattr(version, 'ROOT', tmp_path)     # no .git, no REVISION
    monkeypatch.delenv('DISPLAYHIVE_REVISION', raising=False)
    assert version.revision() == 'unknown'
    assert version.display() == version.release()


def test_revision_comes_from_git_in_a_checkout(monkeypatch):
    monkeypatch.delenv('DISPLAYHIVE_REVISION', raising=False)
    revision = version.revision()
    assert revision == 'unknown' or (7 <= len(revision) <= 12 and revision.isalnum())


def test_asset_version_changes_with_the_revision(tmp_path, monkeypatch):
    monkeypatch.setattr(version, 'ROOT', tmp_path)
    (tmp_path / 'VERSION').write_text('1.0.0')
    monkeypatch.setenv('DISPLAYHIVE_REVISION', 'abc1234')
    assert version.asset_version() == '1.0.0-abc1234'
    version.revision.cache_clear()
    monkeypatch.setenv('DISPLAYHIVE_REVISION', 'def5678')
    assert version.asset_version() == '1.0.0-def5678'


def test_asset_version_without_a_revision_uses_the_screen_bundle_time(tmp_path, monkeypatch):
    monkeypatch.setattr(version, 'ROOT', tmp_path)
    monkeypatch.delenv('DISPLAYHIVE_REVISION', raising=False)
    (tmp_path / 'VERSION').write_text('1.0.0')
    assert version.asset_version() == '1.0.0'
    bundle = tmp_path / 'dist' / 'screen' / 'screen.js'
    bundle.parent.mkdir(parents=True)
    bundle.write_text('x')
    assert version.asset_version().startswith('1.0.0-') and version.asset_version() != '1.0.0'


def test_asset_version_is_url_safe(monkeypatch):
    monkeypatch.setenv('DISPLAYHIVE_REVISION', 'a b&c=d')
    assert version.asset_version().replace('.', '').replace('-', '').isalnum()


def test_app_config_carries_version_and_asset_version(flask_app):
    config = flask_app.app.config
    assert config['APP_VERSION'] == version.release()
    assert config['APP_REVISION'] == version.revision()
    assert config['ASSET_VERSION'].startswith(version.release())


def test_auth_me_returns_the_version(flask_app, db_session, make_user):
    from application.auth import create_token
    token = create_token(flask_app.app, make_user())
    body = flask_app.app.test_client().get('/admin/api/auth/me', headers={'Authorization': f'Bearer {token}'}).get_json()
    assert body['version'] == version.release() and body['revision'] == version.revision()


def test_the_screen_page_uses_the_asset_version(flask_app):
    html = flask_app.app.test_client().get('/').get_data(as_text=True)
    assert f"?v={flask_app.app.config['ASSET_VERSION']}" in html


def test_admin_connect_reports_the_version_in_the_status_event(flask_app, db_session, make_user):
    from application.auth import create_token
    client = flask_app.socketio.test_client(flask_app.app, auth={'token': create_token(flask_app.app, make_user())})
    try:
        events = [m['args'][0] for m in client.get_received() if m['name'] == 'displayhive:system:stc:security_status']
    finally:
        client.disconnect()
    assert events and events[0]['version'] == version.release() and events[0]['revision'] == version.revision()
