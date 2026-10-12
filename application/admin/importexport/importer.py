"""Selective database import (the export side is ``exporter.py``).

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
  ``payload._normalize_legacy_payload``) — this best-effort upgrade logic is
  unchanged from before this refactor.
"""

import logging

from .payload import prepare_import_payload
from .registry import ENTITY_TYPES, get_model
from .rows import (
    ImportContext,
    import_content_elements,
    import_contentcontainers,
    import_contenttypes,
    import_designs,
    import_devices,
    import_gradients,
    import_layouts,
    import_media,
    import_screengroups,
    import_screens,
    import_soft_associations,
    import_system_settings,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import — selection resolution and the reset / merge drivers. The legacy
# payload upgrade is in payload.py, the per-type row inserts in rows.py.
# ---------------------------------------------------------------------------

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
        if selected['layouts']:
            for v in data.get('layout_variations', []):
                if v['layout_id'] in selected['layouts']:
                    for cid in v.get('container_ids', []):
                        if cid not in selected['contentcontainers']:
                            selected['contentcontainers'].add(cid)
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
    ``ImportContext.upsert`` and the design/layout/contenttype/magic-tag
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
    ]
    for table, col in sequences:
        db.session.execute(db.text(
            f"SELECT setval(pg_get_serial_sequence('{table}', '{col}'), "
            f"COALESCE(MAX({col}), 1), MAX({col}) IS NOT NULL) FROM {table}"
        ))


def _clear_all_tables(db, models):
    """Delete all rows from every importable table, most-dependent first."""
    (content_element_screengroup, screengroup_screen, layout_container, TagConfig,
     ContentElement, Device, Screen, Screengroup, DesignContainerStyle, DesignGlobalStyle,
     ContentContainer, Contenttype, Layout, DesignGradient, Design, Gradient, Media) = models

    from application.models.content import LayoutVariation, ContainerPosition, layout_variation_container
    db.session.execute(db.delete(layout_variation_container))
    db.session.execute(db.delete(LayoutVariation))
    db.session.execute(db.delete(ContainerPosition))
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
    db.session.commit()
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
    see ``payload._normalize_legacy_payload``'s docstring. These have no selection
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
            ctx = ImportContext(db, data, selected, mode, conflict_resolution)

            # FK-safe dependency order (mirrors registry.ENTITY_TYPES):
            import_screens(ctx)
            import_screengroups(ctx)
            import_gradients(ctx)
            import_contentcontainers(ctx)
            import_designs(ctx)
            import_layouts(ctx)
            import_contenttypes(ctx)
            import_content_elements(ctx)
            import_media(ctx)
            import_devices(ctx)
            import_soft_associations(ctx)
            import_system_settings(ctx)

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
        ContentContainer, TagConfig, Media, Device,
    )
    from application.models.base import screengroup_screen, content_element_screengroup
    from application.models.content import (
        layout_container, Gradient, DesignGradient, DesignContainerStyle, DesignGlobalStyle,
    )
    return (
        content_element_screengroup, screengroup_screen, layout_container, TagConfig,
        ContentElement, Device, Screen, Screengroup, DesignContainerStyle, DesignGlobalStyle,
        ContentContainer, Contenttype, Layout, DesignGradient, Design, Gradient, Media,
    )
