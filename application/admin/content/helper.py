"""Helpers for the admin Content page."""

import json
import logging
import random as _random
import urllib.parse
from html import escape as _html_escape
from markupsafe import Markup

from application.admin.content.pretalx_render import (
    _get_pretalx_data,
    _render_pretalx_table,
    _render_table,
)

logger = logging.getLogger(__name__)


def render_content_fields(tagconfigs, serialized_input: str, db=None) -> dict:
    """Render each of *tagconfigs*' field values and return
    ``{contentcontainer_id_str: rendered_html}``, one entry per field.

    Each ContentContainer a Contenttype uses is itself one field with an
    assigned field_handler (textklein, image, pretalx_table, etc) — there is
    no separate HTML template to fill in; the field's transformed value *is*
    the container's rendered content.

    Args:
        tagconfigs:        The Contenttype's TagConfig rows (field_name,
                            field_handler, contentcontainer_id).
        serialized_input:  JSON string previously saved in
                            ``ContentElement.serialized_input``.
        db:                Optional SQLAlchemy db instance. When provided,
                            image fields whose mode is ``random_tags`` have a
                            random matching media item resolved, pretalx
                            fields fetch live schedule data, and
                            datetime_format fields use the configured
                            timezone.

    Returns:
        {contentcontainer_id_str: rendered_html} — fields with no container
        assigned are skipped.
    """
    ctx: dict = {}
    try:
        if serialized_input:
            ctx = json.loads(serialized_input)
    except Exception:
        ctx = {}

    field_handlers = {tc.field_name: tc.field_handler for tc in (tagconfigs or []) if tc.field_name}

    # Resolve random_tags image fields to a concrete URL before rendering
    if db is not None and field_handlers:
        from application.models.content import Media
        image_mode_keys = [k for k in ctx if k.endswith('__image_mode') and ctx[k] == 'random_tags']
        for mode_key in image_mode_keys:
            field_name = mode_key[: -len('__image_mode')]
            if field_handlers.get(field_name) != 'image':
                continue
            tags_key = f'{field_name}__image_tags'
            selected_tags = [t for t in ctx.get(tags_key, []) if t]
            if not selected_tags:
                continue
            all_media = db.session.execute(db.select(Media)).scalars().all()
            candidates = []
            for m in all_media:
                media_tags = {t.strip() for t in (m.tags or '').split(',') if t.strip()}
                if any(t in media_tags for t in selected_tags):
                    folder = m.folder_path or ''
                    file_rel = (folder + '/' + m.filename) if folder else m.filename
                    candidates.append(f'/static/media/{file_rel}')
            if candidates:
                ctx[field_name] = _random.choice(candidates)

    # Inject magic tags so {{ var_<name> }} typed into a text field's stored
    # value gets substituted before that value is escaped/wrapped below.
    tvars: dict = {}
    if db is not None:
        try:
            from application.admin.magictags.helper import load_magic_tags, substitute_magic_tags
            tvars = load_magic_tags(db)
        except Exception:
            tvars = {}

    # Transform each field's raw value according to its field_handler.
    # Values are HTML-escaped to prevent XSS from stored field data.
    for field_name, ftype in field_handlers.items():
        if ftype == 'image' and field_name in ctx and ctx[field_name]:
            url = str(ctx[field_name]).strip()
            parsed_scheme = urllib.parse.urlparse(url).scheme.lower()
            if parsed_scheme not in ('', 'http', 'https', 'data'):
                ctx[field_name] = ''
            elif url:
                ctx[field_name] = Markup(f'<img src="{_html_escape(url)}" style="max-width:100%;height:auto;" />')
        elif ftype == 'arrows' and field_name in ctx and ctx[field_name]:
            char = _html_escape(str(ctx[field_name]).strip())
            size_key = f'{field_name}_size'
            size = ctx.get(size_key, 48)
            try:
                size = int(size)
            except Exception:
                size = 48
            if char:
                ctx[field_name] = Markup(f'<span style="font-size:{size}px;line-height:1;">{char}</span>')
        elif ftype == 'datetime_format':
            fmt_str = str(ctx.get(field_name, 'HH:mm:ss')).strip()
            tz_name = 'UTC'
            if db is not None:
                try:
                    from application.models import SystemSetting
                    tz_row = db.session.execute(
                        db.select(SystemSetting).where(SystemSetting.key == 'timezone')
                    ).scalar_one_or_none()
                    if tz_row and tz_row.value:
                        tz_name = tz_row.value
                except Exception:
                    pass
            ctx[field_name] = Markup(
                f'<div class="dh-clock"'
                f' data-dh-clock="{_html_escape(fmt_str)}"'
                f' data-dh-timezone="{_html_escape(tz_name)}"></div>'
            )
        elif ftype == 'pretalx_table':
            pretalx_data = _get_pretalx_data(str(ctx.get(field_name, '')).strip(), db)
            _ps_no_session  = 'No session running'
            _ps_coming_up   = 'Coming up next'
            _ps_invalid     = 'Invalid API data'
            _ps_time_format = 'HH:mm'
            _ps_end_of_day  = '23:59'
            _ps_sim_dt      = ''
            try:
                if db is not None:
                    from application.models import PretalxSettings
                    _ps = db.session.execute(db.select(PretalxSettings)).scalar_one_or_none()
                    if _ps:
                        _ps_no_session  = _ps.no_session_text or _ps_no_session
                        _ps_coming_up   = _ps.coming_up_text  or _ps_coming_up
                        _ps_invalid     = _ps.invalid_data_text or _ps_invalid
                        _ps_time_format = _ps.time_format or _ps_time_format
                        _ps_end_of_day  = _ps.end_of_day  or _ps_end_of_day
                        _ps_sim_dt      = _ps.sim_datetime or ''
            except Exception:
                pass
            _el_invalid = str(ctx.get(f'{field_name}__invalid_data_text', '')).strip()
            if _el_invalid:
                _ps_invalid = _el_invalid
            ctx[field_name] = Markup(_render_pretalx_table(
                data=pretalx_data,
                roomname=str(ctx.get(f'{field_name}__roomname', '')).strip(),
                linecount=ctx.get(f'{field_name}__linecount', 10),
                fields_config=str(ctx.get(f'{field_name}__fields', '')).strip(),
                display_author=bool(ctx.get(f'{field_name}__author_under_title', False)),
                display_type=str(ctx.get(f'{field_name}__type', 'list')).strip() or 'list',
                empty_text=str(ctx.get(f'{field_name}__empty_text', '')).strip(),
                tracklist_columns=str(ctx.get(f'{field_name}__tracklist_columns', 'name|Name,color|Color')).strip(),
                tracklist_layout=str(ctx.get(f'{field_name}__tracklist_layout', 'list')).strip() or 'list',
                tracklist_exclude=str(ctx.get(f'{field_name}__tracklist_exclude', '')).strip(),
                invalid_data_text=_ps_invalid,
                no_session_text=_ps_no_session,
                coming_up_text=_ps_coming_up,
                time_format=_ps_time_format,
                end_of_day=_ps_end_of_day,
                sim_datetime=_ps_sim_dt,
                today_only=bool(ctx.get(f'{field_name}__today_only', False)),
                separate_days=bool(ctx.get(f'{field_name}__separate_days', False)),
                day_prefix=str(ctx.get(f'{field_name}__day_prefix', '')).strip(),
                tracks_by_color=bool(ctx.get(f'{field_name}__tracks_by_color', False)),
            ))
        elif ftype in ('textklein', 'textbig', 'link') and field_name in ctx:
            raw = str(ctx[field_name])
            if tvars:
                raw = substitute_magic_tags(raw, tvars)
            escaped = _html_escape(raw)
            ctx[field_name] = Markup(escaped.replace('\n', '<br>'))
        elif ftype == 'table':
            ctx[field_name] = Markup(_render_table(ctx.get(field_name, '')))

    rendered_by_container: dict = {}
    for tc in (tagconfigs or []):
        if tc.contentcontainer_id is None:
            continue
        value = str(ctx.get(tc.field_name, '') or '')
        # An empty field value (nothing entered for this ContentElement) falls
        # back to the container's own default_content, the same fallback used
        # when a scene doesn't target the container at all — a field left
        # blank shouldn't look any different from a container not being used.
        if not value and tc.contentcontainer is not None:
            value = render_container_default(tc.contentcontainer, db=db)
        rendered_by_container[str(tc.contentcontainer_id)] = value
    return rendered_by_container


