"""Tests for application/paths.py (DATA_DIR resolution, legacy fallback,
directory permissions) and the /static/media* routes that serve from it."""

import os
import stat

import pytest

from application import paths


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


@pytest.fixture()
def roots(tmp_path):
    app_root = tmp_path / 'app'
    data_dir = tmp_path / 'data'
    app_root.mkdir()
    return app_root, data_dir


def _resolve(roots, **env):
    app_root, data_dir = roots
    return paths.resolve({'DATA_DIR': str(data_dir), **env}, app_root=str(app_root))


def test_fresh_install_uses_data_dir_for_everything(roots):
    app_root, data_dir = roots
    p = _resolve(roots)
    assert p.media == str(data_dir / 'media')
    assert p.media_previews == str(data_dir / 'media_previews')
    assert p.media_renditions == str(data_dir / 'media_renditions')
    assert p.import_staging == str(data_dir / 'import-staging')
    assert p.db_path == str(data_dir / 'db' / 'project.db')
    assert p.legacy == []


def test_default_data_dir_is_inside_the_app_root(roots):
    app_root, _ = roots
    p = paths.resolve({}, app_root=str(app_root))
    assert p.data_dir == str(app_root / 'data')


def test_legacy_media_with_files_keeps_being_used(roots):
    app_root, _ = roots
    legacy = app_root / 'static' / 'media'
    legacy.mkdir(parents=True)
    (legacy / 'logo.png').write_bytes(b'x')
    (app_root / 'static' / 'media_previews').mkdir()  # empty: not "in use"
    p = _resolve(roots)
    assert p.media == str(legacy)
    assert p.media_previews.endswith(os.path.join('data', 'media_previews'))
    assert p.legacy == [{'kind': 'media', 'path': str(legacy)}]


def test_new_location_wins_once_it_has_data(roots):
    app_root, data_dir = roots
    (app_root / 'static' / 'media').mkdir(parents=True)
    (app_root / 'static' / 'media' / 'old.png').write_bytes(b'x')
    (data_dir / 'media').mkdir(parents=True)
    (data_dir / 'media' / 'new.png').write_bytes(b'x')
    p = _resolve(roots)
    assert p.media == str(data_dir / 'media')
    assert p.legacy == []


def test_database_resolution(roots):
    app_root, data_dir = roots
    (app_root / 'project.db').write_bytes(b'')
    p = _resolve(roots)
    assert p.db_path == str(app_root / 'project.db')
    assert {'kind': 'database', 'path': str(app_root / 'project.db')} in p.legacy

    assert _resolve(roots, DATABASE_URL='postgresql://x/y').db_path is None
    assert _resolve(roots, TEST_DB_PATH='/tmp/x.db').db_path == '/tmp/x.db'


def test_ensure_dirs_creates_tight_permissions_but_leaves_existing_ones(roots):
    app_root, data_dir = roots
    (data_dir / 'media').mkdir(parents=True)
    os.chmod(data_dir / 'media', 0o755)  # admin's own choice
    os.chmod(data_dir, 0o755)
    p = _resolve(roots)
    paths.ensure_dirs(p)
    assert _mode(data_dir) == 0o755
    assert _mode(data_dir / 'media') == 0o755
    assert _mode(data_dir / 'media_previews') == 0o750
    assert _mode(data_dir / 'import-staging') == 0o700
    assert _mode(data_dir / 'db') == 0o700


def test_ensure_dirs_warns_about_a_readable_database(roots, caplog):
    app_root, data_dir = roots
    p = _resolve(roots)
    paths.ensure_dirs(p)
    with open(p.db_path, 'wb'):
        pass
    os.chmod(p.db_path, 0o644)
    paths.ensure_dirs(p)
    # Inside the 0700 db/ directory nobody else can reach it.
    assert 'readable by other users' not in caplog.text
    os.chmod(os.path.dirname(p.db_path), 0o755)
    paths.ensure_dirs(p)
    assert 'readable by other users' in caplog.text


@pytest.mark.parametrize('value, expected', [
    ('docker', 'docker'), ('NixOS', 'nixos'), ('', 'manual'), ('kubernetes', 'manual'),
])
def test_deployment_kind(value, expected):
    assert paths.deployment_kind({'DISPLAYHIVE_DEPLOYMENT': value}) == expected


# --- Serving ------------------------------------------------------------------


def test_media_urls_are_served_from_data_dir(flask_app):
    media_dir = flask_app.DATA_PATHS.media
    with open(os.path.join(media_dir, 'pytest-served.txt'), 'w') as f:
        f.write('hello')
    try:
        client = flask_app.app.test_client()
        response = client.get('/static/media/pytest-served.txt')
        assert response.status_code == 200
        assert response.data == b'hello'
        # No escaping into the rest of DATA_DIR (e.g. the SQLite file in db/).
        assert client.get('/static/media/../db/project.db').status_code == 404
        assert client.get('/static/media/%2e%2e/import-staging/x').status_code == 404
    finally:
        os.remove(os.path.join(media_dir, 'pytest-served.txt'))


def test_media_routes_take_precedence_over_the_static_folder(flask_app):
    adapter = flask_app.app.url_map.bind('localhost')
    assert adapter.match('/static/media/a/b.png')[0] == 'static_media'
    assert adapter.match('/static/media_previews/a.png')[0] == 'static_media_previews'
    assert adapter.match('/static/media_renditions/fhd/a.png')[0] == 'static_media_renditions'
    assert adapter.match('/static/js-build/app.js')[0] == 'static'
