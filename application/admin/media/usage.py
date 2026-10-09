"""Where is a media file used? One scan over everything that can hold a media URL.

Media are referenced by URL (``/static/media/<folder>/<file>``) inside free text — content
values, field presets, container defaults, design backdrops, settings — not by foreign key.
So "used" means: that URL occurs in one of those texts, or (for an image field in random
mode) the field picks by a tag the file carries.
"""

import json
import re
from urllib.parse import unquote

# Up to the end of the URL inside JSON, CSS ``url(...)``, HTML attributes or plain text.
_MEDIA_URL = re.compile(r'/static/media/([^"\'\s)<>\\?#]+)')


def _urls_in(text) -> set:
    """Media paths (``folder/file``, URL-decoded) mentioned in *text*."""
    return {unquote(match) for match in _MEDIA_URL.findall(text or '')}


def _random_tags_in(text) -> set:
    """Tags that image fields in a JSON value bag draw random pictures by."""
    try:
        bag = json.loads(text or '')
    except (TypeError, ValueError):
        return set()
    if not isinstance(bag, dict):
        return set()
    tags = set()
    for key, mode in bag.items():
        if key.endswith('__image_mode') and mode == 'random_tags':
            chosen = bag.get(key[: -len('__image_mode')] + '__image_tags')
            if isinstance(chosen, list):
                tags.update(str(t).strip() for t in chosen if str(t).strip())
    return tags


def _owners(db):
    """Yield ``(owner, [texts])`` for everything that may reference media.

    An owner is ``{'kind', 'id', 'name'}`` as the admin shows it (a content element, a
    content type whose field presets hold the file, a layout whose container default does,
    a design, a system setting).
    """
    from application.models.content import ContentContainer, ContentElement, Design, SystemSetting, TagConfig, Contenttype

    for el in db.session.execute(db.select(ContentElement)).scalars():
        yield {'kind': 'content', 'id': el.id, 'name': el.title}, [el.serialized_input, el.html]

    presets = {}
    for tag in db.session.execute(db.select(TagConfig)).scalars():
        if tag.contenttype_id is not None:
            presets.setdefault(tag.contenttype_id, []).append(tag.default_value)
    for ct in db.session.execute(db.select(Contenttype)).scalars():
        if ct.id in presets:
            yield {'kind': 'contenttype', 'id': ct.id, 'name': ct.name}, presets[ct.id]

    for container in db.session.execute(db.select(ContentContainer)).scalars():
        if not container.default_content:
            continue
        holders = [{'kind': 'layout', 'id': l.id, 'name': l.name} for l in container.layouts]
        for holder in holders or [{'kind': 'container', 'id': container.id, 'name': container.name}]:
            yield holder, [container.default_content]

    for design in db.session.execute(db.select(Design)).scalars():
        yield (
            {'kind': 'design', 'id': design.id, 'name': design.name},
            [design.background_image_url, design.css, design.html, design.background_effect_settings],
        )

    for setting in db.session.execute(db.select(SystemSetting)).scalars():
        yield {'kind': 'setting', 'id': setting.id, 'name': setting.key}, [setting.value]


def media_usage(db, media_list) -> dict:
    """``{media id: [owner, …]}`` for every file in *media_list* that something uses.

    *media_list* is the Media rows. Owners are listed once each, in scan order.
    """
    by_path = {}
    by_tag = {}
    for m in media_list:
        rel = f'{m.folder_path}/{m.filename}' if m.folder_path else m.filename
        by_path[rel] = m.id
        for tag in (t.strip() for t in (m.tags or '').split(',')):
            if tag:
                by_tag.setdefault(tag, set()).add(m.id)

    usage: dict = {}
    for owner, texts in _owners(db):
        used = set()
        for text in texts:
            used.update(by_path[p] for p in _urls_in(text) if p in by_path)
            for tag in _random_tags_in(text):
                used.update(by_tag.get(tag, ()))
        for media_id in used:
            entries = usage.setdefault(media_id, [])
            if owner not in entries:
                entries.append(owner)
    return usage
