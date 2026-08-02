"""Helper functions for database import/export."""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Export — one function per entity group, each returning a JSON-serialisable
# list of dicts. export_database() below just calls these in order and
# assembles the final payload.
# ---------------------------------------------------------------------------

def _export_screens(db, Screen):
    return [{
        'id': s.id,
        'active': bool(s.active),
        'lastseen': s.lastseen.isoformat() if s.lastseen else None,
        'name': s.name,
        'resolution_width': s.resolution_width,
        'resolution_height': s.resolution_height,
        'debug': bool(s.debug),
    } for s in db.session.execute(db.select(Screen)).scalars().all()]


def _export_screengroups(db, Screengroup):
    return [{
        'id': sg.id,
        'name': sg.name,
        'is_one_screen': bool(sg.is_one_screen),
    } for sg in db.session.execute(db.select(Screengroup)).scalars().all()]


def _export_screengroup_screen(db, screengroup_screen):
    rows = db.session.execute(db.select(screengroup_screen)).fetchall()
    return [{'screen_id': r[0], 'screengroup_id': r[1]} for r in rows]


def _export_designs(db, Design):
    return [{
        'id': d.id,
        'name': d.name,
        'description': d.description,
        'html': d.html,
        'css': d.css,
        'isDefault': bool(d.isDefault),
        'background_color': d.background_color,
        'background_image_url': d.background_image_url,
        'background_repeat': d.background_repeat,
        'background_size': d.background_size,
        'background_opacity': d.background_opacity,
        'background_effect': d.background_effect,
        'background_effect_settings': d.background_effect_settings,
    } for d in db.session.execute(db.select(Design)).scalars().all()]


def _export_gradients(db, Gradient):
    return [{
        'id': g.id,
        'name': g.name,
        'type': g.type,
        'repeating': bool(g.repeating),
        'angle': g.angle,
        'shape': g.shape,
        'size': g.size,
        'position_x': g.position_x,
        'position_y': g.position_y,
        'stops': g.stops,
    } for g in db.session.execute(db.select(Gradient)).scalars().all()]


def _export_design_gradients(db, DesignGradient):
    return [{
        'id': dg.id,
        'design_id': dg.design_id,
        'gradient_id': dg.gradient_id,
        'order': dg.order,
    } for dg in db.session.execute(db.select(DesignGradient)).scalars().all()]


def _export_design_container_styles(db, DesignContainerStyle):
    return [{
        'id': dcs.id,
        'design_id': dcs.design_id,
        'contentcontainer_id': dcs.contentcontainer_id,
        'property': dcs.property,
        'value': dcs.value,
    } for dcs in db.session.execute(db.select(DesignContainerStyle)).scalars().all()]


def _export_design_global_styles(db, DesignGlobalStyle):
    return [{
        'id': dgs.id,
        'design_id': dgs.design_id,
        'property': dgs.property,
        'value': dgs.value,
    } for dgs in db.session.execute(db.select(DesignGlobalStyle)).scalars().all()]


def _export_layouts(db, Layout):
    return [{
        'id': lo.id,
        'name': lo.name,
        'description': lo.description,
    } for lo in db.session.execute(db.select(Layout)).scalars().all()]


def _export_layout_container(db, layout_container):
    rows = db.session.execute(db.select(layout_container)).fetchall()
    return [{'layout_id': r[0], 'contentcontainer_id': r[1]} for r in rows]


def _export_containers(db, ContentContainer):
    return [{
        'id': c.id,
        'name': c.name,
        'order': c.order,
        'top': c.top,
        'left': c.left,
        'width': c.width,
        'height': c.height,
        'default_field_handler': c.default_field_handler,
        'default_content': c.default_content,
    } for c in db.session.execute(db.select(ContentContainer)).scalars().all()]


def _export_contenttypes(db, Contenttype):
    return [{
        'id': ct.id,
        'name': ct.name,
        'description': ct.description,
        'layout_id': ct.layout_id,
    } for ct in db.session.execute(db.select(Contenttype)).scalars().all()]


