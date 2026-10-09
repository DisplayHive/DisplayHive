"""Import/export workflow pieces that need no request: upload parsing, staging,
media extraction (incl. path-traversal guard), folder wiping."""

import io
import json
import os
import stat
import time
import zipfile

import pytest

from application.admin.importexport import service


def _zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


# --- parse_import_upload ---------------------------------------------------------

def test_parse_zip_with_db_json():
    raw = _zip({'db.json': json.dumps({'export_version': 9}), 'media/a.png': b'x'})
    payload, zip_bytes = service.parse_import_upload('backup.ZIP', raw)
    assert payload == {'export_version': 9} and zip_bytes == raw


def test_parse_json():
    payload, zip_bytes = service.parse_import_upload('db.json', b'{"a": 1}')
    assert payload == {'a': 1} and zip_bytes is None


@pytest.mark.parametrize('name, raw, message', [
    ('x.zip', b'not a zip', 'Invalid ZIP file'),
    ('x.zip', _zip({'other.txt': b''}), 'ZIP does not contain db.json'),
    ('x.json', b'{broken', 'Invalid JSON'),
    ('x.txt', b'hi', 'Unsupported file type'),
    ('', b'hi', 'Unsupported file type'),
], ids=['not-a-zip', 'zip-without-db-json', 'broken-json', 'unsupported-extension', 'no-filename'])   # (a generated zip's bytes carry a timestamp: no auto ids)
def test_parse_rejects_bad_uploads(name, raw, message):
    with pytest.raises(service.ImportUploadError, match=message):
        service.parse_import_upload(name, raw)


# --- staging -----------------------------------------------------------------------

def test_stage_import_writes_private_files_and_is_found_by_token(tmp_path):
    token = service.stage_import(str(tmp_path), {'k': 'v'}, b'zipbytes')
    json_path, zip_path = service.stage_paths(str(tmp_path), token)
    assert json.load(open(json_path)) == {'k': 'v'}
    assert open(zip_path, 'rb').read() == b'zipbytes'
    for path in (json_path, zip_path):
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600   # may contain device credentials


def test_stage_paths_cannot_escape_the_staging_dir(tmp_path):
    json_path, zip_path = service.stage_paths(str(tmp_path), '../../etc/passwd')
    assert os.path.dirname(json_path) == str(tmp_path) and os.path.dirname(zip_path) == str(tmp_path)
    assert '..' not in os.path.basename(json_path) and '/' not in os.path.basename(json_path)


def test_cleanup_removes_only_stale_staged_files(tmp_path):
    old, fresh, other = (tmp_path / n for n in ('displayhive-import-old.json', 'displayhive-import-new.json', 'keep.txt'))
    for f in (old, fresh, other):
        f.write_text('x')
    past = time.time() - service.IMPORT_STAGE_MAX_AGE - 60
    os.utime(old, (past, past))
    os.utime(other, (past, past))
    service.cleanup_stale_stages(str(tmp_path))
    assert not old.exists() and fresh.exists() and other.exists()


def test_cleanup_tolerates_a_missing_directory(tmp_path):
    service.cleanup_stale_stages(str(tmp_path / 'nope'))   # must not raise


def test_apply_staged_import_returns_none_for_an_unknown_token(tmp_path):
    assert service.apply_staged_import(
        str(tmp_path), 'does-not-exist', selection=None, mode='reset', conflict_resolution='skip',
        app=None, db=None, socketio=None, media_folder=str(tmp_path), renditions_folder=str(tmp_path / 'r'),
    ) is None


# --- media folders -----------------------------------------------------------------

def test_wipe_folder_contents_keeps_the_folder_itself(tmp_path):
    media = tmp_path / 'media'
    (media / 'sub').mkdir(parents=True)
    (media / 'sub' / 'a.png').write_text('x')
    (media / 'b.png').write_text('x')
    service.wipe_folder_contents(str(media))
    assert media.is_dir() and list(media.iterdir()) == []
    service.wipe_folder_contents(str(tmp_path / 'created'))   # missing folders are created
    assert (tmp_path / 'created').is_dir()


def test_wipe_media_also_removes_the_renditions(tmp_path):
    media, rend = tmp_path / 'media', tmp_path / 'rend'
    (rend / 'fhd').mkdir(parents=True)
    (rend / 'fhd' / 'a.png').write_text('x')
    media.mkdir()
    (media / 'a.png').write_text('x')
    service.wipe_media(str(media), str(rend))
    assert list(media.iterdir()) == [] and not rend.exists()


def test_extract_all_media_blocks_path_traversal(tmp_path):
    media = tmp_path / 'media'
    media.mkdir()
    zf = zipfile.ZipFile(io.BytesIO(_zip({'media/ok.png': b'1', 'media/sub/deep.png': b'2', 'media/../evil.txt': b'3'})))
    service.extract_all_media(zf, str(media))
    assert (media / 'ok.png').read_bytes() == b'1' and (media / 'sub' / 'deep.png').read_bytes() == b'2'
    assert not (tmp_path / 'evil.txt').exists()


def test_extract_selected_media_honours_the_selection_and_traversal(tmp_path):
    media = tmp_path / 'media'
    media.mkdir()
    zf = zipfile.ZipFile(io.BytesIO(_zip({'media/a.png': b'A', 'media/b.png': b'B', 'media/../x.png': b'X'})))
    payload = {'media': [
        {'uuid': 'u-a', 'filename': 'a.png', 'folder_path': ''},
        {'uuid': 'u-b', 'filename': 'b.png', 'folder_path': ''},
        {'uuid': 'u-x', 'filename': '../x.png', 'folder_path': ''},
        {'uuid': 'u-missing', 'filename': 'gone.png', 'folder_path': ''},
    ]}
    service.extract_selected_media(zf, payload, {'media': ['u-a', 'u-x', 'u-missing']}, str(media))
    assert (media / 'a.png').exists() and not (media / 'b.png').exists()   # b not selected
    assert not (tmp_path / 'x.png').exists()                                # traversal refused
    service.extract_selected_media(zf, payload, None, str(media))           # no selection = everything present
    assert (media / 'b.png').exists()


def test_export_filename_is_timestamped():
    from datetime import datetime, timezone
    assert service.export_filename(datetime(2026, 10, 7, 12, 30, 5, tzinfo=timezone.utc)) == \
        'displayhive-export-2026-10-07T12-30-05.zip'
