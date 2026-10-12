"""`flask dh rerender` and `rerender-content`: regenerate previews, renditions and cached HTML."""

import os

import click

from .group import dh


def rerender_media(db, media_root, previews_root, renditions_root, missing_only=False, progress=None) -> dict:
    """Recreate the preview and FHD/4K/8K renditions of every Media row.

    *missing_only* only fills gaps (what the Media page's "Sync previews"
    does); otherwise everything is rendered from scratch — e.g. after
    changing the preview or rendition settings, or to repair corrupt files.
    *progress* is called once per media item. Returns counts.
    """
    from application.admin.media import renditions as media_renditions
    from application.models import Media

    stats = {'media': 0, 'previews': 0, 'renditions': 0, 'missing_source': 0}
    rows = db.session.execute(db.select(Media).order_by(Media.id)).scalars().all()
    for m in rows:
        stats['media'] += 1
        rel = f'{m.folder_path}/{m.filename}' if m.folder_path else m.filename
        source = os.path.join(media_root, rel)
        if progress:
            progress(rel)
        if not os.path.isfile(source):
            stats['missing_source'] += 1
            continue
        is_video = bool(m.mime_type and m.mime_type.startswith('video/'))

        preview = media_renditions.preview_path(previews_root, rel)
        if not (missing_only and os.path.exists(preview)):
            if os.path.exists(preview):
                os.remove(preview)  # so a failed re-render shows up as missing, not as stale
            media_renditions.create_preview(source, preview, is_video)
            if os.path.exists(preview) and not is_video:
                stats['previews'] += 1

        if not is_video:
            if not missing_only:
                media_renditions.remove_renditions(renditions_root, rel)
            stats['renditions'] += len(media_renditions.render_renditions(source, renditions_root, rel))
    return stats


@dh.command('rerender')
@click.option('--missing-only', is_flag=True, help='Only create previews/renditions that are missing.')
def rerender(missing_only):
    """Re-render the previews and FHD/4K/8K renditions of all media files.

    Without --missing-only every preview and rendition is rendered again from
    the original upload. Originals are never touched.
    """
    from flask import current_app
    from application.models import Media

    app = current_app
    db = app.extensions['sqlalchemy']
    total = db.session.execute(db.select(db.func.count()).select_from(Media)).scalar()
    with click.progressbar(length=total, label='Rendering media', show_pos=True,
                           item_show_func=lambda rel: rel) as bar:
        def _step(rel):
            bar.update(1, rel)
        stats = rerender_media(
            db, app.config['MEDIA_FOLDER'], app.config['PREVIEW_FOLDER'], app.config['MEDIA_RENDITIONS_FOLDER'],
            missing_only=missing_only, progress=_step,
        )
    click.echo(f"Done: {stats['media']} media file(s), {stats['previews']} preview(s) and "
               f"{stats['renditions']} rendition(s) written.")
    if stats['missing_source']:
        click.secho(f"{stats['missing_source']} media file(s) are missing on disk and were skipped.", fg='yellow')


# --- rerender-content --------------------------------------------------------------


def rerender_all(db, contenttype_ids=None, echo=click.echo) -> int:
    """Re-render the stored HTML of every content element (of *contenttype_ids*,
    or of all content types). Returns how many elements were updated."""
    from application.models import Contenttype
    from application.admin.content.helper import rerender_content_element_for_contenttype

    if not contenttype_ids:
        contenttype_ids = db.session.execute(db.select(Contenttype.id).order_by(Contenttype.id)).scalars().all()
    total = 0
    for ct_id in contenttype_ids:
        if db.session.get(Contenttype, ct_id) is None:
            echo(f'Content type {ct_id}: not found, skipped')
            continue
        updated = rerender_content_element_for_contenttype(db, ct_id)
        total += len(updated)
        echo(f'Content type {ct_id}: re-rendered {len(updated)} content element(s)')
    echo(f'Done. Re-rendered {total} content element(s).')
    return total


@dh.command('rerender-content')
@click.option('--contenttype', 'contenttype_ids', type=int, multiple=True,
              help='Only this content type ID (repeatable). Default: all.')
def rerender_content(contenttype_ids):
    """Re-render the stored HTML of all content.

    Refreshes field rendering after an update, magic tags and Pretalx tables.
    Running screens get the new HTML with their next content push (e.g. the
    next content change or reconnect) — this command can't reach them itself.
    """
    from flask import current_app
    rerender_all(current_app.extensions['sqlalchemy'], list(contenttype_ids))


# --- migrate, backup, backups, restore -----------------------------------------------
