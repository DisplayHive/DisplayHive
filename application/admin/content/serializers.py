"""Shared serialization + container-building helpers for admin Content handlers.

These were previously nested closures inside ``register_admin_content_handlers``.
Hoisted to module level so the read (``queries``) and write (``mutations``)
handler modules can share them. Functions that touch the database take the
Flask-SQLAlchemy ``db`` instance explicitly.
"""

import json
import re

from application.models import ContentElement, Template


def extract_template_css(tpl) -> str:
    """Return all CSS relevant for the preview iframe.

    Combines the standalone `tpl.css` field with every <style> block
    found inside `tpl.html` so that background colours, font sizes and
    other styles defined in the full template HTML are applied.
    """
    if not tpl:
        return ''
    parts = []
    if tpl.css:
        parts.append(tpl.css)
    if tpl.html:
        for block in re.findall(r'<style[^>]*>(.*?)</style>', tpl.html, re.DOTALL | re.IGNORECASE):
            parts.append(block)
    return '\n'.join(parts)


def fmt_dt(dt) -> str | None:
    """Return an ISO-8601 string for a datetime or None."""
    if dt is None:
        return None
    try:
        return dt.strftime('%Y-%m-%dT%H:%M')
    except Exception:
        return str(dt)


def build_containers_for_template(db, template):
    """Return a sorted list of container dicts for *template*, with content counts."""
    containers = []
    for cc in (template.contentcontainers if template else []):
        count = db.session.execute(
            db.select(db.func.count()).select_from(ContentElement).where(ContentElement.contentcontainer == cc.name)
        ).scalar()
        containers.append({
            'id': cc.id,
            'name': cc.name,
            'title': cc.title or cc.name,
            'order': cc.order,
            'contentCount': count,
            'template_name': getattr(template, 'name', None),
        })
    containers.sort(key=lambda x: x['order'])
    return containers


def resolve_preview_css(db):
    """Fetch preview CSS from the default (or first) template."""
    tpl = (
        db.session.execute(db.select(Template).where(Template.isDefault == True)).scalar_one_or_none()
        or db.session.execute(db.select(Template)).scalars().first()
    )
    return extract_template_css(tpl)


def build_content_dict(content, preview_css=''):
    """Serialize a ContentElement ORM object into a dict for admin clients."""
    data = {
        'id': content.id,
        'title': content.title,
        'active': content.active,
        'duration': content.duration,
        'start_time': fmt_dt(getattr(content, 'start_time', None)),
        'end_time': fmt_dt(getattr(content, 'end_time', None)),
        'contentcontainer': content.contentcontainer,
        'contenttypeName': content.contenttype.name if content.contenttype else '',
        'html': content.html or '',
        'preview_css': preview_css,
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
    if content.contenttype and content.contenttype.tagconfigs:
        data['_field_metadata'] = {
            tag.field_name: {
                'label': tag.field_label or tag.field_name,
                'order': tag.order,
                'type': tag.field_handler,
            }
            for tag in sorted(content.contenttype.tagconfigs, key=lambda t: t.order)
        }
    return data