def _export_tagconfigs(db, TagConfig):
    return [{
        'id': tc.id,
        'contenttype_id': tc.contenttype_id,
        'contentcontainer_id': tc.contentcontainer_id,
        'field_name': tc.field_name,
        'field_handler': tc.field_handler,
        'field_label': tc.field_label,
        'required': bool(tc.required),
        'default_value': tc.default_value,
        'order': tc.order,
    } for tc in db.session.execute(db.select(TagConfig)).scalars().all()]


def _export_content_elements(db, ContentElement):
    return [{
        'id': m.id,
        'active': bool(m.active),
        'title': m.title,
        'html': m.html,
        'duration': m.duration,
        'serialized_input': m.serialized_input,
        'contenttype_id': m.contenttype_id,
    } for m in db.session.execute(db.select(ContentElement)).scalars().all()]


def _export_content_element_screengroup(db, content_element_screengroup):
    rows = db.session.execute(db.select(content_element_screengroup)).fetchall()
    return [{'content_element_id': r[0], 'screengroup_id': r[1]} for r in rows]


def _export_media(db, Media):
    """Metadata only — binary files are handled separately (e.g. zipped alongside)."""
    return [{
        'id': med.id,
        'filename': med.filename,
        'title': med.title,
        'tags': med.tags,
        'folder_path': med.folder_path,
        'mime_type': med.mime_type,
        'file_size': getattr(med, 'file_size', None),
        'created_at': med.created_at.isoformat() if med.created_at else None,
    } for med in db.session.execute(db.select(Media)).scalars().all()]


def _export_devices(db, Device):
    return [{
        'id': d.id,
        'devicekey': d.devicekey,
        'name': d.name,
        'registration_token': d.registration_token,
        'find': bool(d.find),
        'is_online': bool(d.is_online),
        'created_at': d.created_at.isoformat() if d.created_at else None,
        'last_connected_at': d.last_connected_at.isoformat() if d.last_connected_at else None,
        'is_active': bool(d.is_active),
        'screen_id': d.screen_id,
    } for d in db.session.execute(db.select(Device)).scalars().all()]


def _export_magic_tag_value_lists(db, MagicTagValueList):
    return [{
        'id': l.id,
        'name': l.name,
        'entries': [{'id': e.id, 'key': e.key, 'value': e.value} for e in l.entries],
    } for l in db.session.execute(db.select(MagicTagValueList)).scalars().all()]


def _export_magic_tags(db, MagicTag):
    return [{
        'id': v.id,
        'name': v.name,
        'value': v.value,
        'description': v.description or '',
        'type': v.type or 'text',
        'value_list_id': v.value_list_id,
    } for v in db.session.execute(db.select(MagicTag)).scalars().all()]


def export_database(app, db):
    """Export the entire database to a JSON-serialisable dict."""
    from application.models import (
        Screen, Screengroup, ContentElement, Design, Layout, Contenttype,
        ContentContainer, TagConfig, Media, Device, MagicTag,
        MagicTagValueList,
    )
    from application.models.base import screengroup_screen, content_element_screengroup
    from application.models.content import (
        layout_container, Gradient, DesignGradient, DesignContainerStyle, DesignGlobalStyle,
    )

    with app.app_context():
        return {
            'export_version': 8,
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'screens': _export_screens(db, Screen),
            'screengroups': _export_screengroups(db, Screengroup),
            'screengroup_screen': _export_screengroup_screen(db, screengroup_screen),
            'designs': _export_designs(db, Design),
            'gradients': _export_gradients(db, Gradient),
            'design_gradients': _export_design_gradients(db, DesignGradient),
            'design_container_styles': _export_design_container_styles(db, DesignContainerStyle),
            'design_global_styles': _export_design_global_styles(db, DesignGlobalStyle),
            'layouts': _export_layouts(db, Layout),
            'layout_container': _export_layout_container(db, layout_container),
            'contentcontainers': _export_containers(db, ContentContainer),
            'contenttypes': _export_contenttypes(db, Contenttype),
            'tagconfigs': _export_tagconfigs(db, TagConfig),
            'content_elements': _export_content_elements(db, ContentElement),
            'content_element_screengroup': _export_content_element_screengroup(db, content_element_screengroup),
            'media': _export_media(db, Media),
            'devices': _export_devices(db, Device),
            'magic_tag_value_lists': _export_magic_tag_value_lists(db, MagicTagValueList),
            'magic_tags': _export_magic_tags(db, MagicTag),
        }


