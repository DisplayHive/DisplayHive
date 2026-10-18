"""Image: a picture from a URL (or the media library), or a random one from media with chosen tags.

A "random from tags" field renders the whole candidate pool into the HTML; the screen picks one on every
display (frontends/screen/ts/screen/random-image-resolver.ts) so every screen shows its own pick.
"""

import json
import urllib.parse
from html import escape as _html_escape

from markupsafe import Markup

from application.plugins.handlers import FieldHandler, RenderContext


def image_style(ctx: dict, field_name: str) -> str:
    """CSS for an image field, from its `__fit` / `__size` sub-settings.

    `__fit` ('height'/'width'/'stretch') takes priority and ignores
    `__size` entirely; unset, falls back to the vh-based fixed-height
    behavior (explicit height keeps it consistent regardless of the
    container's own height; 0/blank just scales to fit as before).

    Any mode that sets an explicit height together with `max-width` also sets
    `object-fit: contain`: when `max-width` clamps the box (an image wider than
    the container), the picture is letterboxed inside it instead of being
    squashed to the unclamped height — i.e. the aspect ratio is kept. Only
    'stretch' deliberately distorts.
    """
    fit = str(ctx.get(f'{field_name}__fit') or '').strip()
    if fit == 'height':
        return 'height:100%;width:auto;max-width:100%;object-fit:contain;'
    if fit == 'width':
        return 'width:100%;height:auto;'
    if fit == 'stretch':
        return 'width:100%;height:100%;object-fit:fill;'
    size = ctx.get(f'{field_name}__size')
    try:
        size = float(size)
    except (TypeError, ValueError):
        size = 0
    return f'height:{size}vh;width:auto;max-width:100%;object-fit:contain;' if size > 0 else 'max-width:100%;height:auto;'


class Handler(FieldHandler):
    id = 'image'
    depends_on = ('media',)

    def _pool(self, rc: RenderContext):
        """Candidate URLs of a ``random_tags`` field (media carrying one of the chosen tags), or ``None``."""
        if rc.db is None or rc.option('image_mode') != 'random_tags':
            return None
        selected_tags = [t for t in rc.values.get(f'{rc.field_name}__image_tags', []) if t]
        if not selected_tags:
            return None
        from application.models.content import Media
        candidates = []
        for media in rc.db.session.execute(rc.db.select(Media)).scalars().all():
            media_tags = {t.strip() for t in (media.tags or '').split(',') if t.strip()}
            if any(t in media_tags for t in selected_tags):
                folder = media.folder_path or ''
                file_rel = (folder + '/' + media.filename) if folder else media.filename
                candidates.append(f'/static/media/{file_rel}')
        return candidates or None

    def render(self, rc: RenderContext):
        pool = self._pool(rc)
        if pool:
            pool_json = _html_escape(json.dumps(pool))
            return Markup(f"<img data-dh-random-pool='{pool_json}' style=\"{image_style(rc.values, rc.field_name)}\" />")
        if rc.has_value:
            url = str(rc.value).strip()
            scheme = urllib.parse.urlparse(url).scheme.lower()
            if scheme not in ('', 'http', 'https', 'data'):
                return ''
            if url:
                return Markup(f'<img src="{_html_escape(url)}" style="{image_style(rc.values, rc.field_name)}" />')
        return None

    def default_values(self, packed: str) -> dict:
        # A container's default used to be just the URL; only the {url, size, fit, mode, tags} shape carries more.
        try:
            parsed = json.loads(packed)
        except (ValueError, TypeError):
            parsed = None
        if isinstance(parsed, dict) and 'url' in parsed:
            return {
                'default': parsed.get('url', ''),
                'default__size': parsed.get('size') or 0,
                'default__fit': parsed.get('fit') or '',
                'default__image_mode': parsed.get('mode') or '',
                'default__image_tags': parsed.get('tags') or [],
            }
        return {'default': packed}


def register(api):
    api.fieldhandlers.add(Handler())
