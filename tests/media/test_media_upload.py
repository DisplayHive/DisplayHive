"""Tests for the HTTP media upload (application/admin/media/routes.py + storage.py):
multipart streamed into DATA_DIR's staging directory, validated, then
hard-linked into the media folder."""

import io
import os
import stat

import pytest
from PIL import Image

from application.admin.media import storage
from application.auth import create_token


def _png_bytes(size=(64, 32), fmt='PNG'):
    buf = io.BytesIO()
    Image.new('RGB', size, (10, 120, 200)).save(buf, fmt)
    return buf.getvalue()


@pytest.fixture()
def uploader(flask_app, db_session, make_user):
    """(test client, auth headers) for a Superadmin."""
    from application.models import Group, UserGroup
    user = make_user()
    group = db_session.query(Group).filter_by(is_superadmin=True).one()
    db_session.add(UserGroup(user_id=user.id, group_id=group.id))
    db_session.commit()
    return flask_app.app.test_client(), {'Authorization': f'Bearer {create_token(flask_app.app, user)}'}


@pytest.fixture()
def cleanup(flask_app):
    """Remove whatever the test wrote into the (shared, per-run) media folders."""
    created = []
    yield created
    config = flask_app.app.config
    for rel in created:
        for root in (config['MEDIA_FOLDER'],):
            path = os.path.join(root, rel)
            if os.path.exists(path):
                os.remove(path)
        from application import media_renditions
        preview = media_renditions.preview_path(config['PREVIEW_FOLDER'], rel)
        if os.path.exists(preview):
            os.remove(preview)
        media_renditions.remove_renditions(config['MEDIA_RENDITIONS_FOLDER'], rel)


def _upload(client, headers, data=None, filename='photo.png', **fields):
    payload = {'file': (io.BytesIO(data if data is not None else _png_bytes()), filename), **fields}
    return client.post('/admin/api/media/upload', data=payload, headers=headers, content_type='multipart/form-data')


def _staging_files(flask_app):
    staging = flask_app.app.config['UPLOAD_STAGING_DIR']
    return [n for n in os.listdir(staging) if n.startswith('upload-')]


def test_upload_stores_file_preview_and_row(flask_app, db_session, uploader, cleanup):
    from application.models import Media
    from application import media_renditions

    client, headers = uploader
    response = _upload(client, headers, title='Hello', tags='a,b')
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    cleanup.append(result['filename'])

    config = flask_app.app.config
    stored = os.path.join(config['MEDIA_FOLDER'], result['filename'])
    assert open(stored, 'rb').read() == _png_bytes()
    # Not the staging file's private 0600: what a normal write would give.
    assert stat.S_IMODE(os.stat(stored).st_mode) == 0o666 & ~storage._UMASK
    assert os.path.exists(media_renditions.preview_path(config['PREVIEW_FOLDER'], result['filename']))
    media = db_session.get(Media, result['id'])
    assert (media.title, media.tags, media.mime_type) == ('Hello', 'a,b', 'image/png')
    assert media.file_size == len(_png_bytes())
    # The staged temp file is gone once the request has finished.
    assert _staging_files(flask_app) == []


def test_upload_is_streamed_into_the_staging_dir(flask_app, uploader, monkeypatch, cleanup):
    seen = {}
    original = storage.ingest_upload

    def spy(db, config, staged_path, **kwargs):
        seen['path'] = staged_path
        media = original(db, config, staged_path, **kwargs)
        cleanup.append(media.filename)
        return media

    monkeypatch.setattr(storage, 'ingest_upload', spy)
    client, headers = uploader
    assert _upload(client, headers).status_code == 200
    staging = os.path.realpath(flask_app.app.config['UPLOAD_STAGING_DIR'])
    assert os.path.dirname(os.path.realpath(seen['path'])) == staging


def test_name_collision_gets_a_suffix(uploader, cleanup):
    client, headers = uploader
    first = _upload(client, headers, filename='same.png').get_json()
    second = _upload(client, headers, filename='same.png').get_json()
    cleanup += [first['filename'], second['filename']]
    assert first['filename'] == 'same.png'
    assert second['filename'] == 'same_1.png'


@pytest.mark.parametrize('data, filename, message', [
    (b'not an image at all', 'fake.png', 'not a valid image'),
    (_png_bytes(fmt='GIF'), 'renamed.png', 'not a supported image'),
    (_png_bytes(), 'photo.gif', 'File type not allowed'),
])
def test_invalid_files_are_rejected(flask_app, uploader, data, filename, message):
    client, headers = uploader
    response = _upload(client, headers, data=data, filename=filename)
    assert response.status_code == 400
    assert message in response.get_json()['error']
    assert not os.path.exists(os.path.join(flask_app.app.config['MEDIA_FOLDER'], filename))
    assert _staging_files(flask_app) == []


def test_path_traversal_in_folder_is_rejected(uploader):
    client, headers = uploader
    response = _upload(client, headers, folder='../../etc')
    assert response.status_code == 400
    assert response.get_json()['error'] == 'Invalid folder path'


def test_too_large(flask_app, uploader, monkeypatch):
    monkeypatch.setattr(storage, 'MAX_FILE_SIZE', 100)
    client, headers = uploader
    response = _upload(client, headers)
    assert response.status_code == 413
    assert 'too large' in response.get_json()['error']


def test_too_large_body_is_refused_before_reading(flask_app, uploader, monkeypatch):
    """Content-Length beyond the limit + multipart overhead never gets parsed."""
    from application.admin.media import routes
    monkeypatch.setattr(storage, 'MAX_FILE_SIZE', 10)
    monkeypatch.setattr(routes, '_MULTIPART_OVERHEAD', 10)
    client, headers = uploader
    response = _upload(client, headers, data=b'x' * 5000)
    assert response.status_code == 413
    assert _staging_files(flask_app) == []


def test_upload_needs_login_and_right(flask_app, db_session, make_user):
    client = flask_app.app.test_client()
    assert _upload(client, {}).status_code == 401
    nobody = make_user()  # no groups, no rights
    headers = {'Authorization': f'Bearer {create_token(flask_app.app, nobody)}'}
    assert _upload(client, headers).status_code == 401


def test_missing_file_part(uploader):
    client, headers = uploader
    response = client.post('/admin/api/media/upload', data={'title': 'x'}, headers=headers,
                           content_type='multipart/form-data')
    assert response.status_code == 400
    assert response.get_json()['error'] == 'No file provided'
