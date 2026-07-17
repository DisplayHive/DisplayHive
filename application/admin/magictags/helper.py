"""Helper utilities for magic tag substitution."""

import re as _re


def load_magic_tags(db) -> dict:
    """Return all MagicTag records as {lowercase_name: rendered_value}.

    A 'text' tag renders its `value` literally. A 'list' tag renders the
    value of the entry in its assigned value list whose key matches `value`
    (or '' if the list/key isn't found).
    """
    try:
        from application.models import MagicTag, MagicTagValueListEntry
        rows = db.session.execute(db.select(MagicTag)).scalars().all()
        result = {}
        for v in rows:
            if getattr(v, 'type', 'text') == 'list':
                entry = None
                if v.value_list_id:
                    entry = db.session.execute(
                        db.select(MagicTagValueListEntry).where(
                            MagicTagValueListEntry.value_list_id == v.value_list_id,
                            MagicTagValueListEntry.key == v.value,
                        )
                    ).scalars().first()
                result[v.name.lower()] = entry.value if entry else ''
            else:
                result[v.name.lower()] = v.value
        return result
    except Exception:
        return {}


def substitute_magic_tags(html: str, vars_dict: dict) -> str:
    """Replace {{var_<name>}} placeholders in *html* with values from *vars_dict*.

    Matching is case-insensitive. Must be called before the container-tag regex
    so that var_ tags are not converted into data-container divs.
    """
    if not html or not vars_dict:
        return html

    def _replace(m):
        return vars_dict.get(m.group(1).lower(), '')

    return _re.sub(r'\{\{\s*var_([a-zA-Z0-9_]+)\s*\}\}', _replace, html)