# ---------------------------------------------------------------------------
# Import — one function per entity group (or tightly-coupled group of
# entities), called in FK-safe dependency order by import_database() below.
# Each inserts its rows and flushes so later groups can reference the
# now-assigned primary keys.
# ---------------------------------------------------------------------------

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


def _import_designs(db, data, is_legacy, Design):
    """Insert Design rows. v3 exports called these 'templates'."""
    design_rows = data.get('designs') if not is_legacy else data.get('templates', [])
    for row in (design_rows or []):
        db.session.add(Design(
            id=row['id'],
            name=row['name'],
            description=row.get('description'),
            html=row.get('html') or '',
            css=row.get('css'),
            isDefault=bool(row.get('isDefault', False)),
            background_color=row.get('background_color'),
            background_image_url=row.get('background_image_url'),
            background_repeat=row.get('background_repeat'),
            background_size=row.get('background_size'),
            background_opacity=row.get('background_opacity'),
            background_effect=row.get('background_effect'),
            background_effect_settings=row.get('background_effect_settings'),
        ))
    db.session.flush()
    return design_rows


def _import_gradients(db, data, Gradient):
    for row in data.get('gradients', []):
        db.session.add(Gradient(
            id=row['id'],
            name=row['name'],
            type=row.get('type') or 'linear',
            repeating=bool(row.get('repeating', False)),
            angle=row.get('angle', 180) or 180,
            shape=row.get('shape'),
            size=row.get('size'),
            position_x=row.get('position_x', 50.0) or 50.0,
            position_y=row.get('position_y', 50.0) or 50.0,
            stops=row.get('stops') or '[]',
        ))
    db.session.flush()


def _import_design_gradients(db, data, DesignGradient):
    """Needs Design + Gradient already inserted."""
    for row in data.get('design_gradients', []):
        db.session.add(DesignGradient(
            id=row['id'],
            design_id=row['design_id'],
            gradient_id=row['gradient_id'],
            order=row.get('order') or 0,
        ))
    db.session.flush()


def _import_containers(db, data, ContentContainer):
    for row in data.get('contentcontainers', []):
        db.session.add(ContentContainer(
            id=row['id'],
            name=row['name'],
            order=row.get('order') or 0,
            top=row.get('top', 0) or 0,
            left=row.get('left', 0) or 0,
            width=row.get('width', 100) or 100,
            height=row.get('height', 100) or 100,
            default_field_handler=row.get('default_field_handler'),
            default_content=row.get('default_content'),
        ))
    db.session.flush()


def _import_design_styles(db, data, DesignContainerStyle, DesignGlobalStyle):
    """Needs Design + ContentContainer already inserted."""
    for row in data.get('design_container_styles', []):
        db.session.add(DesignContainerStyle(
            id=row['id'],
            design_id=row['design_id'],
            contentcontainer_id=row['contentcontainer_id'],
            property=row['property'],
            value=row.get('value'),
        ))
    db.session.flush()

    for row in data.get('design_global_styles', []):
        db.session.add(DesignGlobalStyle(
            id=row['id'],
            design_id=row['design_id'],
            property=row['property'],
            value=row.get('value'),
        ))
    db.session.flush()


def _import_layouts(db, data, is_legacy, design_rows, Layout, ContentContainer):
    """Insert Layouts. v3 exports had no Layout concept, so one Layout is
    synthesized (named after the default/first Design) carrying every
    already-inserted container, best-effort — review it in the Layouts
    admin page after importing a v3 export.
    """
    if is_legacy:
        default_design = next((r for r in design_rows if r.get('isDefault')), None) or (design_rows[0] if design_rows else None)
        layout = Layout(name=f"{default_design['name']} (imported)" if default_design else 'Imported Layout')
        db.session.add(layout)
        db.session.flush()
        layout.contentcontainers = db.session.execute(db.select(ContentContainer)).scalars().all()
        return layout.id

    for row in data.get('layouts', []):
        db.session.add(Layout(id=row['id'], name=row['name'], description=row.get('description')))
    db.session.flush()
    return None


