"""Per-page admin media socket handlers (migrated from socketio_handlers/media.py)."""

import os
import logging

from flask_socketio import emit

from application import media_renditions

logger = logging.getLogger(__name__)


def register_admin_media_handlers(socketio, app, db):
    """Register all media-related socket.io event handlers for admin media page."""
    from application.models.content import Media
    from application.socketio_handlers.auth import require_right, current_admin_user, fields
    from application.socketio_handlers.actions import admin_action, get_or_fail, ok
    from application.permissions import has_right

    # Absolute paths inside DATA_DIR, set by app.py from application/paths.py.
    MEDIA_FOLDER = app.config['MEDIA_FOLDER']
    PREVIEW_FOLDER = app.config['PREVIEW_FOLDER']
    RENDITIONS_FOLDER = app.config['MEDIA_RENDITIONS_FOLDER']
    create_preview = media_renditions.create_preview

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

    # Uploads are an HTTP multipart route now (routes.py / storage.py), not a
    # base64 Socket.IO event.

    def _do_media_edit(media_id, title, tags_raw):
        """Shared edit logic used by both legacy and namespaced handlers."""
        media = get_or_fail(db, Media, media_id, 'Media')

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

        return ok(id=media.id)

    @socketio.on('displayhive:media:cts:update_media')
    @admin_action()
    def handle_update_media(data):
        """Namespaced: update title/tags for a media item.

        Title and tags are gated by separate rights (media.rename /
        media.tag), so each requested field is checked independently and
        silently dropped (not the whole call rejected) if the caller lacks
        the right for that specific field.
        """
        media_id, title, tags_raw = fields(data, 'id', 'title', 'tags')
        user = current_admin_user()
        if title is not None and not has_right(db, user, 'media.rename'):
            title = None
        if tags_raw is not None and not has_right(db, user, 'media.tag'):
            tags_raw = None
        return _do_media_edit(media_id=media_id, title=title, tags_raw=tags_raw)

    @socketio.on('displayhive:media:cts:sync_previews')
    @admin_action('media.upload')
    def handle_sync_previews(data=None):
        """Compare the count of media files against their preview/thumbnail
        files on disk and regenerate any that are missing — and render any
        missing FHD/4K/8K renditions of the images (e.g. lost in a
        backup that didn't include static/media_previews, or a manual file
        copy). Returns a summary ack; pushes a refreshed media list since a
        previously-broken thumbnail URL now resolves.
        """
        all_media = db.session.execute(db.select(Media)).scalars().all()
        missing = 0
        regenerated = 0
        skipped_no_source = 0
        renditions_created = 0
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
            if not (m.mime_type and m.mime_type.startswith('video/')) and os.path.exists(file_path):
                rel = f'{m.folder_path}/{m.filename}' if m.folder_path else m.filename
                renditions_created += len(
                    media_renditions.run_blocking(media_renditions.render_renditions, file_path, RENDITIONS_FOLDER, rel)
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
        logger.info('sync_previews: %s image renditions (FHD/4K/8K) created', renditions_created)
        if regenerated:
            _push_media_list()

        return ok(
            total=len(all_media),
            missing=missing,
            regenerated=regenerated,
            skipped_no_source=skipped_no_source,
            renditions_created=renditions_created,
        )

    @socketio.on('displayhive:media:cts:delete_media')
    @admin_action('media.delete')
    def handle_delete_media(data):
        """Namespaced: delete a media item."""
        media = get_or_fail(db, Media, fields(data, 'id')[0], 'Media')

        # Delete files
        file_path = os.path.join(MEDIA_FOLDER, media.folder_path, media.filename) if media.folder_path else os.path.join(MEDIA_FOLDER, media.filename)
        preview_filename = f"{os.path.splitext(media.filename)[0]}_preview.jpg"
        preview_path = os.path.join(PREVIEW_FOLDER, media.folder_path, preview_filename) if media.folder_path else os.path.join(PREVIEW_FOLDER, preview_filename)

        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(preview_path):
            os.remove(preview_path)
        media_renditions.remove_renditions(
            RENDITIONS_FOLDER,
            f'{media.folder_path}/{media.filename}' if media.folder_path else media.filename,
        )

        # Delete from database
        db.session.delete(media)
        db.session.commit()

        # Push refreshed media list
        _push_media_list()
