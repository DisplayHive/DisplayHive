"""The admin side of icon libraries: socket handlers (Settings card), the upload route, serving."""

import io
import os
import time
import zipfile

import pytest

from application import icon_libraries as icons
from application.auth import create_token
from tests.test_admin_actions import plain_client, superadmin_client  # noqa: F401  (fixtures)
from tests.test_icon_libraries import SVG, _zip

GET = 'displayhive:admin:cts:get_icon_libraries'
INSTALL = 'displayhive:admin:cts:install_icon_library'
INSTALL_ALL = 'displayhive:admin:cts:install_all_icon_libraries'
INSTALL_URL = 'displayhive:admin:cts:install_icon_library_url'
REMOVE = 'displayhive:admin:cts:remove_icon_library'


def _ack(client, event, data=None):
    return client.emit(event, data, callback=True)


@pytest.fixture()
def icons_dir(flask_app, tmp_path, monkeypatch):
    folder = str(tmp_path / 'icons')
    monkeypatch.setitem(flask_app.app.config, 'ICON_LIBRARIES_FOLDER', folder)
    yield folder


def _wait_idle(client, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = _ack(client, GET)
        if not state['job']['running']:
            return state
        time.sleep(0.05)
    raise AssertionError('the installation did not finish')


def test_the_card_lists_the_known_libraries(superadmin_client, icons_dir):
    state = _ack(superadmin_client, GET)
    assert state['success'] and [c['id'] for c in state['catalog']][:2] == ['lucide', 'heroicons']
    assert all(not c['installed'] for c in state['catalog']) and state['custom'] == []


def test_installing_needs_the_right(plain_client, icons_dir):
    assert _ack(plain_client, GET)['success'] is False
    for event, payload in ((INSTALL, {'id': 'lucide'}), (INSTALL_ALL, None), (REMOVE, {'id': 'lucide'})):
        assert _ack(plain_client, event, payload) == {'success': False, 'error': 'Permission denied'}


def test_install_from_the_catalog_in_the_background(superadmin_client, icons_dir, monkeypatch):
    monkeypatch.setattr(icons, 'install_from_catalog', lambda folder, library_id: icons.install(
        folder, library_id, _zip({'a.svg': SVG, 'b.svg': SVG}), label=library_id, source='catalog'))
    assert _ack(superadmin_client, INSTALL, {'id': 'lucide'}) == {'success': True}
    state = _wait_idle(superadmin_client)
    lucide = next(c for c in state['catalog'] if c['id'] == 'lucide')
    assert lucide['installed'] and lucide['count'] == 2
    pushes = [m for m in superadmin_client.get_received() if m['name'] == 'displayhive:admin:stc:icon_libraries']
    assert pushes, 'every admin is told when the state changes'
    assert os.path.isfile(os.path.join(icons_dir, 'lucide', 'a.svg'))


def test_a_failing_download_is_reported_not_raised(superadmin_client, icons_dir, monkeypatch):
    def boom(folder, library_id):
        raise icons.IconLibraryError('The download failed: the server answered 503.')
    monkeypatch.setattr(icons, 'install_from_catalog', boom)
    assert _ack(superadmin_client, INSTALL, {'id': 'tabler'})['success']
    state = _wait_idle(superadmin_client)
    assert state['job']['errors'] == {'tabler': 'The download failed: the server answered 503.'}
    assert not next(c for c in state['catalog'] if c['id'] == 'tabler')['installed']


def test_install_all_skips_what_is_installed(superadmin_client, icons_dir, monkeypatch):
    seen = []
    monkeypatch.setattr(icons, 'install_from_catalog', lambda folder, library_id: seen.append(library_id) or icons.install(
        folder, library_id, _zip({'a.svg': SVG}), label=library_id))
    icons.install(icons_dir, 'lucide', _zip({'x.svg': SVG}), label='Lucide')
    assert _ack(superadmin_client, INSTALL_ALL) == {'success': True, 'queued': 8}
    _wait_idle(superadmin_client)
    assert 'lucide' not in seen and len(seen) == 8
    assert _ack(superadmin_client, INSTALL_ALL) == {'success': False, 'error': 'All known libraries are installed.'}


def test_unknown_library_and_bad_custom_input(superadmin_client, icons_dir):
    assert _ack(superadmin_client, INSTALL, {'id': 'nope'}) == {'success': False, 'error': 'Unknown library.'}
    bad_id = _ack(superadmin_client, INSTALL_URL, {'id': 'Bad Id', 'label': 'x', 'license': '', 'url': 'https://e.org/a.zip'})
    assert bad_id['success'] is False and 'lowercase' in bad_id['error']
    no_url = _ack(superadmin_client, INSTALL_URL, {'id': 'ok-id', 'label': 'x', 'license': '', 'url': ' '})
    assert no_url['success'] is False


def test_install_from_a_link_shows_up_as_own_library_and_can_be_removed(superadmin_client, icons_dir, monkeypatch):
    monkeypatch.setattr(icons, 'download', lambda url, max_bytes=0: _zip({'z.svg': SVG}))
    assert _ack(superadmin_client, INSTALL_URL, {'id': 'mine', 'label': 'Mine', 'license': 'CC0', 'url': 'https://e.org/a.zip'})['success']
    state = _wait_idle(superadmin_client)
    assert [c['id'] for c in state['custom']] == ['mine'] and state['custom'][0]['license'] == 'CC0'
    assert _ack(superadmin_client, REMOVE, {'id': 'mine'})['success']
    assert _ack(superadmin_client, GET)['custom'] == []
    assert _ack(superadmin_client, REMOVE, {'id': 'mine'})['success'] is False


# --- upload route and serving ----------------------------------------------------------------

@pytest.fixture()
def uploader(flask_app, db_session, make_user, make_group):
    from application.models import UserGroup
    user = make_user()
    group = make_group(is_superadmin=True)
    db_session.add(UserGroup(user_id=user.id, group_id=group.id))
    db_session.commit()
    return flask_app.app.test_client(), {'Authorization': f'Bearer {create_token(flask_app.app, user)}'}


def _post(client, headers, files=None, **form):
    data = dict(form)
    if files is not None:
        data['file'] = (io.BytesIO(files), 'icons.zip')
    return client.post('/admin/api/icons/upload', data=data, headers=headers, content_type='multipart/form-data')


def test_upload_installs_and_the_files_are_served(uploader, icons_dir, flask_app):
    client, headers = uploader
    response = _post(client, headers, _zip({'set/home.svg': SVG}), id='uploaded', label='Uploaded', license='MIT')
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['library']['count'] == 1
    served = client.get('/static/icons/uploaded/home.svg')
    assert served.status_code == 200 and served.mimetype == 'image/svg+xml'
    assert "sandbox" in served.headers['Content-Security-Policy']
    manifest = client.get('/static/icons/manifest.json')
    assert manifest.get_json() == {'uploaded': ['home']} and manifest.headers['Cache-Control'] == 'no-cache'
    assert client.get('/static/icons/uploaded/missing.svg').status_code == 404
    assert client.get('/static/icons/../manifest.json').status_code in (308, 404)


def test_upload_problems(uploader, icons_dir):
    client, headers = uploader
    assert _post(client, headers, None, id='x', label='x').status_code == 400
    bad = _post(client, headers, _zip({'a.txt': 'x'}), id='x', label='x')
    assert bad.status_code == 400 and 'No usable' in bad.get_json()['error']
    assert _post(client, headers, _zip({'a.svg': SVG}), id='Bad Id', label='x').status_code == 400
    assert client.post('/admin/api/icons/upload', data={}, content_type='multipart/form-data').status_code in (401, 403)


def test_upload_needs_the_right(flask_app, db_session, make_user, icons_dir):
    user = make_user()
    client = flask_app.app.test_client()
    headers = {'Authorization': f'Bearer {create_token(flask_app.app, user)}'}
    assert _post(client, headers, _zip({'a.svg': SVG}), id='x', label='x').status_code == 401