def _import_layout_container(db, data, layout_container):
    for row in data.get('layout_container', []):
        db.session.execute(
            layout_container.insert().values(
                layout_id=row['layout_id'],
                contentcontainer_id=row['contentcontainer_id'],
            )
        )
    db.session.flush()


def _import_contenttypes(db, data, is_legacy, default_layout_id, Contenttype):
    """Needs Layout already inserted."""
    contenttype_rows = data.get('contenttypes', [])
    for row in contenttype_rows:
        db.session.add(Contenttype(
            id=row['id'],
            name=row['name'],
            description=row.get('description'),
            layout_id=row.get('layout_id') if not is_legacy else default_layout_id,
        ))
    db.session.flush()
    return contenttype_rows


def _import_tagconfigs(db, data, version, is_legacy, default_layout_id, TagConfig, Layout):
    """Resolve each row's (contenttype_id, contentcontainer_id) per export version:

    - v5+ (current shape): stored directly on the row.
    - v4: the row references a now-removed ContentHandler by id; resolve via
      the export's 'content_handlers' list (never a real table).
    - v3 (legacy): row already has contenttype_id; target container defaults
      to the first container of the synthesized default Layout.
    """
    first_container_id = None
    if is_legacy and default_layout_id is not None:
        lo = db.session.get(Layout, default_layout_id)
        ordered = sorted(lo.contentcontainers or [], key=lambda c: (c.order, c.id))
        first_container_id = ordered[0].id if ordered else None

    content_handler_lookup = {
        h['id']: (h.get('contenttype_id'), h.get('contentcontainer_id'))
        for h in data.get('content_handlers', [])
    } if version == 4 else {}

    for row in data.get('tagconfigs', []):
        if is_legacy:
            contenttype_id = row.get('contenttype_id')
            contentcontainer_id = first_container_id
        elif version == 4:
            contenttype_id, contentcontainer_id = content_handler_lookup.get(row.get('content_handler_id'), (None, None))
        else:
            contenttype_id = row.get('contenttype_id')
            contentcontainer_id = row.get('contentcontainer_id')
        db.session.add(TagConfig(
            id=row['id'],
            contenttype_id=contenttype_id,
            contentcontainer_id=contentcontainer_id,
            field_name=row['field_name'],
            field_handler=row['field_handler'],
            field_label=row.get('field_label'),
            required=bool(row.get('required', False)),
            default_value=row.get('default_value'),
            order=row.get('order') or 0,
        ))
    db.session.flush()


def _import_screens(db, data, Screen):
    for row in data.get('screens', []):
        db.session.add(Screen(
            id=row['id'],
            active=bool(row.get('active', True)),
            lastseen=datetime.fromisoformat(row['lastseen']) if row.get('lastseen') else datetime.now(timezone.utc),
            name=row['name'],
            resolution_width=row.get('resolution_width') or 0,
            resolution_height=row.get('resolution_height') or 0,
            debug=bool(row.get('debug', False)),
        ))
    db.session.flush()


def _import_screengroups(db, data, Screengroup):
    for row in data.get('screengroups', []):
        db.session.add(Screengroup(
            id=row['id'],
            name=row['name'],
            is_one_screen=bool(row.get('is_one_screen', False)),
        ))
    db.session.flush()


def _import_screengroup_screen(db, data, screengroup_screen):
    for row in data.get('screengroup_screen', []):
        db.session.execute(
            screengroup_screen.insert().values(
                screen_id=row['screen_id'],
                screengroup_id=row['screengroup_id'],
            )
        )
    db.session.flush()


def _import_content_elements(db, data, ContentElement):
    """Needs Contenttype already inserted."""
    for row in data.get('content_elements', []):
        db.session.add(ContentElement(
            id=row['id'],
            active=bool(row.get('active', True)),
            title=row.get('title') or '',
            html=row.get('html') or '',
            duration=row.get('duration') or 10,
            serialized_input=row.get('serialized_input') or '',
            contenttype_id=row.get('contenttype_id'),
        ))
    db.session.flush()


def _import_content_element_screengroup(db, data, content_element_screengroup):
    for row in data.get('content_element_screengroup', []):
        db.session.execute(
            content_element_screengroup.insert().values(
                content_element_id=row['content_element_id'],
                screengroup_id=row['screengroup_id'],
            )
        )
    db.session.flush()


