"""Per-page admin media socket handlers (migrated from socketio_handlers/media.py)."""

import os
import re
import shutil
import logging
from datetime import datetime, timezone

from flask_socketio import emit
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)


def _is_within(base, target):
    """Return True if *target* resolves to *base* itself or a path inside it.

    Compares against ``base + os.sep`` so a sibling that merely shares a name
    prefix (e.g. ``.../media_previews`` vs ``.../media``) is not mistaken for a
    path inside *base* — the trailing-separator boundary a bare ``startswith``
    check misses.
    """
    base_real = os.path.realpath(base)
    target_real = os.path.realpath(target)
    return target_real == base_real or target_real.startswith(base_real + os.sep)


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

    def get_folder_tree(base_path, current_path=''):
        """Recursively build folder tree structure."""
        folders = []
        full_path = os.path.join(base_path, current_path) if current_path else base_path

        if not os.path.exists(full_path):
            return folders

        try:
            for item in sorted(os.listdir(full_path)):
                item_path = os.path.join(full_path, item)
                if os.path.isdir(item_path):
                    relative_path = os.path.join(current_path, item) if current_path else item
                    folders.append({
                        'name': item,
                        'path': relative_path,
                        'children': get_folder_tree(base_path, relative_path)
                    })
        except PermissionError:
            pass

        return folders

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

    def delete_folder_recursive(media_folder_path, preview_folder_path):
        """Recursively delete folder and all contents from both media and preview directories."""
        if os.path.exists(media_folder_path):
            shutil.rmtree(media_folder_path)
        if os.path.exists(preview_folder_path):
            shutil.rmtree(preview_folder_path)

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

    def _build_folders_payload():
        """Build a flat list of folder dicts for the Vue SPA."""
        folder_tree = get_folder_tree(MEDIA_FOLDER)
        folders = []

        def _flatten(nodes, prefix=''):
            """Recursively flatten the nested folder tree into a flat list of path dicts."""
            for node in nodes:
                path = node.get('path', '')
                folders.append({'name': node.get('name', path), 'path': path})
                _flatten(node.get('children', []), path)
        _flatten(folder_tree)
        return folders

    @socketio.on('displayhive:media:cts:get_media')
    @require_right('media.page')
    def handle_get_media(data=None):
        """Namespaced: return structured media list to the requesting client."""
        emit('displayhive:media:stc:media_list', {'media': _build_media_list_payload()})

    @socketio.on('displayhive:media:cts:get_folders')
    @require_right('media.page')
    def handle_get_folders(data=None):
        """Namespaced: return folder list to the requesting client."""
        emit('displayhive:media:stc:folders_list', {'folders': _build_folders_payload()})

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

    @socketio.on('displayhive:media:cts:folder_create')
    @require_right('media.upload')
    def media_folder_create(message):
        """Create new folder."""
        parent_folder = message.get('parent', '')
        folder_name = message.get('name', '').strip()

        if not folder_name:
            emit('media_error', {'error': 'Folder name required'})
            return

        # Sanitize folder name (no path separators or special chars)
        folder_name = re.sub(r'[^\w\s-]', '', folder_name).strip()
        folder_name = re.sub(r'[-\s]+', '-', folder_name)

        if not folder_name:
            emit('media_error', {'error': 'Invalid folder name'})
            return

        new_folder_path = os.path.join(parent_folder, folder_name) if parent_folder else folder_name

        # Prevent path traversal attacks
        if not _is_within(MEDIA_FOLDER, os.path.join(MEDIA_FOLDER, new_folder_path)):
            emit('media_error', {'error': 'Invalid folder path'})
            return

        # Create in both media and preview directories
        os.makedirs(os.path.join(MEDIA_FOLDER, new_folder_path), exist_ok=True)
        os.makedirs(os.path.join(PREVIEW_FOLDER, new_folder_path), exist_ok=True)

        emit('media_folder_created', {
            'success': True,
            'path': new_folder_path,
            'folder_tree': get_folder_tree(MEDIA_FOLDER),
        })

    @socketio.on('displayhive:media:cts:folder_delete')
    @require_right('media.delete')
    def media_folder_delete(message):
        """Delete folder and all contents."""
        folder_path = message.get('folder', '')

        if not folder_path:
            emit('media_error', {'error': 'Cannot delete root folder'})
            return

        media_folder_path = os.path.join(MEDIA_FOLDER, folder_path)
        if not _is_within(MEDIA_FOLDER, media_folder_path):
            emit('media_error', {'error': 'Invalid folder path'})
            return

        preview_folder_path = os.path.join(PREVIEW_FOLDER, folder_path)

        delete_folder_recursive(media_folder_path, preview_folder_path)

        # Delete database entries
        media_items = db.session.execute(
            db.select(Media).where(Media.folder_path.like(f"{folder_path}%"))
        ).scalars().all()

        for item in media_items:
            db.session.delete(item)
        db.session.commit()

        emit('media_folder_deleted', {
            'success': True,
            'folder_tree': get_folder_tree(MEDIA_FOLDER),
        })

    @socketio.on('displayhive:media:cts:folder_rename')
    @require_right('media.rename')
    def media_folder_rename(message):
        """Rename folder."""
        old_path = message.get('old_path', '')
        new_name = message.get('new_name', '').strip()

        if not old_path or not new_name:
            emit('media_error', {'error': 'Invalid parameters'})
            return

        # Guard against path traversal in the source path
        if not _is_within(MEDIA_FOLDER, os.path.join(MEDIA_FOLDER, old_path)):
            emit('media_error', {'error': 'Invalid folder path'})
            return

        # Sanitize new name
        new_name = re.sub(r'[^\w\s-]', '', new_name).strip()
        new_name = re.sub(r'[-\s]+', '-', new_name)

        # Calculate new path
        parent = os.path.dirname(old_path)
        new_path = os.path.join(parent, new_name) if parent else new_name

        # Guard the destination too, so a crafted parent/name can't escape.
        if not _is_within(MEDIA_FOLDER, os.path.join(MEDIA_FOLDER, new_path)):
            emit('media_error', {'error': 'Invalid folder path'})
            return

        # Rename in both directories
        old_media = os.path.join(MEDIA_FOLDER, old_path)
        new_media = os.path.join(MEDIA_FOLDER, new_path)
        old_preview = os.path.join(PREVIEW_FOLDER, old_path)
        new_preview = os.path.join(PREVIEW_FOLDER, new_path)

        if os.path.exists(old_media):
            shutil.move(old_media, new_media)
        if os.path.exists(old_preview):
            shutil.move(old_preview, new_preview)

        # Update database entries
        media_items = db.session.execute(
            db.select(Media).where(Media.folder_path.like(f"{old_path}%"))
        ).scalars().all()

        for item in media_items:
            if item.folder_path == old_path:
                item.folder_path = new_path
            elif item.folder_path.startswith(old_path + '/'):
                item.folder_path = new_path + item.folder_path[len(old_path):]

        db.session.commit()

        emit('media_folder_renamed', {
            'success': True,
            'new_path': new_path,
            'old_path': old_path,
            'folder_tree': get_folder_tree(MEDIA_FOLDER),
        })
