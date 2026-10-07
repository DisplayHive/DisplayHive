"""Down-scaled renditions of uploaded images: FHD, 4K and 8K.

Every uploaded raster image gets up to three smaller copies under
``static/media_renditions/<tier>/<folder>/<filename>`` (same name and format
as the original), so a screen can load an image that fits its resolution
instead of the full-size upload. The screen client picks the smallest tier
that is still at least as large as its own resolution
(frontends/screen/ts/screen/media-renditions.ts).

Tiers are measured on the image's *long edge* (1920 / 3840 / 7680 px), so
portrait images work the same as landscape ones. A tier is **never larger
than the source**: if the original's long edge is not bigger than the tier's,
that tier is simply not rendered (the original already is the best available
image for it), and the client falls back to the original when a tier's URL
doesn't exist.
"""

import logging
import os
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# (name, long-edge in px) — smallest first.
TIERS = (('fhd', 1920), ('4k', 3840), ('8k', 7680))

_JPEG_QUALITY = 90


def rendition_path(renditions_root: str, tier: str, rel: str) -> str:
    """Absolute-ish path of a tier's rendition of the media file *rel*."""
    return os.path.join(renditions_root, tier, rel)


def _save(img, path: str, fmt: str, info: dict) -> None:
    """Write *img* to *path* atomically (temp file in the same folder + replace)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f'{path}.tmp-{os.getpid()}'
    try:
        if fmt == 'JPEG':
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            params = {'quality': _JPEG_QUALITY, 'optimize': True, 'progressive': True}
            if info.get('icc_profile'):
                params['icc_profile'] = info['icc_profile']
            img.save(tmp, 'JPEG', **params)
        else:
            params = {'optimize': True}
            if info.get('icc_profile'):
                params['icc_profile'] = info['icc_profile']
            img.save(tmp, fmt, **params)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def render_renditions(source_path: str, renditions_root: str, rel: str) -> list:
    """Render the missing renditions of *source_path* (media-relative path *rel*).

    Only tiers strictly smaller than the source's long edge are rendered, and
    an existing rendition that is newer than the source is kept. Returns the
    names of the tiers rendered by this call. Raises nothing for unreadable
    or non-raster files — they're logged and yield no renditions.
    """
    try:
        from PIL import Image, ImageOps

        src_mtime = os.path.getmtime(source_path)
        todo = []
        with Image.open(source_path) as probe:
            fmt = probe.format or ''
            if fmt not in ('JPEG', 'PNG', 'WEBP'):
                return []
            img = ImageOps.exif_transpose(probe)  # browsers honour EXIF orientation; bake it in
            img.load()
            info = dict(probe.info)
            w, h = img.size
            long_edge = max(w, h)
            for tier, edge in TIERS:
                if edge >= long_edge:
                    continue  # never render larger than (or equal to) the source
                dest = rendition_path(renditions_root, tier, rel)
                if os.path.exists(dest) and os.path.getmtime(dest) >= src_mtime:
                    continue
                todo.append((tier, edge, dest))

            created = []
            for tier, edge, dest in todo:
                scale = edge / long_edge
                size = (max(1, round(w * scale)), max(1, round(h * scale)))
                work = img
                if work.mode == 'P':
                    work = work.convert('RGBA' if 'transparency' in work.info else 'RGB')
                _save(work.resize(size, Image.Resampling.LANCZOS), dest, fmt, info)
                created.append(tier)
            return created
    except Exception:
        logger.exception('Could not render renditions for %s', source_path)
        return []


PREVIEW_SIZE = (400, 400)


def preview_path(previews_root: str, rel: str) -> str:
    """Thumbnail location for the media file *rel*: same folder, ``<stem>_preview.jpg``."""
    folder, filename = os.path.split(rel)
    return os.path.join(previews_root, folder, f'{os.path.splitext(filename)[0]}_preview.jpg')


def create_preview(source_path: str, dest_path: str, is_video: bool = False) -> None:
    """Write a 400px JPEG thumbnail of *source_path* to *dest_path* (best effort).

    Videos get none yet (that would need ffmpeg); the media list falls back
    to a placeholder for them.
    """
    if is_video:
        return
    try:
        from PIL import Image

        with Image.open(source_path) as img:
            # Flatten transparency onto white — JPEG has no alpha channel.
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail(PREVIEW_SIZE, Image.Resampling.LANCZOS)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            img.save(dest_path, 'JPEG', quality=85)
    except Exception:
        logger.exception('Error creating preview for %s', source_path)


def remove_renditions(renditions_root: str, rel: str) -> None:
    """Delete every tier's rendition of the media file *rel* (best effort)."""
    for tier, _edge in TIERS:
        path = rendition_path(renditions_root, tier, rel)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            logger.warning('Could not remove rendition %s', path, exc_info=True)


def ensure_all(rels: Iterable[str], media_root: str, renditions_root: str) -> dict:
    """Render whatever renditions are missing for every media file in *rels*.

    Idempotent and safe to run repeatedly (startup, after an import, from the
    media page's sync button). Does no database access, so it can run in a
    worker thread. Returns ``{'checked', 'created', 'skipped_no_source'}``.
    """
    checked = created = skipped = 0
    for rel in rels:
        source = os.path.join(media_root, rel)
        if not os.path.isfile(source):
            skipped += 1
            continue
        checked += 1
        created += len(render_renditions(source, renditions_root, rel))
    return {'checked': checked, 'created': created, 'skipped_no_source': skipped}


def run_blocking(fn, *args):
    """Run CPU-bound *fn* without stalling the eventlet hub.

    Under eventlet (the production server) image resizing in the green thread
    would freeze every socket for its duration, so it goes through a real
    thread pool; anywhere else it just runs inline.
    """
    try:
        from eventlet import tpool
        return tpool.execute(fn, *args)
    except Exception:
        return fn(*args)


def media_rels(media_rows) -> list:
    """Media-relative paths ("folder/name.png") for Media rows."""
    out = []
    for m in media_rows:
        folder = (m.folder_path or '').strip('/')
        out.append(f'{folder}/{m.filename}' if folder else m.filename)
    return out


def schedule_backfill(socketio, app, db, media_root: str, renditions_root: str,
                      only: Optional[Iterable[str]] = None) -> None:
    """Backfill missing renditions in the background (startup / after import).

    The Media rows are read here, in the caller's context; the heavy file work
    then runs off the event loop. *only* limits it to the given media paths.
    """
    from application.models.content import Media

    def _job():
        try:
            with app.app_context():
                rels = media_rels(db.session.execute(db.select(Media)).scalars().all())
            if only is not None:
                wanted = set(only)
                rels = [r for r in rels if r in wanted]
            stats = run_blocking(ensure_all, rels, media_root, renditions_root)
            if stats['created']:
                logger.info('Media renditions backfill: %s', stats)
        except Exception:
            logger.exception('Media renditions backfill failed')

    socketio.start_background_task(_job)