def _import_media(db, data, Media):
    """Metadata only — binary files are restored separately (e.g. unzipped alongside)."""
    for row in data.get('media', []):
        db.session.add(Media(
            id=row['id'],
            filename=row['filename'],
            title=row.get('title'),
            tags=row.get('tags'),
            folder_path=row.get('folder_path') or '',
            mime_type=row.get('mime_type'),
            file_size=row.get('file_size'),
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else datetime.now(timezone.utc),
        ))
    db.session.flush()


def _import_magic_tags(db, data, MagicTagValueList, MagicTagValueListEntry, MagicTag):
    """Value lists must exist before Magic Tags reference them."""
    for row in data.get('magic_tag_value_lists', []):
        value_list = MagicTagValueList(id=row['id'], name=row['name'])
        db.session.add(value_list)
        db.session.flush()
        for entry in row.get('entries', []):
            db.session.add(MagicTagValueListEntry(
                id=entry['id'], value_list_id=value_list.id,
                key=entry['key'], value=entry.get('value') or '',
            ))
    db.session.flush()

    for row in data.get('magic_tags', []):
        db.session.add(MagicTag(
            id=row['id'], name=row['name'], value=row['value'],
            description=row.get('description') or '',
            type=row.get('type') or 'text',
            value_list_id=row.get('value_list_id'),
        ))
    db.session.flush()


def _import_devices(db, data, Device):
    """Needs Screen already inserted (via screen_id)."""
    for row in data.get('devices', []):
        db.session.add(Device(
            id=row['id'],
            devicekey=row['devicekey'],
            name=row.get('name'),
            registration_token=row.get('registration_token'),
            find=bool(row.get('find', False)),
            is_online=False,  # always start offline after import
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else datetime.now(timezone.utc),
            last_connected_at=datetime.fromisoformat(row['last_connected_at']) if row.get('last_connected_at') else None,
            is_active=bool(row.get('is_active', True)),
            screen_id=row.get('screen_id'),
        ))
    db.session.flush()


def _reset_postgres_sequences(db):
    """On PostgreSQL, reset every auto-increment sequence to the highest
    explicitly-inserted id — otherwise the next INSERT reuses an id already
    present in the table and raises a UniqueViolation. No-op on SQLite,
    which doesn't use sequences.
    """
    db_uri = db.engine.url.render_as_string(hide_password=False)
    if not db_uri.startswith('postgresql'):
        return
    sequences = [
        ('design', 'id'), ('gradient', 'id'), ('design_gradient', 'id'),
        ('design_container_style', 'id'), ('design_global_style', 'id'),
        ('layout', 'id'), ('contenttype', 'id'), ('screen', 'id'),
        ('screengroup', 'id'), ('contentcontainer', 'id'), ('tagconfig', 'id'),
        ('content_element', 'id'), ('media', 'id'), ('device', 'id'),
        ('magic_tag_value_list', 'id'), ('magic_tag_value_list_entry', 'id'),
        ('magic_tag', 'id'),
    ]
    for table, col in sequences:
        db.session.execute(db.text(
            f"SELECT setval(pg_get_serial_sequence('{table}', '{col}'), "
            f"COALESCE(MAX({col}), 0)) FROM {table}"
        ))


