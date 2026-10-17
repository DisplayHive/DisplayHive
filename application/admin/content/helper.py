"""Helpers for the admin Content page."""

import json
import logging

from application.plugins import registry as plugin_registry
from application.plugins.handlers import RenderContext

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
    except (ValueError, TypeError):
        ctx = {}

    # Locked/hidden *individual sub-settings* always render their
    # Contenttype-configured preset, regardless of what the caller's
    # serialized_input actually contains for that key — this is the single
    # enforcement point for both "prohibit overwrite" and "hide from user",
    # since every rendering path (screens, previews, create/update) goes
    # through this function. option_flags is keyed by the same flat wire key
    # shape as default_value/ctx itself (e.g. '<name>', '<name>__size'), so
    # only the specific flagged sub-settings are overridden, not the whole
    # field.
    for tc in (tagconfigs or []):
        if not tc.field_name:
            continue
        try:
            flags = json.loads(tc.option_flags) if tc.option_flags else {}
        except (ValueError, TypeError):
            flags = {}
        if not isinstance(flags, dict) or not flags:
            continue
        try:
            preset = json.loads(tc.default_value) if tc.default_value else {}
        except (ValueError, TypeError):
            preset = {}
        if not isinstance(preset, dict):
            continue
        for key, flag in flags.items():
            if isinstance(flag, dict) and (flag.get('locked') or flag.get('hidden')) and key in preset:
                ctx[key] = preset[key]

    # Each field is rendered by its field handler — code that lives in a plugin (plugins/<id>/), found
    # through the registry. Handlers escape what they output; nothing from the stored data reaches the
    # page as markup unless a handler deliberately says so (the Markup it returns).
    for tc in (tagconfigs or []):
        field_name, ftype = tc.field_name, tc.field_handler
        if not field_name:
            continue
        if ftype == '':
            # 'None': this field has no input in the ContentElement editor — always fall through to the
            # container's own default_content below, even if a value happens to still be stored from
            # before the field's handler was switched to 'None'.
            ctx[field_name] = ''
            continue
        handler = plugin_registry.fieldhandler(ftype)
        if handler is None:
            # The plugin that provides this handler is not installed or not switched on: the field stays
            # empty (the stored value is kept) and comes back once the plugin is active again.
            plugin_registry.warn_missing_handler(ftype)
            ctx[field_name] = ''
            continue
        rendered = handler.render(RenderContext(field_name=field_name, values=ctx, db=db, tagconfig=tc))
        if rendered is not None:
            ctx[field_name] = rendered

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


def _key_bag_of(content: str):
    """A container default saved as the field's flat key bag (``{"default": …, "default__size": …}``, how
    some instances stored it) as it is; ``None`` for the packed form every handler's ``default_values`` reads."""
    try:
        parsed = json.loads(content)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) and 'default' in parsed else None


def render_default_value(field_handler: str, content: str, db=None) -> str:
    """Render a single ad-hoc value through *field_handler*'s transform,
    reusing the same logic as a regular Contenttype field (TagConfig).

    Used both for a ContentContainer's own fallback content and for the
    admin's live preview of that default while editing it. The 'arrows',
    'icon' and 'pretalx_table' handlers store their multi-part config as
    JSON in *content* (mirroring how a regular field keeps that same shape
    spread across several `<field>__suffix` keys) — every other handler
    treats *content* as the field's plain raw value.
    """
    if not field_handler or not content:
        return ''
    from application.models import TagConfig

    fake_tc = TagConfig(field_name='default', field_handler=field_handler, contentcontainer_id=0)
    handler = plugin_registry.fieldhandler(field_handler)
    ctx = _key_bag_of(content)
    if ctx is None:
        ctx = handler.default_values(content) if handler is not None else {'default': content}
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