def render_default_value(field_handler: str, content: str, db=None) -> str:
    """Render a single ad-hoc value through *field_handler*'s transform,
    reusing the same logic as a regular Contenttype field (TagConfig).

    Used both for a ContentContainer's own fallback content and for the
    admin's live preview of that default while editing it. The 'arrows'
    handler stores {char, size} as JSON in *content* (mirroring how a
    regular field keeps its size in a separate `<field>_size` key) — every
    other handler treats *content* as the field's plain raw value.
    """
    if not field_handler or not content:
        return ''
    from application.models import TagConfig

    fake_tc = TagConfig(field_name='default', field_handler=field_handler, contentcontainer_id=0)
    ctx = {'default': content}
    if field_handler == 'arrows':
        try:
            parsed = json.loads(content)
            ctx = {'default': parsed.get('char', ''), 'default_size': parsed.get('size', 48)}
        except Exception:
            ctx = {'default': content}
    serialized = json.dumps(ctx, ensure_ascii=False)
    rendered = render_content_fields([fake_tc], serialized, db=db)
    return rendered.get('0', '')


def render_container_default(container, db=None) -> str:
    """Render a ContentContainer's own fallback content through its
    default_field_handler. Returns '' if no default is configured.
    """
    return render_default_value(container.default_field_handler, container.default_content, db=db)


def rerender_content_element_for_contenttype(db, contenttype_id: int) -> list[int]:
    """Re-render all ContentElement rows that use a given Contenttype.

    Each field (TagConfig) targets one container; ContentElement's stored
    ``html`` is a JSON map of ``{contentcontainer_id: rendered_html}``.

    Args:
        db:              SQLAlchemy db instance (Flask-SQLAlchemy).
        contenttype_id:  Primary key of the Contenttype whose fields changed.

    Returns:
        List of ContentElement IDs that were updated.
    """
    from application.models import ContentElement, Contenttype

    try:
        ct = db.session.get(Contenttype, int(contenttype_id))
        if not ct:
            logger.warning('Contenttype %s not found – skipping re-render', contenttype_id)
            return []

        items = db.session.execute(
            db.select(ContentElement).where(ContentElement.contenttype_id == ct.id)
        ).scalars().all()

        tagconfigs = ct.tagconfigs or []

        updated_ids: list[int] = []
        for mc in items:
            rendered_by_container = render_content_fields(tagconfigs, mc.serialized_input or '', db=db)
            mc.html = json.dumps(rendered_by_container, ensure_ascii=False)
            db.session.add(mc)
            updated_ids.append(mc.id)

        if updated_ids:
            db.session.commit()
            logger.info('Re-rendered %s content_element item(s) for contenttype %s', len(updated_ids), contenttype_id)
        else:
            logger.debug('No content_element items for contenttype %s – nothing to re-render', contenttype_id)

        return updated_ids
    except Exception:
        db.session.rollback()
        logger.exception('rerender_content_element_for_contenttype failed')
        return []
