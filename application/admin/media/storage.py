"""Turning an uploaded file on disk into a Media item.

The upload arrives as an HTTP multipart request (routes.py) that Werkzeug
streams straight into a temp file in DATA_DIR's staging directory (see
DataDirRequest in app.py) — it's never held in memory or base64-encoded.
This module validates that file and moves it into the media folder,
then renders its preview and renditions and creates the database row.
"""

import logging
import mimetypes
import os
import shutil
from datetime import datetime, timezone

from werkzeug.utils import secure_filename

from application import media_renditions

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
ALLOWED_FORMATS = {'png', 'jpeg'}  # what Pillow must detect in the content
# Keep in sync with the reverse proxy's body limit (client_max_body_size in
# the nginx example in nix/module.nix) and the hint on the Media page.
MAX_FILE_SIZE = 50 * 1024 * 1024

# The process umask, read once at import (reading it means setting it).
_UMASK = os.umask(0)
os.umask(_UMASK)


class UploadError(Exception):
    """An upload that can't be accepted. `str(e)` is safe to show the uploader;
    *status* is the HTTP status to answer with."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _validate_image(path: str) -> None:
    """The bytes must decode as an image of an allowed format — not just carry
    an allowed extension. Rejects renamed and polyglot files."""
    try:
        from PIL import Image
        with Image.open(path) as probe:
            probe.verify()
            fmt = (probe.format or '').lower()
    except Exception as e:
        logger.warning('upload rejected: not a valid image (%s)', e)
        raise UploadError('File is not a valid image') from e
    if fmt == 'jpg':
        fmt = 'jpeg'
    if fmt not in ALLOWED_FORMATS:
        logger.warning('upload rejected by content check: detected format=%r', fmt)
        raise UploadError('File content is not a supported image')


def _inside(root: str, path: str) -> bool:
    root = os.path.realpath(root)
    return os.path.realpath(path) == root or os.path.realpath(path).startswith(root + os.sep)


def _place(src_path: str, dest_path: str) -> None:
    """Put the staged upload at *dest_path* without copying when possible.

    A hard link is instant on the same filesystem (DATA_DIR) and leaves the
    staging temp file to be deleted when the request closes it; across
    filesystems (a legacy media folder elsewhere) it falls back to a copy.
    `x` mode / link both fail if *dest_path* already exists, so two
    simultaneous uploads of the same name can't overwrite each other.
    """
    try:
        os.link(src_path, dest_path)
    except OSError as e:
        if os.path.exists(dest_path):
            raise
        logger.debug('hard link into media folder failed (%s), copying instead', e)
        with open(src_path, 'rb') as src, open(dest_path, 'xb') as dst:
            shutil.copyfileobj(src, dst, 1024 * 1024)
    # The staging temp file is private (0600) and a hard link shares its
    # mode — give the media file the permissions a plain write would have,
    # so e.g. a reverse proxy serving /static/media from disk can read it.
    os.chmod(dest_path, 0o666 & ~_UMASK)


def ingest_upload(db, config, staged_path: str, filename: str, folder_path: str = '',
                  title: str = '', tags: str = '', mime_type: str = ''):
    """Validate the staged file and store it as a Media item; returns the Media row.

    *config* is the Flask app config (MEDIA_FOLDER / PREVIEW_FOLDER /
    MEDIA_RENDITIONS_FOLDER). Raises UploadError for anything the uploader
    should be told about.
    """
    from application.models.content import Media

    media_folder = config['MEDIA_FOLDER']
    preview_folder_root = config['PREVIEW_FOLDER']
    renditions_folder = config['MEDIA_RENDITIONS_FOLDER']

    original_name = filename or ''
    if not original_name or not os.path.isfile(staged_path):
        raise UploadError('No file provided')
    if '.' not in original_name or original_name.rsplit('.', 1)[1].lower() not in ALLOWED_EXTENSIONS:
        logger.warning('upload rejected by extension check: filename=%s', original_name)
        raise UploadError('File type not allowed')
    file_size = os.path.getsize(staged_path)
    if file_size > MAX_FILE_SIZE:
        raise UploadError(f'File too large (max {MAX_FILE_SIZE // 1024 // 1024} MB)', status=413)
    _validate_image(staged_path)

    folder_path = (folder_path or '').strip().strip('/')
    target_folder = os.path.join(media_folder, folder_path) if folder_path else media_folder
    preview_folder = os.path.join(preview_folder_root, folder_path) if folder_path else preview_folder_root
    # The folder comes from the client: keep it strictly inside both roots.
    if folder_path and not (_inside(media_folder, target_folder) and _inside(preview_folder_root, preview_folder)):
        logger.warning('upload rejected by path traversal check: folder=%r', folder_path)
        raise UploadError('Invalid folder path')
    os.makedirs(target_folder, exist_ok=True)

    safe_name = secure_filename(original_name)
    if not safe_name or '.' not in safe_name:
        raise UploadError('Invalid file name')
    base, ext = os.path.splitext(safe_name)
    candidate, counter = safe_name, 1
    while True:
        dest = os.path.join(target_folder, candidate)
        if not os.path.exists(dest):
            try:
                _place(staged_path, dest)
                break
            except FileExistsError:
                pass  # taken by a concurrent upload in the meantime
        candidate = f'{base}_{counter}{ext}'
        counter += 1

    mime_type = mime_type or mimetypes.guess_type(candidate)[0] or ''
    rel = f'{folder_path}/{candidate}' if folder_path else candidate
    media_renditions.create_preview(dest, media_renditions.preview_path(preview_folder_root, rel))
    media_renditions.run_blocking(media_renditions.render_renditions, dest, renditions_folder, rel)

    media = Media(
        filename=candidate,
        title=(title or '').strip() or original_name,
        tags=(tags or '').strip(),
        folder_path=folder_path,
        mime_type=mime_type,
        file_size=file_size,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(media)
    db.session.commit()
    logger.info("upload saved media id=%s filename='%s' (%s bytes)", media.id, candidate, file_size)
    return media