def import_database(app, db, data: dict) -> dict:
    """Import (replace) the entire database from an exported JSON dict.

    All existing rows are deleted before inserting the imported data.
    Returns a summary dict with counts of imported records.

    Accepts export_version 3 (pre-Design/Layout rearchitecture) on a
    best-effort basis: each Template becomes a Design, one Layout is
    generated per Design carrying its old containers, each old Contenttype
    is assigned to the Layout of the first Design, and every field (TagConfig)
    targets the first container of that Layout. Re-open the Content Types /
    Layouts admin pages after importing a v3 export to review/fix these
    best-effort assignments.

    Also accepts export_version 4 and 5, which stored a separate
    ContentHandler row per (contenttype, container) — now-removed. v4's
    TagConfig rows reference a content_handler_id; the handler's
    contenttype_id/contentcontainer_id are resolved from the export's
    'content_handlers' list. v5's TagConfig rows already carry
    contenttype_id/contentcontainer_id directly (only its now-dropped
    'content_handlers' list is ignored).
    """
    from application.models import (
        Screen, Screengroup, ContentElement, Design, Layout, Contenttype,
        ContentContainer, TagConfig, Media, Device, MagicTag,
        MagicTagValueList, MagicTagValueListEntry,
    )
    from application.models.base import screengroup_screen, content_element_screengroup
    from application.models.content import (
        layout_container, Gradient, DesignGradient, DesignContainerStyle, DesignGlobalStyle,
    )

    version = data.get('export_version', 1)
    logger.info('Starting import, export_version=%s', version)
    is_legacy = version < 4

    with app.app_context():
        try:
            # Disable FK enforcement for SQLite only.
            # On PostgreSQL the PRAGMA statement is a syntax error; catch it and
            # rollback so the transaction is clean before continuing.
            try:
                db.session.execute(db.text('PRAGMA foreign_keys = OFF'))
            except Exception:
                db.session.rollback()

            _clear_all_tables(db, (
                content_element_screengroup, screengroup_screen, layout_container, TagConfig,
                ContentElement, Device, Screen, Screengroup, DesignContainerStyle, DesignGlobalStyle,
                ContentContainer, Contenttype, Layout, DesignGradient, Design, Gradient, Media,
                MagicTag, MagicTagValueListEntry, MagicTagValueList,
            ))

            # -------------------------------------------------------
            # Insert in FK-safe dependency order:
            #   Design
            #   Layout, layout_container (needs ContentContainer — inserted first)
            #   ContentContainer
            #   Contenttype (needs Layout)
            #   TagConfig (needs Contenttype + ContentContainer)
            #   Screen, Screengroup, screengroup_screen
            #   ContentElement (needs Contenttype) → content_element_screengroup
            #   Media, Device
            # -------------------------------------------------------

            design_rows = _import_designs(db, data, is_legacy, Design)
            _import_gradients(db, data, Gradient)
            _import_design_gradients(db, data, DesignGradient)
            _import_containers(db, data, ContentContainer)
            _import_design_styles(db, data, DesignContainerStyle, DesignGlobalStyle)
            default_layout_id = _import_layouts(db, data, is_legacy, design_rows, Layout, ContentContainer)
            if not is_legacy:
                _import_layout_container(db, data, layout_container)
            contenttype_rows = _import_contenttypes(db, data, is_legacy, default_layout_id, Contenttype)
            _import_tagconfigs(db, data, version, is_legacy, default_layout_id, TagConfig, Layout)
            _import_screens(db, data, Screen)
            _import_screengroups(db, data, Screengroup)
            _import_screengroup_screen(db, data, screengroup_screen)
            _import_content_elements(db, data, ContentElement)
            _import_content_element_screengroup(db, data, content_element_screengroup)
            _import_media(db, data, Media)
            _import_magic_tags(db, data, MagicTagValueList, MagicTagValueListEntry, MagicTag)
            _import_devices(db, data, Device)

            _reset_postgres_sequences(db)

            db.session.commit()
            db.session.expire_all()

            # Re-enable FK enforcement
            try:
                db.session.execute(db.text('PRAGMA foreign_keys = ON'))
            except Exception:
                pass

            logger.info('Import committed successfully')

            return {
                'success': True,
                'counts': {
                    'screens': len(data.get('screens', [])),
                    'screengroups': len(data.get('screengroups', [])),
                    'designs': len(design_rows or []),
                    'gradients': len(data.get('gradients', [])),
                    'contenttypes': len(contenttype_rows or []),
                    'content_elements': len(data.get('content_elements', [])),
                    'media': len(data.get('media', [])),
                    'devices': len(data.get('devices', [])),
                    'magic_tags': len(data.get('magic_tags', [])),
                    'magic_tag_value_lists': len(data.get('magic_tag_value_lists', [])),
                },
            }
        except Exception as e:
            db.session.rollback()
            try:
                db.session.execute(db.text('PRAGMA foreign_keys = ON'))
            except Exception:
                pass
            logger.exception('Import failed')
            return {'success': False, 'error': str(e)}
