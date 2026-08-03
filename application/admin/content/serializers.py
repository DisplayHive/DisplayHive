"""Shared serialization + container-building helpers for admin Content handlers.

These were previously nested closures inside ``register_admin_content_handlers``.
Hoisted to module level so the read (``queries``) and write (``mutations``)
handler modules can share them. Functions that touch the database take the
Flask-SQLAlchemy ``db`` instance explicitly.
"""

import json


def fmt_dt(dt) -> str | None:
    """Return an ISO-8601 string for a datetime or None."""
    if dt is None:
        return None
    try:
        return dt.strftime('%Y-%m-%dT%H:%M')
    except Exception:
        return str(dt)


def build_content_dict(content, design_payload=None, db=None):
    """Serialize a ContentElement ORM object into a dict for admin clients.

    Includes a Layout-positioned `containers` map (see
    build_scene_containers) and the shared `design_payload` (the active
    Design's {name, html, css, background_effect} — same shape
    build_design_payload/get_design_preview already use, computed once by
    the caller and passed in rather than re-fetched per row) so the admin
    Content list's row-expansion preview can render an accurate as-on-screen
    iframe instead of an unpositioned concatenation of fragments.
    """
    from application.admin.content.helper import build_scene_containers

    data = {
        'id': content.id,
        'title': content.title,
        'active': content.active,
        'duration': content.duration,
        'start_time': fmt_dt(getattr(content, 'start_time', None)),
        'end_time': fmt_dt(getattr(content, 'end_time', None)),
        'contenttypeName': content.contenttype.name if content.contenttype else '',
        'design': design_payload,
        'containers': build_scene_containers(content.contenttype, content.html or '', db=db),
        'screengroups': [
            {'id': sg.id, 'name': sg.name} for sg in content.screengroups
        ] if content.screengroups else [],
    }
    if content.serialized_input:
        try:
            for k, v in json.loads(content.serialized_input).items():
                if k not in data:
                    data[k] = v
        except (json.JSONDecodeError, TypeError):
            pass
    tagconfigs = list(getattr(content.contenttype, 'tagconfigs', None) or []) if content.contenttype else []
    if tagconfigs:
        data['_field_metadata'] = {
            tag.field_name: {
                'label': tag.field_label or tag.field_name,
                'order': tag.order,
                'type': tag.field_handler,
                'contentcontainer_id': tag.contentcontainer_id,
            }
            for tag in tagconfigs
        }
    return data
