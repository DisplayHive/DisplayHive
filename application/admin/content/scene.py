"""Composing a layout's containers into the scene HTML a screen shows: per-container
HTML combined across the aspect-ratio variations of a layout."""

from application.utils.aspect_ratio import BASE_RATIO
from .helper import render_container_default


def combine_layout_containers(layout_containers, rendered_by_container: dict, db=None, ratio: str = BASE_RATIO) -> dict:
    """Combine already-rendered per-container HTML (keyed by
    contentcontainer_id, e.g. from render_content_fields/parse_content_html)
    with each container's own Layout position, falling back to the
    container's own default_content when nothing rendered targets it.

    Looking a container up by id in *rendered_by_container* (rather than
    iterating fields/TagConfigs first) means a stale TagConfig — one whose
    contentcontainer_id no longer belongs to *layout_containers* because the
    Layout was edited independently of the Contenttype — is automatically
    excluded: its rendered value just sits under a key nothing here ever
    looks up. Shared by build_scene_containers (already-saved content) and
    the preview_content_element handler (in-progress/unsaved content) so
    there's one implementation of "resolve a scene's positioned containers",
    matching what real screen delivery does in
    application/socketio_handlers/upd_content.py's _build_payload.

    *ratio* picks which aspect-ratio variant's position/size each container
    is placed at (the caller passes that variant's own member containers).

    Returns {contentcontainer_id_str: {top, left, width, height, html}}.
    """
    from application.admin.layouts.helper import container_geometry
    containers = {}
    for c in (layout_containers or []):
        html = rendered_by_container.get(str(c.id)) or render_container_default(c, db=db)
        if not html and not c.show_when_empty:
            continue
        containers[str(c.id)] = {**container_geometry(c, ratio), 'html': html or ''}
    return containers


def build_scene_containers(contenttype, content_html: str, db=None, ratio: str = BASE_RATIO) -> dict:
    """Combine a saved ContentElement's already-rendered per-field HTML
    (its `html` column) with its Contenttype's Layout container positions —
    see combine_layout_containers. Reused by admin previews (Content list,
    Content edit page) so they show exactly what's actually live on screens
    rather than a separately-approximated render.

    Returns {contentcontainer_id_str: {top, left, width, height, html}}.
    """
    from application.utils.design import parse_content_html

    if not contenttype or not contenttype.layout:
        return {}

    rendered_by_container = parse_content_html(content_html, contenttype.tagconfigs or [])
    from application.admin.layouts.helper import containers_for_ratio
    return combine_layout_containers(
        containers_for_ratio(contenttype.layout, ratio), rendered_by_container, db=db, ratio=ratio,
    )


def build_scene_containers_by_ratio(contenttype, content_html: str, db=None) -> dict:
    """build_scene_containers for every aspect ratio the Contenttype's Layout
    has a variant for: {ratio: {contentcontainer_id_str: {...}}}."""
    from application.admin.layouts.helper import layout_ratios

    if not contenttype or not contenttype.layout:
        return {}
    return {
        r: build_scene_containers(contenttype, content_html, db=db, ratio=r)
        for r in layout_ratios(contenttype.layout)
    }
