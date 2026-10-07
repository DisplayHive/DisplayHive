"""The import/export workflow behind the /admin/export, /admin/import and
/admin/demo routes (application/web/importexport_routes.py).

Everything here is plain Python — no request, no Flask routing — so it can be
tested directly and reused. The routes only authenticate, read the request and
turn the results into responses.

Two flows share most steps:

* **Selective import**, two-step: a preview parses an uploaded file and stages
  it under a random token (so the payload needn't round-trip through the
  browser again); confirm loads the staged payload, applies the chosen
  selection/mode and restores the matching media files.
* **Demo import**: always a full reset from a bundled package.
"""

import io
import json
import logging
import os
import secrets
import shutil
import time
import zipfile
from datetime import datetime, timezone
from typing import Optional

from application import media_renditions

logger = logging.getLogger(__name__)

IMPORT_STAGE_MAX_AGE = 3600  # seconds a staged upload is kept
_STAGE_PREFIX = 'displayhive-import-'


class ImportUploadError(ValueError):
    """The uploaded import file is unusable; the message is shown to the user."""


# --- Demo mode ---------------------------------------------------------------------

def demo_mode_hidden(db) -> bool:
    """Whether the 'hide_demo_mode' system setting is enabled.

    When enabled, Demo Mode must be unreachable through the API too — not just
    hidden in the nav — so the /admin/demo/* routes check this and 404 rather
    than relying on the frontend alone to hide the page.
    """
    from application.models import SystemSetting
    row = db.session.execute(
        db.select(SystemSetting).where(SystemSetting.key == 'hide_demo_mode')
    ).scalar_one_or_none()
    return row is not None and row.value == 'true'


