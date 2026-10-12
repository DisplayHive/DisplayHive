"""Database export: one row serialiser per entity type, the selection walk
that pulls in every hard-FK dependency (see ``registry.py``'s ``depends_on``)
and ``export_database`` / ``export_manifest``.

The counterpart is ``importer.py``; the identity model both rely on (the
stable ``uuid`` column) is described there."""

import logging
from datetime import datetime, timezone

from .common import _exportable_setting_keys, _support_models
from .registry import ENTITY_TYPES, get_model

logger = logging.getLogger(__name__)

EXPORT_VERSION = 10  # bumped from 9: added the 'system_settings' blob.

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
        'aspect_ratio': s.aspect_ratio,
        'rotation': s.rotation,
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
        'show_when_empty': c.show_when_empty,
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
        'aspect_ratios': d.aspect_ratios,
        'indicator_enabled': bool(d.indicator_enabled), 'indicator_color': d.indicator_color,
        'indicator_height': d.indicator_height, 'indicator_direction': d.indicator_direction,
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
        if selected['layouts']:
            # Aspect-ratio variants: their member containers come along too.
            from application.models.content import LayoutVariation
            for v in db.session.execute(db.select(LayoutVariation).where(LayoutVariation.layout_id.in_(selected['layouts']))).scalars():
                for c in v.contentcontainers:
                    if c.id not in selected['contentcontainers']:
                        selected['contentcontainers'].add(c.id)
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
        from application.models.content import LayoutVariation, ContainerPosition
        layout_variation_rows = [
            {
                'layout_id': v.layout_id, 'aspect_ratio': v.aspect_ratio,
                'container_ids': [c.id for c in v.contentcontainers if c.id in selected['contentcontainers']],
            }
            for v in db.session.execute(db.select(LayoutVariation)).scalars()
            if v.layout_id in selected['layouts']
        ]
        container_position_rows = [
            {'contentcontainer_id': p.contentcontainer_id, 'aspect_ratio': p.aspect_ratio,
             'top': p.top, 'left': p.left, 'width': p.width, 'height': p.height}
            for p in db.session.execute(db.select(ContainerPosition)).scalars()
            if p.contentcontainer_id in selected['contentcontainers']
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

        from application.models import SystemSetting
        exportable_keys = _exportable_setting_keys()
        system_settings = {
            row.key: row.value
            for row in db.session.execute(db.select(SystemSetting)).scalars()
            if row.key in exportable_keys
        }

        return {
            'export_version': EXPORT_VERSION,
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'system_settings': system_settings,
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
            'layout_variations': layout_variation_rows,
            'container_positions': container_position_rows,
            'contentcontainers': [_row_container(c) for c in rows_of('contentcontainers')],
            'contenttypes': [_row_contenttype(ct) for ct in rows_of('contenttypes')],
            'tagconfigs': tagconfigs,
            'content_elements': [_row_content_element(m) for m in rows_of('content_elements')],
            'content_element_screengroup': content_element_screengroup_rows,
            'media': [_row_media(med) for med in rows_of('media')],
            'devices': [_row_device(d, selected['screens']) for d in rows_of('devices')],
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
