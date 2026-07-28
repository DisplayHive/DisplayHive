"""Shared serialization + container-building helpers for admin Content handlers.

These were previously nested closures inside ``register_admin_content_handlers``.
Hoisted to module level so the read (``queries``) and write (``mutations``)
handler modules can share them. Functions that touch the database take the
Flask-SQLAlchemy ``db`` instance explicitly.
"""

import json
import re

from application.models import ContentElement, Design


def extract_design_css(design) -> str:
    """Return all CSS relevant for the preview iframe.

    Combines the standalone `design.css` field with every <style> block
    found inside `design.html` so that background colours, font sizes and
    other styles defined in the full design HTML are applied.
    """
    if not design:
        return ''
    parts = []
    if design.css:
        parts.append(design.css)
    if design.html:
        for block in re.findall(r'<style[^>]*>(.*?)</style>', design.html, re.DOTALL | re.IGNORECASE):
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


def resolve_preview_css(db):
    """Fetch preview CSS from the active (or first) Design."""
    design = (
        db.session.execute(db.select(Design).where(Design.isDefault == True)).scalar_one_or_none()
        or db.session.execute(db.select(Design)).scalars().first()
    )
    return extract_design_css(design)


def build_content_dict(content, preview_css=''):
    """Serialize a ContentElement ORM object into a dict for admin clients."""
    data = {
        'id': content.id,
        'title': content.title,
        'active': content.active,
        'duration': content.duration,
        'start_time': fmt_dt(getattr(content, 'start_time', None)),
        'end_time': fmt_dt(getattr(content, 'end_time', None)),
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