def load_demo_catalog(desc_path: str) -> Optional[list]:
    """The demo packages described in exampledesc.json, or None if it's missing."""
    if not os.path.isfile(desc_path):
        return None
    with open(desc_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# --- Media folder helpers ----------------------------------------------------------

def wipe_folder_contents(folder: str) -> None:
    """Delete everything inside *folder* (creating it if needed).

    shutil.rmtree on the folder itself fails when it is a Docker volume mount
    point (EBUSY), so only its contents are removed.
    """
    if os.path.isdir(folder):
        for entry in os.scandir(folder):
            if entry.is_dir(follow_symlinks=False):
                shutil.rmtree(entry.path)
            else:
                os.remove(entry.path)
    os.makedirs(folder, exist_ok=True)


def wipe_media(media_folder: str, renditions_folder: str) -> None:
    """Empty the media folder; the renditions derived from it go with it."""
    wipe_folder_contents(media_folder)
    if os.path.isdir(renditions_folder):
        shutil.rmtree(renditions_folder, ignore_errors=True)


def _safe_target(media_folder: str, rel: str) -> Optional[str]:
    """The path for *rel* inside *media_folder*, or None if it would escape it."""
    target = os.path.join(media_folder, rel)
    root = os.path.realpath(media_folder)
    if not os.path.realpath(target).startswith(root + os.sep):
        return None
    return target


def _write_member(zf: zipfile.ZipFile, name: str, target: str) -> None:
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with zf.open(name) as src, open(target, 'wb') as dst:
        dst.write(src.read())


def extract_all_media(zf: zipfile.ZipFile, media_folder: str) -> None:
    """Restore every file under ``media/`` in the archive."""
    for name in zf.namelist():
        if name.startswith('media/') and not name.endswith('/'):
            target = _safe_target(media_folder, name[len('media/'):])
            if target:
                _write_member(zf, name, target)


def extract_selected_media(zf: zipfile.ZipFile, db_payload: dict, selection: Optional[dict],
                           media_folder: str) -> None:
    """Restore the media files of the payload's Media rows (all, or just the
    selected uuids when *selection* has a ``media`` list)."""
    selected = set(selection.get('media') or []) if selection is not None else None
    names = set(zf.namelist())
    for row in db_payload.get('media', []):
        if selected is not None and row.get('uuid') not in selected:
            continue
        rel = os.path.join(row.get('folder_path') or '', row['filename'])
        arcname = 'media/' + rel.replace(os.sep, '/')
        if arcname not in names:
            continue
        target = _safe_target(media_folder, rel)
        if target:
            _write_member(zf, arcname, target)


# --- After an import ---------------------------------------------------------------

def broadcast_import_update(socketio, app, db) -> None:
    """Notify already-connected admin tabs and screen clients that the database
    was just replaced/merged via import, so they refetch instead of continuing
    to show stale in-memory state.

    Admin tabs: re-emit the same list broadcasts used after normal
    layout/container/contenttype/content edits, to the whole 'admins' room.
    Screens: force every connected device to hard-reload, which re-runs its
    normal connect-time upd_content flow and picks up everything fresh.
    """
    from application.admin.layouts.helper import emit_layouts_update, emit_containers_update
    from application.admin.contenttypes.helper import emit_contenttypes_update
    from application.admin.content.queries import emit_all_content_element
    from application.utils import reload_devices_on_all_screens

    try:
        emit_layouts_update(socketio, app, db, room='admins')
        emit_containers_update(socketio, app, db, room='admins')
        emit_contenttypes_update(socketio, app, db, room='admins')
        emit_all_content_element(socketio, db, room='admins')
    except Exception:
        logger.exception('Error broadcasting admin update after import')
    try:
        reload_devices_on_all_screens(socketio, db)
    except Exception:
        logger.exception('Error reloading screens after import')


def _finish_import(result: dict, *, app, db, socketio, media_folder: str, renditions_folder: str) -> dict:
    """Common tail of every import: tell clients, and render the imported
    images' FHD/4K/8K renditions."""
    if result.get('success'):
        broadcast_import_update(socketio, app, db)
        media_renditions.schedule_backfill(socketio, app, db, media_folder, renditions_folder)
    return result


def restore_from_zip_bytes(raw: bytes, *, app, db, socketio, media_folder: str, renditions_folder: str) -> dict:
    """Replace the media folder + database from an export-format ZIP's bytes.

    Used by the demo importer, which always does a full reset: pull db.json out
    of the zip, wipe the media folder and restore any files it contains, then
    run import_database with selection=None, mode='reset'.
    """
    from application.admin.importexport.helper import import_database

    with zipfile.ZipFile(io.BytesIO(raw), 'r') as zf:
        if 'db.json' not in zf.namelist():
            return {'success': False, 'error': 'ZIP does not contain db.json'}
        db_payload = json.loads(zf.read('db.json').decode('utf-8'))
        wipe_media(media_folder, renditions_folder)
        extract_all_media(zf, media_folder)

    result = import_database(app, db, db_payload, selection=None, mode='reset')
    return _finish_import(result, app=app, db=db, socketio=socketio,
                          media_folder=media_folder, renditions_folder=renditions_folder)


# --- Export ------------------------------------------------------------------------

def build_export_zip(app, db, selection: Optional[dict], media_folder: str) -> io.BytesIO:
    """A ZIP with db.json plus the matching media files for the selected
    entities (selection None = everything), ready to stream."""
    from application.admin.importexport.helper import export_database

    export_data = export_database(app, db, selection)

    # With a selection, only bundle media files that belong to the
    # (dependency-resolved) selected Media rows — export_data['media'] already
    # reflects that resolution.
    selected_rel_paths = None
    if selection is not None:
        selected_rel_paths = {
            os.path.join(m.get('folder_path') or '', m['filename']).replace(os.sep, '/')
            for m in export_data.get('media', [])
        }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('db.json', json.dumps(export_data, indent=2))
        if os.path.isdir(media_folder):
            for root, _dirs, files in os.walk(media_folder):
                for fname in files:
                    abs_path = os.path.join(root, fname)
                    rel = os.path.relpath(abs_path, media_folder)
                    if selected_rel_paths is not None and rel.replace(os.sep, '/') not in selected_rel_paths:
                        continue
                    zf.write(abs_path, os.path.join('media', rel))
    buf.seek(0)
    return buf


def export_filename(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f'displayhive-export-{now.strftime("%Y-%m-%dT%H-%M-%S")}.zip'


# --- Selective import: staging -----------------------------------------------------

def parse_import_upload(filename: str, raw: bytes) -> tuple:
    """Read an uploaded ``.zip`` (with db.json) or ``.json`` export.

    Returns ``(db_payload, zip_bytes_or_None)``; raises ImportUploadError with a
    user-facing message otherwise.
    """
    lower = (filename or '').lower()
    if lower.endswith('.zip'):
        try:
            with zipfile.ZipFile(io.BytesIO(raw), 'r') as zf:
                if 'db.json' not in zf.namelist():
                    raise ImportUploadError('ZIP does not contain db.json')
                return json.loads(zf.read('db.json').decode('utf-8')), raw
        except zipfile.BadZipFile:
            raise ImportUploadError('Invalid ZIP file') from None
    if lower.endswith('.json'):
        try:
            return json.loads(raw.decode('utf-8')), None
        except Exception as exc:
            raise ImportUploadError(f'Invalid JSON: {exc}') from exc
    raise ImportUploadError('Unsupported file type — upload a .zip or .json file')


def stage_paths(stage_dir: str, token: str) -> tuple:
    """(json path, zip path) of a staged import. The token is reduced to safe
    characters so it can't point outside *stage_dir*."""
    safe = ''.join(c for c in (token or '') if c.isalnum() or c == '-')
    return (
        os.path.join(stage_dir, f'{_STAGE_PREFIX}{safe}.json'),
        os.path.join(stage_dir, f'{_STAGE_PREFIX}{safe}.zip'),
    )


def _open_stage_file(path: str, binary: bool):
    """Create a staged-import file with owner-only permissions (0600).

    Staged imports can include Device credentials (devicekey /
    registration_token). The staging directory itself is 0700 already; this
    keeps the files private too, should someone loosen the directory's
    permissions or point DATA_DIR at a shared location.
    """
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    return os.fdopen(fd, 'wb' if binary else 'w', encoding=None if binary else 'utf-8')


def stage_import(stage_dir: str, db_payload: dict, zip_bytes: Optional[bytes]) -> str:
    """Store a parsed upload under a fresh random token and return the token."""
    token = secrets.token_urlsafe(24)
    json_path, zip_path = stage_paths(stage_dir, token)
    with _open_stage_file(json_path, binary=False) as f:
        json.dump(db_payload, f)
    if zip_bytes is not None:
        with _open_stage_file(zip_path, binary=True) as f:
            f.write(zip_bytes)
    return token


def cleanup_stale_stages(stage_dir: str, max_age: int = IMPORT_STAGE_MAX_AGE) -> None:
    """Best-effort delete of staged import files older than *max_age* seconds."""
    try:
        now = time.time()
        for name in os.listdir(stage_dir):
            if not name.startswith(_STAGE_PREFIX):
                continue
            path = os.path.join(stage_dir, name)
            try:
                if now - os.path.getmtime(path) > max_age:
                    os.remove(path)
            except OSError:
                pass
    except OSError:
        pass


def apply_staged_import(stage_dir: str, token: str, *, selection, mode: str, conflict_resolution: str,
                        app, db, socketio, media_folder: str, renditions_folder: str) -> Optional[dict]:
    """Finish a staged import: apply the selection/mode/conflict resolution,
    restore matching media files, then discard the staged upload.

    Returns the import result, or None if the staged upload doesn't exist
    (expired or unknown token).
    """
    from application.admin.importexport.helper import import_database

    json_path, zip_path = stage_paths(stage_dir, token)
    if not os.path.isfile(json_path):
        return None
    with open(json_path, 'r', encoding='utf-8') as f:
        db_payload = json.load(f)

    try:
        # Reset implies a full media wipe first, matching the old
        # whole-database-reset behaviour; merge leaves existing files alone.
        if mode == 'reset':
            wipe_media(media_folder, renditions_folder)
        if os.path.isfile(zip_path):
            with zipfile.ZipFile(zip_path, 'r') as zf:
                extract_selected_media(zf, db_payload, selection, media_folder)

        result = import_database(app, db, db_payload, selection=selection, mode=mode,
                                 conflict_resolution=conflict_resolution)
        return _finish_import(result, app=app, db=db, socketio=socketio,
                              media_folder=media_folder, renditions_folder=renditions_folder)
    finally:
        for path in (json_path, zip_path):
            try:
                os.remove(path)
            except OSError:
                pass
