"""Normalising an uploaded export payload: upgrade old shapes and backfill uuids
(see ``importer.py`` for the identity model)."""

from uuid import uuid4

from .registry import ENTITY_TYPES


def _normalize_legacy_payload(data: dict, version: int):
    """Upgrade an old export shape (< export_version 4) to the modern
    Design/Layout/Contenttype/TagConfig shape in place, so the rest of the
    import pipeline never needs to special-case it. Unchanged best-effort
    logic from before this refactor (see former ``_import_layouts``'s
    legacy branch and ``_import_tagconfigs``'s version handling).
    """
    if version < 4:
        design_rows = data.get('templates', [])
        data['designs'] = design_rows
        default_design = next((r for r in design_rows if r.get('isDefault')), None) or (design_rows[0] if design_rows else None)

        container_rows = data.get('contentcontainers', [])
        next_layout_id = 1
        layout_row = {
            'id': next_layout_id,
            'name': f"{default_design['name']} (imported)" if default_design else 'Imported Layout',
            'description': None,
        }
        data['layouts'] = [layout_row]
        data['layout_container'] = [{'layout_id': next_layout_id, 'contentcontainer_id': c['id']} for c in container_rows]

        for ct in data.get('contenttypes', []):
            ct['layout_id'] = next_layout_id

        ordered = sorted(container_rows, key=lambda c: (c.get('order', 0), c['id']))
        first_container_id = ordered[0]['id'] if ordered else None
        for row in data.get('tagconfigs', []):
            row['contentcontainer_id'] = first_container_id
    elif version == 4:
        content_handler_lookup = {
            h['id']: (h.get('contenttype_id'), h.get('contentcontainer_id'))
            for h in data.get('content_handlers', [])
        }
        for row in data.get('tagconfigs', []):
            contenttype_id, contentcontainer_id = content_handler_lookup.get(row.get('content_handler_id'), (None, None))
            row['contenttype_id'] = contenttype_id
            row['contentcontainer_id'] = contentcontainer_id


def _ensure_uuids(data: dict):
    """Assign a fresh uuid4() to every entity row missing one (legacy files,
    or files from before this refactor). Mutates ``data`` in place."""
    for et in ENTITY_TYPES:
        for row in data.get(et.key, []) or []:
            if not row.get('uuid'):
                row['uuid'] = str(uuid4())


def prepare_import_payload(data: dict) -> dict:
    """Normalize an uploaded export payload (any supported version) into the
    modern shape with a guaranteed 'uuid' on every entity row. Safe to call
    more than once (idempotent). Returns the same dict, mutated in place.
    """
    version = data.get('export_version', 1)
    _normalize_legacy_payload(data, version)
    _ensure_uuids(data)
    return data


def is_legacy_payload(data: dict) -> bool:
    """True when the payload predates per-row uuids (export_version < 9) —
    the selection tree has nothing meaningful to key off, so the frontend
    treats it as select-everything."""
    return data.get('export_version', 1) < 9
