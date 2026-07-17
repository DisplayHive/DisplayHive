"""Helper functions for database import/export."""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def export_database(app, db):
    """Export the entire database to a JSON-serialisable dict."""
    from application.models import (
        Screen, Screengroup, ContentElement, Template, Contenttype,
        ContentContainer, TagConfig, Media, Device, MagicTag,
        MagicTagValueList,
    )
    from application.models.base import screengroup_screen, content_element_screengroup
    from application.models.content import contenttype_container

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
                'template_id': s.template_id,
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

        # --- Templates ---
        templates = []
        for t in db.session.execute(db.select(Template)).scalars().all():
            templates.append({
                'id': t.id,
                'name': t.name,
                'description': t.description,
                'html': t.html,
                'css': t.css,
                'isDefault': bool(t.isDefault),
            })

        # --- ContentContainers ---
        containers = []
        for c in db.session.execute(db.select(ContentContainer)).scalars().all():
            containers.append({
                'id': c.id,
                'name': c.name,
                'template_id': c.template_id,
                'order': c.order,
                'title': c.title,
            })

        # --- Contenttypes ---
        contenttypes = []
        for ct in db.session.execute(db.select(Contenttype)).scalars().all():
            contenttypes.append({
                'id': ct.id,
                'name': ct.name,
                'description': ct.description,
                'html': ct.html,
                'css': ct.css,
            })

        # --- Association: contenttype_container ---
        ct_container_rows = db.session.execute(
            db.select(contenttype_container)
        ).fetchall()
        ct_container_assoc = [{'contenttype_id': r[0], 'contentcontainer_id': r[1]} for r in ct_container_rows]

        # --- TagConfigs ---
        tagconfigs = []
        for tc in db.session.execute(db.select(TagConfig)).scalars().all():
            tagconfigs.append({
                'id': tc.id,
                'contenttype_id': tc.contenttype_id,
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
                'contentcontainer': m.contentcontainer,
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
            'export_version': 3,
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'screens': screens,
            'screengroups': screengroups,
            'screengroup_screen': sg_screen_assoc,
            'templates': templates,
            'contentcontainers': containers,
            'contenttypes': contenttypes,
            'contenttype_container': ct_container_assoc,
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
    """
    from application.models import (
        Screen, Screengroup, ContentElement, Template, Contenttype,
        ContentContainer, TagConfig, Media, Device, MagicTag,
        MagicTagValueList, MagicTagValueListEntry,
    )
    from application.models.base import screengroup_screen, content_element_screengroup
    from application.models.content import contenttype_container

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
            # Association tables have no dependents, so they go first.
            # On PostgreSQL FK constraints are always enforced, so the order below
            # must not leave any referencing rows when a referenced table is deleted:
            #   screen_log has ON DELETE CASCADE at the DB level → deleted automatically with Screen
            #   Device (screen_id → screen.id) must go before Screen
            #   Screen (template_id → template.id) must go before Template
            #   ContentContainer (template_id → template.id) must go before Template
            db.session.execute(db.delete(content_element_screengroup))
            db.session.execute(db.delete(screengroup_screen))
            db.session.execute(db.delete(contenttype_container))
            db.session.execute(db.delete(TagConfig))
            db.session.execute(db.delete(ContentElement))
            db.session.execute(db.delete(Device))
            db.session.execute(db.delete(Screen))
            db.session.execute(db.delete(Screengroup))
            db.session.execute(db.delete(ContentContainer))
            db.session.execute(db.delete(Contenttype))
            db.session.execute(db.delete(Template))
            db.session.execute(db.delete(Media))
            db.session.execute(db.delete(MagicTag))
            db.session.execute(db.delete(MagicTagValueListEntry))
            db.session.execute(db.delete(MagicTagValueList))
            db.session.commit()

            # -------------------------------------------------------
            # Insert in FK-safe dependency order:
            #   Template (referenced by Screen.template_id + ContentContainer.template_id)
            #   Contenttype (referenced by ContentContainer assoc + TagConfig + ContentElement)
            #   Screen (template_id → template.id)
            #   Screengroup → screengroup_screen assoc
            #   ContentContainer → contenttype_container assoc
            #   TagConfig
            #   ContentElement → content_element_screengroup assoc
            #   Media
            #   Device (screen_id → screen.id)
            # -------------------------------------------------------

            # --- Templates (must exist before Screen + ContentContainer) ---
            for row in data.get('templates', []):
                t = Template(
                    id=row['id'],
                    name=row['name'],
                    description=row.get('description'),
                    html=row.get('html') or '',
                    css=row.get('css'),
                    isDefault=bool(row.get('isDefault', False)),
                )
                db.session.add(t)
            db.session.flush()

            # --- Contenttypes (must exist before ContentContainers assoc + TagConfig + ContentElement) ---
            for row in data.get('contenttypes', []):
                ct = Contenttype(
                    id=row['id'],
                    name=row['name'],
                    description=row.get('description'),
                    html=row.get('html') or '',
                    css=row.get('css'),
                )
                db.session.add(ct)
            db.session.flush()

            # --- Screens (template_id → template.id, must come after Template) ---
            for row in data.get('screens', []):
                s = Screen(
                    id=row['id'],
                    active=bool(row.get('active', True)),
                    lastseen=datetime.fromisoformat(row['lastseen']) if row.get('lastseen') else datetime.now(timezone.utc),
                    name=row['name'],
                    resolution_width=row.get('resolution_width') or 0,
                    resolution_height=row.get('resolution_height') or 0,
                    debug=bool(row.get('debug', False)),
                    template_id=row.get('template_id'),
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

            # --- ContentContainers (needs Template + Contenttype already present for assoc) ---
            for row in data.get('contentcontainers', []):
                c = ContentContainer(
                    id=row['id'],
                    name=row['name'],
                    template_id=row['template_id'],
                    order=row.get('order') or 0,
                    title=row.get('title'),
                )
                db.session.add(c)
            db.session.flush()

            # --- Association: contenttype_container (needs both Contenttype + ContentContainer) ---
            for row in data.get('contenttype_container', []):
                db.session.execute(
                    contenttype_container.insert().values(
                        contenttype_id=row['contenttype_id'],
                        contentcontainer_id=row['contentcontainer_id'],
                    )
                )
            db.session.flush()

            # --- TagConfigs (needs Contenttype) ---
            for row in data.get('tagconfigs', []):
                tc = TagConfig(
                    id=row['id'],
                    contenttype_id=row['contenttype_id'],
                    field_name=row['field_name'],
                    field_handler=row['field_handler'],
                    field_label=row.get('field_label'),
                    required=bool(row.get('required', False)),
                    default_value=row.get('default_value'),
                    order=row.get('order') or 0,
                )
                db.session.add(tc)
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
                    contentcontainer=row.get('contentcontainer') or 'maincontent',
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
                    ('template', 'id'),
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
                    'templates': len(data.get('templates', [])),
                    'contenttypes': len(data.get('contenttypes', [])),
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
