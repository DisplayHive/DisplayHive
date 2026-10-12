"""The per-type row inserts of an import (reset and merge mode share them):
the import context, conflict handling and one ``import_<type>`` function per
entity type. ``importer.py`` drives them."""

from datetime import datetime, timezone

from .common import _exportable_setting_keys, _support_models
from .registry import ENTITY_TYPES, ENTITY_TYPES_BY_KEY, get_model


def conflict_action(conflict_resolution, row_uuid) -> str:
    """conflict_resolution: 'skip' | 'overwrite' (applies to every conflict),
    or {'default': 'skip'|'overwrite', 'overrides': {uuid: 'skip'|'overwrite'}}
    for a global default with per-item exceptions. Defaults to 'skip'."""
    if isinstance(conflict_resolution, dict):
        overrides = conflict_resolution.get('overrides') or {}
        if row_uuid in overrides:
            return overrides[row_uuid]
        return conflict_resolution.get('default') or 'skip'
    return conflict_resolution or 'skip'


class ImportContext:
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
                action = conflict_action(self.conflict_resolution, row['uuid'])
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


def import_screens(ctx):
    ctx.upsert('screens', lambda row: dict(
        active=bool(row.get('active', True)),
        lastseen=datetime.fromisoformat(row['lastseen']) if row.get('lastseen') else datetime.now(timezone.utc),
        name=row['name'],
        resolution_width=row.get('resolution_width') or 0,
        resolution_height=row.get('resolution_height') or 0,
        debug=bool(row.get('debug', False)),
        monitoring_enabled=bool(row.get('monitoring_enabled', True)),
        aspect_ratio=row.get('aspect_ratio') or '16:9',
        rotation=row.get('rotation') or 0,
    ))


def import_screengroups(ctx):
    ctx.upsert('screengroups', lambda row: dict(
        name=row['name'],
        is_one_screen=bool(row.get('is_one_screen', False)),
    ))


def import_gradients(ctx):
    ctx.upsert('gradients', lambda row: dict(
        name=row['name'], type=row.get('type') or 'linear', repeating=bool(row.get('repeating', False)),
        angle=row.get('angle', 180) or 180, shape=row.get('shape'), size=row.get('size'),
        position_x=row.get('position_x', 50.0) or 50.0, position_y=row.get('position_y', 50.0) or 50.0,
        stops=row.get('stops') or '[]',
    ))


def import_contentcontainers(ctx):
    ctx.upsert('contentcontainers', lambda row: dict(
        name=row['name'], order=row.get('order') or 0,
        top=row.get('top', 0) or 0, left=row.get('left', 0) or 0,
        width=row.get('width', 100) or 100, height=row.get('height', 100) or 100,
        default_field_handler=row.get('default_field_handler'), default_content=row.get('default_content'),
        show_when_empty=bool(row.get('show_when_empty')),
    ))


def import_designs(ctx):
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
        aspect_ratios=row.get('aspect_ratios'),
        indicator_enabled=bool(row.get('indicator_enabled')), indicator_color=row.get('indicator_color'),
        indicator_height=row.get('indicator_height'), indicator_direction=row.get('indicator_direction'),
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


def import_layouts(ctx):
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
    import_aspect_ratio_variants(ctx)


def import_aspect_ratio_variants(ctx):
    """Per-ratio container positions, then each Layout's variations."""
    from application.models import ContentContainer
    from application.models.content import LayoutVariation, ContainerPosition
    db = ctx.db

    for file_id, local_id in ctx.id_map['contentcontainers'].items():
        if ctx.action['contentcontainers'][file_id] == 'overwritten':
            db.session.execute(db.delete(ContainerPosition).where(ContainerPosition.contentcontainer_id == local_id))
    for r in ctx.data.get('container_positions', []):
        local = ctx.id_map['contentcontainers'].get(r['contentcontainer_id'])
        if local is None or ctx.action['contentcontainers'][r['contentcontainer_id']] == 'skipped':
            continue
        db.session.add(ContainerPosition(
            contentcontainer_id=local, aspect_ratio=r['aspect_ratio'],
            top=r['top'], left=r['left'], width=r['width'], height=r['height'],
        ))
    db.session.flush()

    for file_id, local_id in ctx.id_map['layouts'].items():
        action = ctx.action['layouts'][file_id]
        if action == 'skipped':
            continue
        if action == 'overwritten':
            for v in db.session.execute(db.select(LayoutVariation).where(LayoutVariation.layout_id == local_id)).scalars().all():
                db.session.delete(v)
            db.session.flush()
        for v in ctx.data.get('layout_variations', []):
            if v['layout_id'] != file_id:
                continue
            variation = LayoutVariation(layout_id=local_id, aspect_ratio=v['aspect_ratio'])
            variation.contentcontainers = [
                db.session.get(ContentContainer, ctx.id_map['contentcontainers'][cid])
                for cid in v.get('container_ids', []) if cid in ctx.id_map['contentcontainers']
            ]
            db.session.add(variation)
    db.session.flush()


def import_contenttypes(ctx):
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


def import_content_elements(ctx):
    ctx.upsert('content_elements', lambda row: dict(
        active=bool(row.get('active', True)), title=row.get('title') or '', html=row.get('html') or '',
        duration=row.get('duration') or 10, serialized_input=row.get('serialized_input') or '',
        start_time=datetime.fromisoformat(row['start_time']) if row.get('start_time') else None,
        end_time=datetime.fromisoformat(row['end_time']) if row.get('end_time') else None,
        contenttype_id=ctx.id_map['contenttypes'].get(row.get('contenttype_id')),
    ))


def import_media(ctx):
    ctx.upsert('media', lambda row: dict(
        filename=row['filename'], title=row.get('title'), tags=row.get('tags'),
        folder_path=row.get('folder_path') or '', mime_type=row.get('mime_type'), file_size=row.get('file_size'),
        created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else datetime.now(timezone.utc),
    ))


def import_devices(ctx):
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


def import_system_settings(ctx):
    """Upsert the exported 'system_settings' blob (present since export_version
    10) by key, ignoring any key outside the current export allowlist — a
    file could be hand-edited, or older/newer than this instance's allowlist,
    so the import side re-validates rather than trusting the file."""
    from application.models import SystemSetting

    settings = ctx.data.get('system_settings') or {}
    if not settings:
        return
    exportable_keys = _exportable_setting_keys()
    db = ctx.db
    existing_by_key = {row.key: row for row in db.session.execute(db.select(SystemSetting)).scalars()}
    for key, value in settings.items():
        if key not in exportable_keys:
            continue
        existing = existing_by_key.get(key)
        if existing is not None:
            existing.value = value
        else:
            db.session.add(SystemSetting(key=key, value=value))
    db.session.flush()


def import_soft_associations(ctx):
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
