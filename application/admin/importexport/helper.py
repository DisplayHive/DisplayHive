"""Helper functions for database import/export."""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


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
        # --- Screens ---
        screens = []
        for s in db.session.execute(db.select(Screen)).scalars().all():
            screens.append({
                'id': s.id,
                'active': bool(s.active),
                'lastseen': s.lastseen.isoformat() if s.lastseen else None,
                'name': s.name,
                'resolution_width': s.resolution_width,
                'resolution_height': s.resolution_height,
                'debug': bool(s.debug),
            })

        # --- Screengroups ---
        screengroups = []
        for sg in db.session.execute(db.select(Screengroup)).scalars().all():
            screengroups.append({
                'id': sg.id,
                'name': sg.name,
                'is_one_screen': bool(sg.is_one_screen),
            })

        # --- Association: screengroup_screen ---
        sg_screen_rows = db.session.execute(
            db.select(screengroup_screen)
        ).fetchall()
        sg_screen_assoc = [{'screen_id': r[0], 'screengroup_id': r[1]} for r in sg_screen_rows]

        # --- Designs ---
        designs = []
        for d in db.session.execute(db.select(Design)).scalars().all():
            designs.append({
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
            })

        # --- Gradients ---
        gradients = []
        for g in db.session.execute(db.select(Gradient)).scalars().all():
            gradients.append({
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
            })

        # --- DesignGradients (ordered association) ---
        design_gradients = []
        for dg in db.session.execute(db.select(DesignGradient)).scalars().all():
            design_gradients.append({
                'id': dg.id,
                'design_id': dg.design_id,
                'gradient_id': dg.gradient_id,
                'order': dg.order,
            })

        # --- DesignContainerStyles ---
        design_container_styles = []
        for dcs in db.session.execute(db.select(DesignContainerStyle)).scalars().all():
            design_container_styles.append({
                'id': dcs.id,
                'design_id': dcs.design_id,
                'contentcontainer_id': dcs.contentcontainer_id,
                'property': dcs.property,
                'value': dcs.value,
            })

        # --- DesignGlobalStyles ---
        design_global_styles = []
        for dgs in db.session.execute(db.select(DesignGlobalStyle)).scalars().all():
            design_global_styles.append({
                'id': dgs.id,
                'design_id': dgs.design_id,
                'property': dgs.property,
                'value': dgs.value,
            })

        # --- Layouts ---
        layouts = []
        for lo in db.session.execute(db.select(Layout)).scalars().all():
            layouts.append({
                'id': lo.id,
                'name': lo.name,
                'description': lo.description,
            })

        # --- Association: layout_container ---
        layout_container_rows = db.session.execute(db.select(layout_container)).fetchall()
        layout_container_assoc = [{'layout_id': r[0], 'contentcontainer_id': r[1]} for r in layout_container_rows]

        # --- ContentContainers ---
        containers = []
        for c in db.session.execute(db.select(ContentContainer)).scalars().all():
            containers.append({
                'id': c.id,
                'name': c.name,
                'order': c.order,
                'top': c.top,
                'left': c.left,
                'width': c.width,
                'height': c.height,
                'default_field_handler': c.default_field_handler,
                'default_content': c.default_content,
            })

        # --- Contenttypes ---
        contenttypes = []
        for ct in db.session.execute(db.select(Contenttype)).scalars().all():
            contenttypes.append({
                'id': ct.id,
                'name': ct.name,
                'description': ct.description,
                'layout_id': ct.layout_id,
            })

        # --- TagConfigs ---
        tagconfigs = []
        for tc in db.session.execute(db.select(TagConfig)).scalars().all():
            tagconfigs.append({
                'id': tc.id,
                'contenttype_id': tc.contenttype_id,
                'contentcontainer_id': tc.contentcontainer_id,
                'field_name': tc.field_name,
                'field_handler': tc.field_handler,
                'field_label': tc.field_label,
                'required': bool(tc.required),
                'default_value': tc.default_value,
                'order': tc.order,
            })

        # --- ContentElement ---
        content_elements = []
        for m in db.session.execute(db.select(ContentElement)).scalars().all():
            content_elements.append({
                'id': m.id,
                'active': bool(m.active),
                'title': m.title,
                'html': m.html,
                'duration': m.duration,
                'serialized_input': m.serialized_input,
                'contenttype_id': m.contenttype_id,
            })

        # --- Association: content_element_screengroup ---
        mc_sg_rows = db.session.execute(
            db.select(content_element_screengroup)
        ).fetchall()
        mc_sg_assoc = [{'content_element_id': r[0], 'screengroup_id': r[1]} for r in mc_sg_rows]

        # --- Media (metadata only, not binary files) ---
        medias = []
        for med in db.session.execute(db.select(Media)).scalars().all():
            medias.append({
                'id': med.id,
                'filename': med.filename,
                'title': med.title,
                'tags': med.tags,
                'folder_path': med.folder_path,
                'mime_type': med.mime_type,
                'file_size': getattr(med, 'file_size', None),
                'created_at': med.created_at.isoformat() if med.created_at else None,
            })

        # --- Devices ---
        devices = []
        for d in db.session.execute(db.select(Device)).scalars().all():
            devices.append({
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
            })

        # --- Magic Tag Value Lists (must be exported before Magic Tags reference them) ---
        magic_tag_value_lists = []
        for l in db.session.execute(db.select(MagicTagValueList)).scalars().all():
            magic_tag_value_lists.append({
                'id': l.id,
                'name': l.name,
                'entries': [{'id': e.id, 'key': e.key, 'value': e.value} for e in l.entries],
            })

        # --- Magic Tags ---
        magic_tags = []
        for v in db.session.execute(db.select(MagicTag)).scalars().all():
            magic_tags.append({
                'id': v.id,
                'name': v.name,
                'value': v.value,
                'description': v.description or '',
                'type': v.type or 'text',
                'value_list_id': v.value_list_id,
            })

        return {
            'export_version': 8,
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'screens': screens,
            'screengroups': screengroups,
            'screengroup_screen': sg_screen_assoc,
            'designs': designs,
            'gradients': gradients,
            'design_gradients': design_gradients,
            'design_container_styles': design_container_styles,
            'design_global_styles': design_global_styles,
            'layouts': layouts,
            'layout_container': layout_container_assoc,
            'contentcontainers': containers,
            'contenttypes': contenttypes,
            'tagconfigs': tagconfigs,
            'content_elements': content_elements,
            'content_element_screengroup': mc_sg_assoc,
            'media': medias,
            'devices': devices,
            'magic_tag_value_lists': magic_tag_value_lists,
            'magic_tags': magic_tags,
        }


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

    with app.app_context():
        try:
            # Disable FK enforcement for SQLite only.
            # On PostgreSQL the PRAGMA statement is a syntax error; catch it and
            # rollback so the transaction is clean before continuing.
            try:
                db.session.execute(db.text('PRAGMA foreign_keys = OFF'))
            except Exception:
                db.session.rollback()

            # Clear all tables in FK-safe order (most dependent first).
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

            is_legacy = version < 4

            # --- Designs (v3: 'templates') ---
            design_rows = data.get('designs') if not is_legacy else data.get('templates', [])
            for row in (design_rows or []):
                d = Design(
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
                )
                db.session.add(d)
            db.session.flush()

            # --- Gradients (needs to exist before DesignGradient references it) ---
            for row in data.get('gradients', []):
                g = Gradient(
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
                )
                db.session.add(g)
            db.session.flush()

            # --- DesignGradients (needs Design + Gradient) ---
            for row in data.get('design_gradients', []):
                dg = DesignGradient(
                    id=row['id'],
                    design_id=row['design_id'],
                    gradient_id=row['gradient_id'],
                    order=row.get('order') or 0,
                )
                db.session.add(dg)
            db.session.flush()

            # --- ContentContainers ---
            for row in data.get('contentcontainers', []):
                c = ContentContainer(
                    id=row['id'],
                    name=row['name'],
                    order=row.get('order') or 0,
                    top=row.get('top', 0) or 0,
                    left=row.get('left', 0) or 0,
                    width=row.get('width', 100) or 100,
                    height=row.get('height', 100) or 100,
                    default_field_handler=row.get('default_field_handler'),
                    default_content=row.get('default_content'),
                )
                db.session.add(c)
            db.session.flush()

            # --- DesignContainerStyles (needs Design + ContentContainer) ---
            for row in data.get('design_container_styles', []):
                dcs = DesignContainerStyle(
                    id=row['id'],
                    design_id=row['design_id'],
                    contentcontainer_id=row['contentcontainer_id'],
                    property=row['property'],
                    value=row.get('value'),
                )
                db.session.add(dcs)
            db.session.flush()

            # --- DesignGlobalStyles (needs Design) ---
            for row in data.get('design_global_styles', []):
                dgs = DesignGlobalStyle(
                    id=row['id'],
                    design_id=row['design_id'],
                    property=row['property'],
                    value=row.get('value'),
                )
                db.session.add(dgs)
            db.session.flush()

            # --- Layouts ---
            default_layout_id = None
            if is_legacy:
                # v3 had no Layout concept: generate one Layout per legacy
                # Template, carrying its old containers (matched via the old
                # per-container template_id, no longer present on the
                # container row itself — the export doesn't preserve it
                # separately, so best-effort: put every container into one
                # Layout named after the (first / default) Design).
                default_design = next((r for r in design_rows if r.get('isDefault')), None) or (design_rows[0] if design_rows else None)
                layout = Layout(name=f"{default_design['name']} (imported)" if default_design else 'Imported Layout')
                db.session.add(layout)
                db.session.flush()
                default_layout_id = layout.id
                all_containers = db.session.execute(db.select(ContentContainer)).scalars().all()
                layout.contentcontainers = all_containers
            else:
                for row in data.get('layouts', []):
                    lo = Layout(id=row['id'], name=row['name'], description=row.get('description'))
                    db.session.add(lo)
                db.session.flush()
                for row in data.get('layout_container', []):
                    db.session.execute(
                        layout_container.insert().values(
                            layout_id=row['layout_id'],
                            contentcontainer_id=row['contentcontainer_id'],
                        )
                    )
                db.session.flush()

            # --- Contenttypes (needs Layout) ---
            contenttype_rows = data.get('contenttypes', [])
            for row in contenttype_rows:
                ct = Contenttype(
                    id=row['id'],
                    name=row['name'],
                    description=row.get('description'),
                    layout_id=row.get('layout_id') if not is_legacy else default_layout_id,
                )
                db.session.add(ct)
            db.session.flush()

            # --- TagConfigs ---
            # v5+: contenttype_id + contentcontainer_id stored directly (current shape).
            # v4: resolve via the row's content_handler_id -> that handler's contenttype/container
            # (the 'content_handlers' list is only present in the export data, never a table).
            # v3 (legacy): row already has contenttype_id (fields belonged to Contenttype
            # pre-rearchitecture too); target container defaults to the first container
            # of the synthesized default Layout.
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
                tc = TagConfig(
                    id=row['id'],
                    contenttype_id=contenttype_id,
                    contentcontainer_id=contentcontainer_id,
                    field_name=row['field_name'],
                    field_handler=row['field_handler'],
                    field_label=row.get('field_label'),
                    required=bool(row.get('required', False)),
                    default_value=row.get('default_value'),
                    order=row.get('order') or 0,
                )
                db.session.add(tc)
            db.session.flush()

            # --- Screens ---
            for row in data.get('screens', []):
                s = Screen(
                    id=row['id'],
                    active=bool(row.get('active', True)),
                    lastseen=datetime.fromisoformat(row['lastseen']) if row.get('lastseen') else datetime.now(timezone.utc),
                    name=row['name'],
                    resolution_width=row.get('resolution_width') or 0,
                    resolution_height=row.get('resolution_height') or 0,
                    debug=bool(row.get('debug', False)),
                )
                db.session.add(s)
            db.session.flush()

            # --- Screengroups ---
            for row in data.get('screengroups', []):
                sg = Screengroup(
                    id=row['id'],
                    name=row['name'],
                    is_one_screen=bool(row.get('is_one_screen', False)),
                )
                db.session.add(sg)
            db.session.flush()

            # --- Association: screengroup_screen ---
            for row in data.get('screengroup_screen', []):
                db.session.execute(
                    screengroup_screen.insert().values(
                        screen_id=row['screen_id'],
                        screengroup_id=row['screengroup_id'],
                    )
                )
            db.session.flush()

            # --- ContentElement (needs Contenttype) ---
            for row in data.get('content_elements', []):
                m = ContentElement(
                    id=row['id'],
                    active=bool(row.get('active', True)),
                    title=row.get('title') or '',
                    html=row.get('html') or '',
                    duration=row.get('duration') or 10,
                    serialized_input=row.get('serialized_input') or '',
                    contenttype_id=row.get('contenttype_id'),
                )
                db.session.add(m)
            db.session.flush()

            # --- Association: content_element_screengroup ---
            for row in data.get('content_element_screengroup', []):
                db.session.execute(
                    content_element_screengroup.insert().values(
                        content_element_id=row['content_element_id'],
                        screengroup_id=row['screengroup_id'],
                    )
                )
            db.session.flush()

            # --- Media (metadata only) ---
            for row in data.get('media', []):
                med = Media(
                    id=row['id'],
                    filename=row['filename'],
                    title=row.get('title'),
                    tags=row.get('tags'),
                    folder_path=row.get('folder_path') or '',
                    mime_type=row.get('mime_type'),
                    file_size=row.get('file_size'),
                    created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else datetime.now(timezone.utc),
                )
                db.session.add(med)
            db.session.flush()

            # --- Magic Tag Value Lists (must exist before Magic Tags reference them) ---
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

            # --- Magic Tags (value_list_id → magic_tag_value_list.id) ---
            for row in data.get('magic_tags', []):
                db.session.add(MagicTag(
                    id=row['id'], name=row['name'], value=row['value'],
                    description=row.get('description') or '',
                    type=row.get('type') or 'text',
                    value_list_id=row.get('value_list_id'),
                ))
            db.session.flush()

            # --- Devices (needs Screen via screen_id) ---
            for row in data.get('devices', []):
                d = Device(
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
                )
                db.session.add(d)
            db.session.flush()

            # On PostgreSQL, reset all sequences so auto-increment picks up
            # after the highest explicitly-inserted ID. Without this, the next
            # INSERT would try to reuse IDs already present in the table and
            # raise a UniqueViolation.
            db_uri = db.engine.url.render_as_string(hide_password=False)
            if db_uri.startswith('postgresql'):
                sequences = [
                    ('design', 'id'),
                    ('gradient', 'id'),
                    ('design_gradient', 'id'),
                    ('design_container_style', 'id'),
                    ('design_global_style', 'id'),
                    ('layout', 'id'),
                    ('contenttype', 'id'),
                    ('screen', 'id'),
                    ('screengroup', 'id'),
                    ('contentcontainer', 'id'),
                    ('tagconfig', 'id'),
                    ('content_element', 'id'),
                    ('media', 'id'),
                    ('device', 'id'),
                    ('magic_tag_value_list', 'id'),
                    ('magic_tag_value_list_entry', 'id'),
                    ('magic_tag', 'id'),
                ]
                for table, col in sequences:
                    db.session.execute(db.text(
                        f"SELECT setval(pg_get_serial_sequence('{table}', '{col}'), "
                        f"COALESCE(MAX({col}), 0)) FROM {table}"
                    ))

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
