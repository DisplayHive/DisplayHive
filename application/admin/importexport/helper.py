"""Helper functions for selective database import/export.

Every primary/independently-selectable entity (see ``registry.py``) carries a
stable ``uuid`` column, which is the authoritative identity used here:

- Export can be filtered to an arbitrary subset of entities (``selection``),
  automatically expanded to include every hard-FK dependency (a Contenttype
  pulls in its Layout, which pulls in that Layout's ContentContainers, etc —
  see ``registry.py``'s ``depends_on`` and the ``_resolve_export_selection``/
  ``_resolve_import_selection`` fixpoint walks below).
- Import supports two modes:
    - ``reset``: wipe the *entire* database (always all-or-nothing,
      independent of what's selected for import — matches the old
      behaviour), then insert the selection fresh.
    - ``merge``: add into the existing database. A row whose ``uuid``
      already exists locally is a *conflict*, resolved per
      ``conflict_resolution`` (skip the import row / overwrite the local
      row in place). Rows that don't conflict are always inserted with a
      **fresh local primary key** — the file's own ``id`` is never reused —
      so two instances' id spaces never collide. A per-type
      ``{old_file_id: new_local_id}`` map is built as rows are
      inserted/matched and used to remap every FK/association column when
      inserting dependent/support rows (this replaces the old
      ``id=row['id']`` inserts and removes the need to ever reset
      autoincrement sequences).
- Legacy exports (``export_version`` < 9, i.e. from before this uuid-based
  rewrite — including the pre-Design/Layout v3 format) have no ``uuid``
  field on their rows: one is generated at load time so the same insert
  path handles them unchanged. Versions < 4 additionally get their
  Design/Layout/TagConfig shape upgraded to the modern schema first (see
  ``_normalize_legacy_payload``) — this best-effort upgrade logic is
  unchanged from before this refactor.
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from .registry import ENTITY_TYPES, ENTITY_TYPES_BY_KEY, get_model

logger = logging.getLogger(__name__)

EXPORT_VERSION = 9  # bumped from 8: every row now carries a stable 'uuid' alongside 'id'.


def _support_models():
    from application.models import TagConfig, MagicTagValueListEntry
    from application.models.base import screengroup_screen, content_element_screengroup
    from application.models.content import (
        layout_container, DesignGradient, DesignContainerStyle, DesignGlobalStyle,
    )
    return dict(
        TagConfig=TagConfig, MagicTagValueListEntry=MagicTagValueListEntry,
        screengroup_screen=screengroup_screen, content_element_screengroup=content_element_screengroup,
        layout_container=layout_container, DesignGradient=DesignGradient,
        DesignContainerStyle=DesignContainerStyle, DesignGlobalStyle=DesignGlobalStyle,
    )


# ---------------------------------------------------------------------------
# Export — one row-serialiser per entity type, filtered to a resolved id set.
# ---------------------------------------------------------------------------

def _row_screen(s):
    return {
        'id': s.id, 'uuid': s.uuid,
        'active': bool(s.active),
        'lastseen': s.lastseen.isoformat() if s.lastseen else None,
        'name': s.name,
        'resolution_width': s.resolution_width,
        'resolution_height': s.resolution_height,
        'debug': bool(s.debug),
        'monitoring_enabled': bool(s.monitoring_enabled),
    }


def _row_screengroup(sg):
    return {'id': sg.id, 'uuid': sg.uuid, 'name': sg.name, 'is_one_screen': bool(sg.is_one_screen)}


def _row_gradient(g):
    return {
        'id': g.id, 'uuid': g.uuid,
        'name': g.name, 'type': g.type, 'repeating': bool(g.repeating), 'angle': g.angle,
        'shape': g.shape, 'size': g.size, 'position_x': g.position_x, 'position_y': g.position_y,
        'stops': g.stops,
    }


def _row_container(c):
    return {
        'id': c.id, 'uuid': c.uuid,
        'name': c.name, 'order': c.order, 'top': c.top, 'left': c.left,
        'width': c.width, 'height': c.height,
        'default_field_handler': c.default_field_handler, 'default_content': c.default_content,
    }


def _row_design(d):
    return {
        'id': d.id, 'uuid': d.uuid,
        'name': d.name, 'description': d.description, 'html': d.html, 'css': d.css,
        'isDefault': bool(d.isDefault),
        'background_color': d.background_color, 'background_image_url': d.background_image_url,
        'background_repeat': d.background_repeat, 'background_size': d.background_size,
        'background_opacity': d.background_opacity,
        'background_effect': d.background_effect, 'background_effect_settings': d.background_effect_settings,
        'default_colors': d.default_colors,
    }


def _row_layout(lo):
    return {'id': lo.id, 'uuid': lo.uuid, 'name': lo.name, 'description': lo.description}


def _row_contenttype(ct):
    return {'id': ct.id, 'uuid': ct.uuid, 'name': ct.name, 'description': ct.description, 'layout_id': ct.layout_id}


def _row_content_element(m):
    return {
        'id': m.id, 'uuid': m.uuid,
        'active': bool(m.active), 'title': m.title, 'html': m.html, 'duration': m.duration,
        'serialized_input': m.serialized_input,
        'start_time': m.start_time.isoformat() if m.start_time else None,
        'end_time': m.end_time.isoformat() if m.end_time else None,
        'contenttype_id': m.contenttype_id,
    }


def _row_media(med):
    return {
        'id': med.id, 'uuid': med.uuid,
        'filename': med.filename, 'title': med.title, 'tags': med.tags,
        'folder_path': med.folder_path, 'mime_type': med.mime_type,
        'file_size': getattr(med, 'file_size', None),
        'created_at': med.created_at.isoformat() if med.created_at else None,
    }


def _row_device(d, selected_screen_ids):
    return {
        'id': d.id, 'uuid': d.uuid,
        'devicekey': d.devicekey, 'name': d.name, 'registration_token': d.registration_token,
        'find': bool(d.find), 'is_online': bool(d.is_online),
        'created_at': d.created_at.isoformat() if d.created_at else None,
        'last_connected_at': d.last_connected_at.isoformat() if d.last_connected_at else None,
        'is_active': bool(d.is_active),
        'max_resolution_width': d.max_resolution_width,
        'max_resolution_height': d.max_resolution_height,
        # Soft/nullable relation: only keep the reference if the Screen is also in the export.
        'screen_id': d.screen_id if d.screen_id in selected_screen_ids else None,
    }


def _row_magic_tag_value_list(l):
    return {
        'id': l.id, 'uuid': l.uuid, 'name': l.name,
        'entries': [{'id': e.id, 'key': e.key, 'value': e.value} for e in l.entries],
    }


def _row_magic_tag(v):
    return {
        'id': v.id, 'uuid': v.uuid,
        'name': v.name, 'value': v.value, 'description': v.description or '',
        'type': v.type or 'text', 'value_list_id': v.value_list_id,
    }


def _resolve_export_selection(db, selection):
    """selection: dict[key, list[uuid]] or None (-> everything).

    Returns (selected_ids, all_rows) where selected_ids is
    dict[key, set[local id]], the fully dependency-closed set of rows to
    export for each entity type, and all_rows is dict[key, list[model
    instance]] (every row of that type currently in the DB — export
    functions filter this list down to selected_ids).
    """
    all_rows = {et.key: db.session.execute(db.select(get_model(et))).scalars().all() for et in ENTITY_TYPES}
    uuid_to_id = {key: {r.uuid: r.id for r in rows} for key, rows in all_rows.items()}

    if selection is None:
        selected = {key: {r.id for r in rows} for key, rows in all_rows.items()}
    else:
        selected = {
            key: {uuid_to_id[key][u] for u in (selection.get(key) or []) if u in uuid_to_id[key]}
            for key in uuid_to_id
        }

    sm = _support_models()
    by_id = {key: {r.id: r for r in rows} for key, rows in all_rows.items()}

    def _pull_in_media_referenced_by(text):
        """Media isn't a hard FK anywhere — image/wysiwyg fields embed the
        media's serving URL as plain text inside various free-text columns.
        Without this scan, a selective export silently omits media that's
        actually displayed/used, leaving broken images after import."""
        from application.utils.design import media_file_urls

        found_new = False
        for med in all_rows['media']:
            if med.id in selected['media']:
                continue
            url, _preview_url = media_file_urls(med)
            if url in text:
                selected['media'].add(med.id)
                found_new = True
        return found_new

    changed = True
    while changed:
        changed = False
        if selected['designs']:
            for r in db.session.execute(db.select(sm['DesignGradient']).where(sm['DesignGradient'].design_id.in_(selected['designs']))).scalars():
                if r.gradient_id not in selected['gradients']:
                    selected['gradients'].add(r.gradient_id)
                    changed = True
            for r in db.session.execute(db.select(sm['DesignContainerStyle']).where(sm['DesignContainerStyle'].design_id.in_(selected['designs']))).scalars():
                if r.contentcontainer_id not in selected['contentcontainers']:
                    selected['contentcontainers'].add(r.contentcontainer_id)
                    changed = True
            for design_id in list(selected['designs']):
                d = by_id['designs'].get(design_id)
                if d and d.background_image_url and _pull_in_media_referenced_by(d.background_image_url):
                    changed = True
        if selected['contentcontainers']:
            for cid in list(selected['contentcontainers']):
                c = by_id['contentcontainers'].get(cid)
                if c and c.default_content and _pull_in_media_referenced_by(c.default_content):
                    changed = True
            # Reverse edge: a container's font/background-color etc. lives on
            # whichever Design(s) style it (DesignContainerStyle) — without
            # this, selecting a container that isn't reached via a Design
            # silently drops its styling (and that Design's other properties,
            # e.g. its default color palette) from the export.
            for r in db.session.execute(db.select(sm['DesignContainerStyle']).where(sm['DesignContainerStyle'].contentcontainer_id.in_(selected['contentcontainers']))).scalars():
                if r.design_id not in selected['designs']:
                    selected['designs'].add(r.design_id)
                    changed = True
        if selected['layouts']:
            for lid, cid in db.session.execute(db.select(sm['layout_container']).where(sm['layout_container'].c.layout_id.in_(selected['layouts']))).fetchall():
                if cid not in selected['contentcontainers']:
                    selected['contentcontainers'].add(cid)
                    changed = True
        if selected['contenttypes']:
            for ct_id in list(selected['contenttypes']):
                ct = by_id['contenttypes'].get(ct_id)
                if ct and ct.layout_id and ct.layout_id not in selected['layouts']:
                    selected['layouts'].add(ct.layout_id)
                    changed = True
        if selected['content_elements']:
            for ce_id in list(selected['content_elements']):
                ce = by_id['content_elements'].get(ce_id)
                if ce and ce.contenttype_id and ce.contenttype_id not in selected['contenttypes']:
                    selected['contenttypes'].add(ce.contenttype_id)
                    changed = True
                if ce and _pull_in_media_referenced_by(f"{ce.serialized_input or ''} {ce.html or ''}"):
                    changed = True
        if selected['magic_tags']:
            for mt_id in list(selected['magic_tags']):
                mt = by_id['magic_tags'].get(mt_id)
                if mt and mt.value_list_id and mt.value_list_id not in selected['magic_tag_value_lists']:
                    selected['magic_tag_value_lists'].add(mt.value_list_id)
                    changed = True

    return selected, all_rows


def export_database(app, db, selection=None):
    """Export the database (or a selection of it) to a JSON-serialisable dict.

    ``selection``: ``{entity_type_key: [uuid, ...]}`` or ``None`` for
    everything. The selection is expanded to its full dependency closure
    before exporting (see ``_resolve_export_selection``).
    """
    sm = _support_models()

    with app.app_context():
        selected, all_rows = _resolve_export_selection(db, selection)

        def rows_of(key):
            return [r for r in all_rows[key] if r.id in selected[key]]

        design_gradients = [
            {'id': r.id, 'design_id': r.design_id, 'gradient_id': r.gradient_id, 'order': r.order}
            for r in db.session.execute(db.select(sm['DesignGradient'])).scalars()
            if r.design_id in selected['designs'] and r.gradient_id in selected['gradients']
        ]
        design_container_styles = [
            {'id': r.id, 'design_id': r.design_id, 'contentcontainer_id': r.contentcontainer_id, 'property': r.property, 'value': r.value}
            for r in db.session.execute(db.select(sm['DesignContainerStyle'])).scalars()
            if r.design_id in selected['designs'] and r.contentcontainer_id in selected['contentcontainers']
        ]
        design_global_styles = [
            {'id': r.id, 'design_id': r.design_id, 'property': r.property, 'value': r.value}
            for r in db.session.execute(db.select(sm['DesignGlobalStyle'])).scalars()
            if r.design_id in selected['designs']
        ]
        layout_container_rows = [
            {'layout_id': lid, 'contentcontainer_id': cid}
            for lid, cid in db.session.execute(db.select(sm['layout_container'])).fetchall()
            if lid in selected['layouts'] and cid in selected['contentcontainers']
        ]
        tagconfigs = [
            {
                'id': tc.id, 'contenttype_id': tc.contenttype_id, 'contentcontainer_id': tc.contentcontainer_id,
                'field_name': tc.field_name, 'field_handler': tc.field_handler, 'field_label': tc.field_label,
                'required': bool(tc.required), 'default_value': tc.default_value, 'order': tc.order,
                'option_flags': tc.option_flags,
            }
            for tc in db.session.execute(db.select(sm['TagConfig'])).scalars()
            if tc.contenttype_id in selected['contenttypes'] and (tc.contentcontainer_id is None or tc.contentcontainer_id in selected['contentcontainers'])
        ]
        screengroup_screen_rows = [
            {'screen_id': sid, 'screengroup_id': sgid}
            for sid, sgid in db.session.execute(db.select(sm['screengroup_screen'])).fetchall()
            if sid in selected['screens'] and sgid in selected['screengroups']
        ]
        content_element_screengroup_rows = [
            {'content_element_id': ceid, 'screengroup_id': sgid}
            for ceid, sgid in db.session.execute(db.select(sm['content_element_screengroup'])).fetchall()
            if ceid in selected['content_elements'] and sgid in selected['screengroups']
        ]

        return {
            'export_version': EXPORT_VERSION,
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'screens': [_row_screen(s) for s in rows_of('screens')],
            'screengroups': [_row_screengroup(sg) for sg in rows_of('screengroups')],
            'screengroup_screen': screengroup_screen_rows,
            'designs': [_row_design(d) for d in rows_of('designs')],
            'gradients': [_row_gradient(g) for g in rows_of('gradients')],
            'design_gradients': design_gradients,
            'design_container_styles': design_container_styles,
            'design_global_styles': design_global_styles,
            'layouts': [_row_layout(lo) for lo in rows_of('layouts')],
            'layout_container': layout_container_rows,
            'contentcontainers': [_row_container(c) for c in rows_of('contentcontainers')],
            'contenttypes': [_row_contenttype(ct) for ct in rows_of('contenttypes')],
            'tagconfigs': tagconfigs,
            'content_elements': [_row_content_element(m) for m in rows_of('content_elements')],
            'content_element_screengroup': content_element_screengroup_rows,
            'media': [_row_media(med) for med in rows_of('media')],
            'devices': [_row_device(d, selected['screens']) for d in rows_of('devices')],
            'magic_tag_value_lists': [_row_magic_tag_value_list(l) for l in rows_of('magic_tag_value_lists')],
            'magic_tags': [_row_magic_tag(v) for v in rows_of('magic_tags')],
        }


def export_manifest(app, db):
    """Lightweight per-type listing (uuid/id/label) for building the export
    selection tree, without serialising full row data."""
    with app.app_context():
        manifest = {}
        for et in ENTITY_TYPES:
            rows = db.session.execute(db.select(get_model(et))).scalars().all()
            manifest[et.key] = [
                {'uuid': r.uuid, 'id': r.id, 'label': getattr(r, et.label_field, None) or f'#{r.id}'}
                for r in rows
            ]
        return manifest


# ---------------------------------------------------------------------------
# Import — legacy normalization, uuid backfill, selection resolution, and a
# generic per-type upsert engine shared by reset and merge modes.
# ---------------------------------------------------------------------------

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


def _resolve_import_selection(data: dict, selection):
    """Mirror of ``_resolve_export_selection`` but walking the parsed file's
    own rows (keyed by the file's local 'id') instead of the DB.

    Returns (selected, all_rows) where selected is dict[key, set[file id]].
    """
    all_rows = {et.key: (data.get(et.key) or []) for et in ENTITY_TYPES}
    uuid_to_id = {key: {r['uuid']: r['id'] for r in rows} for key, rows in all_rows.items()}
    by_id = {key: {r['id']: r for r in rows} for key, rows in all_rows.items()}

    if selection is None:
        selected = {key: {r['id'] for r in rows} for key, rows in all_rows.items()}
    else:
        selected = {
            key: {uuid_to_id[key][u] for u in (selection.get(key) or []) if u in uuid_to_id[key]}
            for key in uuid_to_id
        }

    def _pull_in_media_referenced_by(text):
        """Mirror of the same helper in ``_resolve_export_selection``."""
        from application.utils.design import media_file_urls

        found_new = False
        for med in all_rows['media']:
            if med['id'] in selected['media']:
                continue
            url, _preview_url = media_file_urls(med)
            if url in text:
                selected['media'].add(med['id'])
                found_new = True
        return found_new

    changed = True
    while changed:
        changed = False
        if selected['designs']:
            for r in data.get('design_gradients', []):
                if r['design_id'] in selected['designs'] and r['gradient_id'] not in selected['gradients']:
                    selected['gradients'].add(r['gradient_id'])
                    changed = True
            for r in data.get('design_container_styles', []):
                if r['design_id'] in selected['designs'] and r['contentcontainer_id'] not in selected['contentcontainers']:
                    selected['contentcontainers'].add(r['contentcontainer_id'])
                    changed = True
            for design_id in list(selected['designs']):
                d = by_id['designs'].get(design_id)
                if d and d.get('background_image_url') and _pull_in_media_referenced_by(d['background_image_url']):
                    changed = True
        if selected['contentcontainers']:
            for cid in list(selected['contentcontainers']):
                c = by_id['contentcontainers'].get(cid)
                if c and c.get('default_content') and _pull_in_media_referenced_by(c['default_content']):
                    changed = True
            # Reverse edge — see the matching comment in _resolve_export_selection.
            for r in data.get('design_container_styles', []):
                if r['contentcontainer_id'] in selected['contentcontainers'] and r['design_id'] not in selected['designs']:
                    selected['designs'].add(r['design_id'])
                    changed = True
        if selected['layouts']:
            for r in data.get('layout_container', []):
                if r['layout_id'] in selected['layouts'] and r['contentcontainer_id'] not in selected['contentcontainers']:
                    selected['contentcontainers'].add(r['contentcontainer_id'])
                    changed = True
        if selected['contenttypes']:
            for ct_id in list(selected['contenttypes']):
                ct = by_id['contenttypes'].get(ct_id)
                if ct and ct.get('layout_id') and ct['layout_id'] not in selected['layouts']:
                    selected['layouts'].add(ct['layout_id'])
                    changed = True
        if selected['content_elements']:
            for ce_id in list(selected['content_elements']):
                ce = by_id['content_elements'].get(ce_id)
                if ce and ce.get('contenttype_id') and ce['contenttype_id'] not in selected['contenttypes']:
                    selected['contenttypes'].add(ce['contenttype_id'])
                    changed = True
                if ce and _pull_in_media_referenced_by(f"{ce.get('serialized_input') or ''} {ce.get('html') or ''}"):
                    changed = True
        if selected['magic_tags']:
            for mt_id in list(selected['magic_tags']):
                mt = by_id['magic_tags'].get(mt_id)
                if mt and mt.get('value_list_id') and mt['value_list_id'] not in selected['magic_tag_value_lists']:
                    selected['magic_tag_value_lists'].add(mt['value_list_id'])
                    changed = True

    return selected, all_rows


def import_manifest(data: dict, app, db) -> dict:
    """Given a parsed (already ``prepare_import_payload``'d) export, return
    the same per-type ``[{uuid, id, label}]`` shape as ``export_manifest``,
    each item flagged ``conflict: bool`` (a row with that uuid already
    exists locally)."""
    with app.app_context():
        manifest = {}
        for et in ENTITY_TYPES:
            model = get_model(et)
            local_uuids = {row[0] for row in db.session.execute(db.select(model.uuid)).all()}
            rows = data.get(et.key) or []
            manifest[et.key] = [
                {
                    'uuid': row['uuid'],
                    'id': row['id'],
                    'label': row.get(et.label_field) or f"#{row['id']}",
                    'conflict': row['uuid'] in local_uuids,
                }
                for row in rows
            ]
        return manifest


def _reset_postgres_sequences(db):
    """On PostgreSQL, reset every auto-increment sequence to the highest
    explicitly-inserted id — otherwise the next INSERT reuses an id already
    present in the table and raises a UniqueViolation. No-op on SQLite,
    which doesn't use sequences.

    Needed again because reset-mode import now inserts rows (and their
    support/child rows) with their original explicit ids (see
    ``_ImportContext.upsert`` and the design/layout/contenttype/magic-tag
    support-row builders) rather than always relying on autoincrement.
    """
    db_uri = db.engine.url.render_as_string(hide_password=False)
    if not db_uri.startswith('postgresql'):
        return
    sequences = [
        ('screen', 'id'), ('screengroup', 'id'), ('design', 'id'), ('gradient', 'id'),
        ('design_gradient', 'id'), ('design_container_style', 'id'), ('design_global_style', 'id'),
        ('layout', 'id'), ('contenttype', 'id'), ('tagconfig', 'id'), ('contentcontainer', 'id'),
        ('content_element', 'id'), ('media', 'id'), ('device', 'id'),
        ('magic_tag_value_list', 'id'), ('magic_tag_value_list_entry', 'id'), ('magic_tag', 'id'),
    ]
    for table, col in sequences:
        db.session.execute(db.text(
            f"SELECT setval(pg_get_serial_sequence('{table}', '{col}'), "
            f"COALESCE(MAX({col}), 0)) FROM {table}"
        ))


def _clear_all_tables(db, models):
    """Delete all rows from every importable table, most-dependent first."""
    (content_element_screengroup, screengroup_screen, layout_container, TagConfig,
     ContentElement, Device, Screen, Screengroup, DesignContainerStyle, DesignGlobalStyle,
     ContentContainer, Contenttype, Layout, DesignGradient, Design, Gradient, Media,
     MagicTag, MagicTagValueListEntry, MagicTagValueList) = models

    db.session.execute(db.delete(content_element_screengroup))
    db.session.execute(db.delete(screengroup_screen))
    db.session.execute(db.delete(layout_container))
    db.session.execute(db.delete(TagConfig))
    db.session.execute(db.delete(ContentElement))
    db.session.execute(db.delete(Device))
    db.session.execute(db.delete(Screen))
    db.session.execute(db.delete(Screengroup))
    db.session.execute(db.delete(DesignContainerStyle))
    db.session.execute(db.delete(DesignGlobalStyle))
    db.session.execute(db.delete(ContentContainer))
    db.session.execute(db.delete(Contenttype))
    db.session.execute(db.delete(Layout))
    db.session.execute(db.delete(DesignGradient))
    db.session.execute(db.delete(Design))
    db.session.execute(db.delete(Gradient))
    db.session.execute(db.delete(Media))
    db.session.execute(db.delete(MagicTag))
    db.session.execute(db.delete(MagicTagValueListEntry))
    db.session.execute(db.delete(MagicTagValueList))
    db.session.commit()


def _conflict_action(conflict_resolution, row_uuid) -> str:
    """conflict_resolution: 'skip' | 'overwrite' (applies to every conflict),
    or {'default': 'skip'|'overwrite', 'overrides': {uuid: 'skip'|'overwrite'}}
    for a global default with per-item exceptions. Defaults to 'skip'."""
    if isinstance(conflict_resolution, dict):
        overrides = conflict_resolution.get('overrides') or {}
        if row_uuid in overrides:
            return overrides[row_uuid]
        return conflict_resolution.get('default') or 'skip'
    return conflict_resolution or 'skip'


class _ImportContext:
    """Bag of state threaded through the per-type import steps: the parsed
    file, the resolved (dependency-closed) file-id selection, the running
    old-file-id -> new-local-id maps per type, and merge configuration."""

    def __init__(self, db, data, selected, mode, conflict_resolution):
        self.db = db
        self.data = data
        self.selected = selected
        self.mode = mode
        self.conflict_resolution = conflict_resolution
        self.id_map = {et.key: {} for et in ENTITY_TYPES}
        # action taken per type per file-id: 'inserted' | 'overwritten' | 'skipped'
        self.action = {et.key: {} for et in ENTITY_TYPES}

    def rows(self, key):
        selected_ids = self.selected[key]
        return [r for r in (self.data.get(key) or []) if r['id'] in selected_ids]

    def upsert(self, key, build_kwargs):
        """Generic upsert loop for a simple (childless-on-its-own-row) type.
        ``build_kwargs(row)`` returns the model constructor kwargs (already
        FK-remapped via self.id_map, excluding id/uuid)."""
        db = self.db
        model = get_model(ENTITY_TYPES_BY_KEY[key])
        local_by_uuid = {}
        if self.mode == 'merge':
            local_by_uuid = {r.uuid: r for r in db.session.execute(db.select(model)).scalars()}

        for row in self.rows(key):
            existing = local_by_uuid.get(row['uuid'])
            if existing is not None:
                action = _conflict_action(self.conflict_resolution, row['uuid'])
                if action == 'overwrite':
                    for field, value in build_kwargs(row).items():
                        setattr(existing, field, value)
                    self.action[key][row['id']] = 'overwritten'
                else:
                    self.action[key][row['id']] = 'skipped'
                self.id_map[key][row['id']] = existing.id
            else:
                extra = {'id': row['id']} if self.mode == 'reset' else {}
                obj = model(uuid=row['uuid'], **extra, **build_kwargs(row))
                db.session.add(obj)
                db.session.flush()
                self.id_map[key][row['id']] = obj.id
                self.action[key][row['id']] = 'inserted'
        db.session.flush()


def _import_screens(ctx):
    ctx.upsert('screens', lambda row: dict(
        active=bool(row.get('active', True)),
        lastseen=datetime.fromisoformat(row['lastseen']) if row.get('lastseen') else datetime.now(timezone.utc),
        name=row['name'],
        resolution_width=row.get('resolution_width') or 0,
        resolution_height=row.get('resolution_height') or 0,
        debug=bool(row.get('debug', False)),
        monitoring_enabled=bool(row.get('monitoring_enabled', True)),
    ))


def _import_screengroups(ctx):
    ctx.upsert('screengroups', lambda row: dict(
        name=row['name'],
        is_one_screen=bool(row.get('is_one_screen', False)),
    ))


def _import_gradients(ctx):
    ctx.upsert('gradients', lambda row: dict(
        name=row['name'], type=row.get('type') or 'linear', repeating=bool(row.get('repeating', False)),
        angle=row.get('angle', 180) or 180, shape=row.get('shape'), size=row.get('size'),
        position_x=row.get('position_x', 50.0) or 50.0, position_y=row.get('position_y', 50.0) or 50.0,
        stops=row.get('stops') or '[]',
    ))


def _import_contentcontainers(ctx):
    ctx.upsert('contentcontainers', lambda row: dict(
        name=row['name'], order=row.get('order') or 0,
        top=row.get('top', 0) or 0, left=row.get('left', 0) or 0,
        width=row.get('width', 100) or 100, height=row.get('height', 100) or 100,
        default_field_handler=row.get('default_field_handler'), default_content=row.get('default_content'),
    ))


def _import_designs(ctx):
    sm = _support_models()
    db = ctx.db
    ctx.upsert('designs', lambda row: dict(
        name=row['name'], description=row.get('description'), html=row.get('html') or '',
        css=row.get('css'), isDefault=bool(row.get('isDefault', False)),
        background_color=row.get('background_color'), background_image_url=row.get('background_image_url'),
        background_repeat=row.get('background_repeat'), background_size=row.get('background_size'),
        background_opacity=row.get('background_opacity'), background_effect=row.get('background_effect'),
        background_effect_settings=row.get('background_effect_settings'),
        default_colors=row.get('default_colors'),
    ))

    for file_id, local_id in ctx.id_map['designs'].items():
        action = ctx.action['designs'][file_id]
        if action == 'skipped':
            continue
        if action == 'overwritten':
            db.session.execute(db.delete(sm['DesignGradient']).where(sm['DesignGradient'].design_id == local_id))
            db.session.execute(db.delete(sm['DesignContainerStyle']).where(sm['DesignContainerStyle'].design_id == local_id))
            db.session.execute(db.delete(sm['DesignGlobalStyle']).where(sm['DesignGlobalStyle'].design_id == local_id))

        for dg in ctx.data.get('design_gradients', []):
            if dg['design_id'] == file_id and dg['gradient_id'] in ctx.id_map['gradients']:
                extra = {'id': dg['id']} if ctx.mode == 'reset' else {}
                db.session.add(sm['DesignGradient'](
                    **extra, design_id=local_id, gradient_id=ctx.id_map['gradients'][dg['gradient_id']], order=dg.get('order') or 0,
                ))
        for dcs in ctx.data.get('design_container_styles', []):
            if dcs['design_id'] == file_id and dcs['contentcontainer_id'] in ctx.id_map['contentcontainers']:
                extra = {'id': dcs['id']} if ctx.mode == 'reset' else {}
                db.session.add(sm['DesignContainerStyle'](
                    **extra, design_id=local_id, contentcontainer_id=ctx.id_map['contentcontainers'][dcs['contentcontainer_id']],
                    property=dcs['property'], value=dcs.get('value'),
                ))
        for dgs in ctx.data.get('design_global_styles', []):
            if dgs['design_id'] == file_id:
                extra = {'id': dgs['id']} if ctx.mode == 'reset' else {}
                db.session.add(sm['DesignGlobalStyle'](
                    **extra, design_id=local_id, property=dgs['property'], value=dgs.get('value'),
                ))
    db.session.flush()


def _import_layouts(ctx):
    sm = _support_models()
    db = ctx.db
    ctx.upsert('layouts', lambda row: dict(name=row['name'], description=row.get('description')))

    for file_id, local_id in ctx.id_map['layouts'].items():
        action = ctx.action['layouts'][file_id]
        if action == 'skipped':
            continue
        if action == 'overwritten':
            db.session.execute(db.delete(sm['layout_container']).where(sm['layout_container'].c.layout_id == local_id))
        for lc in ctx.data.get('layout_container', []):
            if lc['layout_id'] == file_id and lc['contentcontainer_id'] in ctx.id_map['contentcontainers']:
                db.session.execute(sm['layout_container'].insert().values(
                    layout_id=local_id, contentcontainer_id=ctx.id_map['contentcontainers'][lc['contentcontainer_id']],
                ))
    db.session.flush()


def _import_contenttypes(ctx):
    sm = _support_models()
    db = ctx.db
    ctx.upsert('contenttypes', lambda row: dict(
        name=row['name'], description=row.get('description'),
        layout_id=ctx.id_map['layouts'].get(row.get('layout_id')),
    ))

    for file_id, local_id in ctx.id_map['contenttypes'].items():
        action = ctx.action['contenttypes'][file_id]
        if action == 'skipped':
            continue
        if action == 'overwritten':
            db.session.execute(db.delete(sm['TagConfig']).where(sm['TagConfig'].contenttype_id == local_id))
        for tc in ctx.data.get('tagconfigs', []):
            if tc['contenttype_id'] != file_id:
                continue
            contentcontainer_id = ctx.id_map['contentcontainers'].get(tc.get('contentcontainer_id'))
            extra = {'id': tc['id']} if ctx.mode == 'reset' else {}
            db.session.add(sm['TagConfig'](
                **extra, contenttype_id=local_id, contentcontainer_id=contentcontainer_id,
                field_name=tc['field_name'], field_handler=tc['field_handler'], field_label=tc.get('field_label'),
                required=bool(tc.get('required', False)), default_value=tc.get('default_value'), order=tc.get('order') or 0,
                option_flags=tc.get('option_flags'),
            ))
    db.session.flush()


def _import_content_elements(ctx):
    ctx.upsert('content_elements', lambda row: dict(
        active=bool(row.get('active', True)), title=row.get('title') or '', html=row.get('html') or '',
        duration=row.get('duration') or 10, serialized_input=row.get('serialized_input') or '',
        start_time=datetime.fromisoformat(row['start_time']) if row.get('start_time') else None,
        end_time=datetime.fromisoformat(row['end_time']) if row.get('end_time') else None,
        contenttype_id=ctx.id_map['contenttypes'].get(row.get('contenttype_id')),
    ))


def _import_media(ctx):
    ctx.upsert('media', lambda row: dict(
        filename=row['filename'], title=row.get('title'), tags=row.get('tags'),
        folder_path=row.get('folder_path') or '', mime_type=row.get('mime_type'), file_size=row.get('file_size'),
        created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else datetime.now(timezone.utc),
    ))


def _import_devices(ctx):
    ctx.upsert('devices', lambda row: dict(
        devicekey=row['devicekey'], name=row.get('name'), registration_token=row.get('registration_token'),
        find=bool(row.get('find', False)), is_online=False,
        created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else datetime.now(timezone.utc),
        last_connected_at=datetime.fromisoformat(row['last_connected_at']) if row.get('last_connected_at') else None,
        is_active=bool(row.get('is_active', True)),
        max_resolution_width=row.get('max_resolution_width'),
        max_resolution_height=row.get('max_resolution_height'),
        screen_id=ctx.id_map['screens'].get(row.get('screen_id')),
    ))


def _import_magic_tag_value_lists(ctx):
    sm = _support_models()
    db = ctx.db
    ctx.upsert('magic_tag_value_lists', lambda row: dict(name=row['name']))

    for file_id, local_id in ctx.id_map['magic_tag_value_lists'].items():
        action = ctx.action['magic_tag_value_lists'][file_id]
        if action == 'skipped':
            continue
        if action == 'overwritten':
            db.session.execute(db.delete(sm['MagicTagValueListEntry']).where(sm['MagicTagValueListEntry'].value_list_id == local_id))
        row = next(r for r in ctx.data.get('magic_tag_value_lists', []) if r['id'] == file_id)
        for entry in row.get('entries', []):
            extra = {'id': entry['id']} if ctx.mode == 'reset' else {}
            db.session.add(sm['MagicTagValueListEntry'](
                **extra, value_list_id=local_id, key=entry['key'], value=entry.get('value') or '',
            ))
    db.session.flush()


def _import_magic_tags(ctx):
    ctx.upsert('magic_tags', lambda row: dict(
        name=row['name'], value=row['value'], description=row.get('description') or '',
        type=row.get('type') or 'text',
        value_list_id=ctx.id_map['magic_tag_value_lists'].get(row.get('value_list_id')),
    ))


def _import_soft_associations(ctx):
    """screengroup_screen / content_element_screengroup: only written when
    both endpoints ended up selected (and processed) — see registry.py."""
    sm = _support_models()
    db = ctx.db

    existing_ss = {(r[0], r[1]) for r in db.session.execute(db.select(sm['screengroup_screen'])).fetchall()}
    for row in ctx.data.get('screengroup_screen', []):
        screen_id = ctx.id_map['screens'].get(row['screen_id'])
        screengroup_id = ctx.id_map['screengroups'].get(row['screengroup_id'])
        if screen_id is None or screengroup_id is None:
            continue
        if (screen_id, screengroup_id) in existing_ss:
            continue
        db.session.execute(sm['screengroup_screen'].insert().values(screen_id=screen_id, screengroup_id=screengroup_id))
        existing_ss.add((screen_id, screengroup_id))

    existing_ces = {(r[0], r[1]) for r in db.session.execute(db.select(sm['content_element_screengroup'])).fetchall()}
    for row in ctx.data.get('content_element_screengroup', []):
        content_element_id = ctx.id_map['content_elements'].get(row['content_element_id'])
        screengroup_id = ctx.id_map['screengroups'].get(row['screengroup_id'])
        if content_element_id is None or screengroup_id is None:
            continue
        if (content_element_id, screengroup_id) in existing_ces:
            continue
        db.session.execute(sm['content_element_screengroup'].insert().values(
            content_element_id=content_element_id, screengroup_id=screengroup_id,
        ))
        existing_ces.add((content_element_id, screengroup_id))

    db.session.flush()


def import_database(app, db, data: dict, selection=None, mode: str = 'reset', conflict_resolution='skip') -> dict:
    """Import an exported JSON dict, either replacing the whole database
    (``mode='reset'``) or adding into the existing one (``mode='merge'``).

    ``selection``: ``{entity_type_key: [uuid, ...]}`` or ``None`` for
    everything in the file. Expanded to its dependency closure (see
    ``_resolve_import_selection``) before importing.

    ``conflict_resolution`` only matters in merge mode, for rows whose
    ``uuid`` already exists locally: ``'skip'``/``'overwrite'`` (applies to
    every conflict) or ``{'default': ..., 'overrides': {uuid: ...}}`` for a
    global default with per-item exceptions.

    Accepts legacy exports (``export_version`` 3-8) on a best-effort basis —
    see ``_normalize_legacy_payload``'s docstring. These have no selection
    tree (nothing to select yet), so ``selection`` is ignored for them and
    everything in the file is imported.
    """
    version = data.get('export_version', 1)
    logger.info('Starting import, export_version=%s, mode=%s', version, mode)

    prepare_import_payload(data)
    if version < 9:
        selection = None  # legacy files have no meaningful selection tree

    with app.app_context():
        try:
            try:
                db.session.execute(db.text('PRAGMA foreign_keys = OFF'))
            except Exception:
                db.session.rollback()

            if mode == 'reset':
                _clear_all_tables(db, _clear_all_models())

            selected, _ = _resolve_import_selection(data, selection)
            ctx = _ImportContext(db, data, selected, mode, conflict_resolution)

            # FK-safe dependency order (mirrors registry.ENTITY_TYPES):
            _import_screens(ctx)
            _import_screengroups(ctx)
            _import_gradients(ctx)
            _import_contentcontainers(ctx)
            _import_designs(ctx)
            _import_layouts(ctx)
            _import_contenttypes(ctx)
            _import_content_elements(ctx)
            _import_media(ctx)
            _import_devices(ctx)
            _import_magic_tag_value_lists(ctx)
            _import_magic_tags(ctx)
            _import_soft_associations(ctx)

            if mode == 'reset':
                _reset_postgres_sequences(db)

            db.session.commit()
            db.session.expire_all()

            try:
                db.session.execute(db.text('PRAGMA foreign_keys = ON'))
            except Exception:
                pass

            logger.info('Import committed successfully')

            counts = {key: len(ctx.id_map[key]) for key in ctx.id_map}
            return {'success': True, 'counts': counts}
        except Exception as e:
            db.session.rollback()
            try:
                db.session.execute(db.text('PRAGMA foreign_keys = ON'))
            except Exception:
                pass
            logger.exception('Import failed')
            return {'success': False, 'error': str(e)}


def _clear_all_models():
    from application.models import (
        Screen, Screengroup, ContentElement, Design, Layout, Contenttype,
        ContentContainer, TagConfig, Media, Device, MagicTag,
        MagicTagValueList, MagicTagValueListEntry,
    )
    from application.models.base import screengroup_screen, content_element_screengroup
    from application.models.content import (
        layout_container, Gradient, DesignGradient, DesignContainerStyle, DesignGlobalStyle,
    )
    return (
        content_element_screengroup, screengroup_screen, layout_container, TagConfig,
        ContentElement, Device, Screen, Screengroup, DesignContainerStyle, DesignGlobalStyle,
        ContentContainer, Contenttype, Layout, DesignGradient, Design, Gradient, Media,
        MagicTag, MagicTagValueListEntry, MagicTagValueList,
    )
