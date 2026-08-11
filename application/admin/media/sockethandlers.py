"""Per-page admin media socket handlers (migrated from socketio_handlers/media.py)."""

import os
import logging
from datetime import datetime, timezone

from flask_socketio import emit
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)


def register_admin_media_handlers(socketio, app, db):
    """Register all media-related socket.io event handlers for admin media page."""
    from application.models.content import Media
    from application.socketio_handlers.auth import admin_handler, require_right, current_admin_user
    from application.permissions import has_right

    MEDIA_FOLDER = app.config.get('MEDIA_FOLDER', 'static/media')
    PREVIEW_FOLDER = app.config.get('PREVIEW_FOLDER', 'static/media_previews')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

    def allowed_file(filename):
        """Return True if *filename* has an allowed extension."""
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    def create_preview(source_path, preview_path, is_video=False):
        """Create a preview/thumbnail for media file."""
        try:
            if is_video:
                # Placeholder for video thumbnail generation
                # Would use ffmpeg here: ffmpeg -i input.mp4 -ss 00:00:01 -vframes 1 output.jpg
                return
            # Image thumbnail using Pillow
            from PIL import Image

            with Image.open(source_path) as img:
                # Convert to RGB if necessary (for PNG with transparency, etc.)
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # Resize maintaining aspect ratio
                img.thumbnail((400, 400), Image.Resampling.LANCZOS)

                # Save as JPEG
                img.save(preview_path, 'JPEG', quality=85)
        except Exception:
            logger.exception('Error creating preview for %s', source_path)

    def _build_media_list_payload():
        """Build a structured list of all media items for the Vue SPA."""
        from application.utils.design import media_file_urls
        all_media = db.session.execute(
            db.select(Media).order_by(Media.created_at.desc())
        ).scalars().all()
        media_list = []
        for m in all_media:
            url, preview_url = media_file_urls(m)
            media_list.append({
                'id': m.id,
                'filename': m.filename,
                'title': m.title or m.filename,
                'tags': [t.strip() for t in (m.tags or '').split(',') if t.strip()],
                'mimetype': m.mime_type or '',
                'folder': m.folder_path or '',
                'url': url,
                'preview_url': preview_url,
                'file_size': m.file_size,
                'created_at': m.created_at.isoformat() if m.created_at else None,
            })
        return media_list

    def _push_media_list():
        """Best-effort push of the refreshed media list to the requesting client."""
        try:
            emit('displayhive:media:stc:media_list', {'media': _build_media_list_payload()})
        except Exception:
            logger.exception('Failed to push media list')

    @socketio.on('displayhive:media:cts:get_media')
    @require_right('media.page')
    def handle_get_media(data=None):
        """Namespaced: return structured media list to the requesting client."""
        emit('displayhive:media:stc:media_list', {'media': _build_media_list_payload()})

    @socketio.on('displayhive:media:cts:upload')
    @require_right('media.upload')
    def handle_upload(data):
        """Namespaced: upload a media file. Returns an ack dict to the caller."""
        file_data = data.get('file_data')  # base64 encoded
        filename = data.get('filename')
        folder_path = data.get('folder', '')
        title = data.get('title', '').strip() or filename
        tags = data.get('tags', '').strip()
        mime_type = data.get('mime_type')

        # If client didn't provide a MIME type, try to guess from filename
        if not mime_type:
            import mimetypes
            mime_type = mimetypes.guess_type(filename)[0] or ''

        if not file_data or not filename:
            return {'success': False, 'error': 'No file provided'}

        if not allowed_file(filename):
            logger.warning('upload rejected by extension check: filename=%s', filename)
            return {'success': False, 'error': 'File type not allowed'}

        # Decode base64 file data. Accept both full data URLs and raw base64.
        import base64
        try:
            if isinstance(file_data, str) and file_data.startswith('data:') and ',' in file_data:
                b64payload = file_data.split(',', 1)[1]
            else:
                b64payload = file_data
            file_bytes = base64.b64decode(b64payload)
            logger.debug("upload decoded %s bytes for '%s'", len(file_bytes), filename)
        except Exception as e:
            return {'success': False, 'error': f'Could not decode file data: {e}'}

        # Check file size
        if len(file_bytes) > MAX_FILE_SIZE:
            return {'success': False, 'error': f'File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)'}

        # Validate the *content*, not just the extension: the bytes must
        # actually decode as an image, and its detected format must match an
        # allowed type. This rejects renamed/polyglot files.
        try:
            import io as _io
            from PIL import Image as _Image
            with _Image.open(_io.BytesIO(file_bytes)) as _probe:
                _probe.verify()
            detected_fmt = (_probe.format or '').lower()
            if detected_fmt == 'jpg':
                detected_fmt = 'jpeg'
            if detected_fmt not in {'png', 'jpeg'}:
                logger.warning('upload rejected by content check: detected format=%r', detected_fmt)
                return {'success': False, 'error': 'File content is not a supported image'}
        except Exception as e:
            logger.warning('upload rejected: not a valid image (%s)', e)
            return {'success': False, 'error': 'File is not a valid image'}

        # Secure filename and ensure uniqueness
        filename = secure_filename(filename)
        base, ext = os.path.splitext(filename)
        counter = 1
        target_folder = os.path.join(MEDIA_FOLDER, folder_path) if folder_path else MEDIA_FOLDER
        # Guard against path traversal via the client-supplied folder path:
        # keep the resolved target strictly inside MEDIA_FOLDER/PREVIEW_FOLDER.
        if folder_path:
            media_root = os.path.realpath(MEDIA_FOLDER)
            preview_root = os.path.realpath(PREVIEW_FOLDER)
            if (not os.path.realpath(target_folder).startswith(media_root + os.sep)
                    or not os.path.realpath(os.path.join(PREVIEW_FOLDER, folder_path)).startswith(preview_root + os.sep)):
                logger.warning('upload rejected by path traversal check: folder=%r', folder_path)
                return {'success': False, 'error': 'Invalid folder path'}
        os.makedirs(target_folder, exist_ok=True)
        while os.path.exists(os.path.join(target_folder, filename)):
            filename = f"{base}_{counter}{ext}"
            counter += 1

        # Save file
        file_path = os.path.join(target_folder, filename)
        with open(file_path, 'wb') as f:
            f.write(file_bytes)

        file_size = len(file_bytes)

        # Create preview
        preview_folder = os.path.join(PREVIEW_FOLDER, folder_path) if folder_path else PREVIEW_FOLDER
        os.makedirs(preview_folder, exist_ok=True)
        preview_filename = f"{os.path.splitext(filename)[0]}_preview.jpg"
        preview_path = os.path.join(preview_folder, preview_filename)
        is_video = mime_type and mime_type.startswith('video/')
        create_preview(file_path, preview_path, is_video)

        # Save to database
        media = Media(
            filename=filename,
            title=title,
            tags=tags,
            folder_path=folder_path,
            mime_type=mime_type,
            file_size=file_size,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(media)
        db.session.commit()
        logger.info("upload saved media id=%s filename='%s'", media.id, filename)

        # Push refreshed media list to the uploader so the gallery updates
        _push_media_list()

        return {'success': True, 'id': media.id, 'filename': filename}

    def _do_media_edit(media_id, title, tags_raw):
        """Shared edit logic used by both legacy and namespaced handlers."""
        if not media_id:
            return {'success': False, 'error': 'No media ID provided'}

        media = db.session.get(Media, media_id)
        if not media:
            return {'success': False, 'error': 'Media not found'}

        if title is not None:
            media.title = title

        # Accept tags as a list ['a','b'] or a comma-string 'a,b'
        if tags_raw is not None:
            if isinstance(tags_raw, list):
                media.tags = ','.join(t.strip() for t in tags_raw if str(t).strip())
            else:
                media.tags = str(tags_raw)

        db.session.commit()
        logger.info("media_edit saved id=%s title='%s' tags='%s'", media_id, media.title, media.tags)

        # Push refreshed list to the caller
        _push_media_list()

        return {'success': True, 'id': media.id}

    @socketio.on('displayhive:media:cts:update_media')
    @admin_handler
    def handle_update_media(data):
        """Namespaced: update title/tags for a media item.

        Title and tags are gated by separate rights (media.rename /
        media.tag), so each requested field is checked independently and
        silently dropped (not the whole call rejected) if the caller lacks
        the right for that specific field.
        """
        data = data or {}
        user = current_admin_user()
        title = data.get('title')
        if title is not None and not has_right(db, user, 'media.rename'):
            title = None
        tags_raw = data.get('tags')
        if tags_raw is not None and not has_right(db, user, 'media.tag'):
            tags_raw = None
        return _do_media_edit(media_id=data.get('id'), title=title, tags_raw=tags_raw)

    @socketio.on('displayhive:media:cts:sync_previews')
    @require_right('media.upload')
    def handle_sync_previews(data=None):
        """Compare the count of media files against their preview/thumbnail
        files on disk and regenerate any that are missing (e.g. lost in a
        backup that didn't include static/media_previews, or a manual file
        copy). Returns a summary ack; pushes a refreshed media list since a
        previously-broken thumbnail URL now resolves.
        """
        all_media = db.session.execute(db.select(Media)).scalars().all()
        missing = 0
        regenerated = 0
        skipped_no_source = 0
        for m in all_media:
            file_path = (
                os.path.join(MEDIA_FOLDER, m.folder_path, m.filename)
                if m.folder_path else os.path.join(MEDIA_FOLDER, m.filename)
            )
            preview_filename = f"{os.path.splitext(m.filename)[0]}_preview.jpg"
            preview_path = (
                os.path.join(PREVIEW_FOLDER, m.folder_path, preview_filename)
                if m.folder_path else os.path.join(PREVIEW_FOLDER, preview_filename)
            )
            if os.path.exists(preview_path):
                continue
            missing += 1
            if not os.path.exists(file_path):
                skipped_no_source += 1
                continue
            os.makedirs(os.path.dirname(preview_path), exist_ok=True)
            is_video = m.mime_type and m.mime_type.startswith('video/')
            create_preview(file_path, preview_path, is_video)
            if os.path.exists(preview_path):
                regenerated += 1

        logger.info(
            'sync_previews: %s media, %s missing previews, %s regenerated, %s skipped (source file missing)',
            len(all_media), missing, regenerated, skipped_no_source,
        )
        if regenerated:
            _push_media_list()

        return {
            'success': True,
            'total': len(all_media),
            'missing': missing,
            'regenerated': regenerated,
            'skipped_no_source': skipped_no_source,
        }

    @socketio.on('displayhive:media:cts:delete_media')
    @require_right('media.delete')
    def handle_delete_media(data):
        """Namespaced: delete a media item."""
        data = data or {}
        media_id = data.get('id')

        if not media_id:
            emit('media_error', {'error': 'No media ID provided'})
            return

        media = db.session.get(Media, media_id)
        if not media:
            emit('media_error', {'error': 'Media not found'})
            return

        # Delete files
        file_path = os.path.join(MEDIA_FOLDER, media.folder_path, media.filename) if media.folder_path else os.path.join(MEDIA_FOLDER, media.filename)
        preview_filename = f"{os.path.splitext(media.filename)[0]}_preview.jpg"
        preview_path = os.path.join(PREVIEW_FOLDER, media.folder_path, preview_filename) if media.folder_path else os.path.join(PREVIEW_FOLDER, preview_filename)

        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(preview_path):
            os.remove(preview_path)

        # Delete from database
        db.session.delete(media)
        db.session.commit()

        # Push refreshed media list
        _push_media_list()
