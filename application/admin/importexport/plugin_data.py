"""The data plugins own, in export and import.

A plugin offers a section (``api.data.add(DataSection)``, application/plugins/handlers.py); the section is one
more node in the export and import trees, next to Screens, Content … — selected or not like the rest. Its rows
go into the export file under ``plugin_data``:

    "plugin_data": {"displayhive.pretalx": {"plugin": "displayhive.pretalx", "version": "1.0.0",
                                            "label": "Pretalx", "rows": [{"uuid": "…", …}]}}

On import a block is applied only if the plugin that wrote it is active here; otherwise it is left out (and
said so in the result). Nothing in a plugin's data is known to the rest of the importer.
"""

import logging

from application.plugins.registry import registry

logger = logging.getLogger(__name__)

KEY_PREFIX = 'plugin:'


def key_of(section_id: str) -> str:
    return KEY_PREFIX + section_id


def export_manifest(db) -> tuple:
    """``(entries, labels)``: ``{key: [{uuid, id, label}]}`` for the tree, and ``{key: section label}``."""
    entries, labels = {}, {}
    for section_id, (_plugin, section) in sorted(registry.sections().items()):
        try:
            items = section.items(db)
        except Exception:
            logger.exception('The data section %s could not list its items', section_id)
            continue
        entries[key_of(section_id)] = [{'uuid': i['uuid'], 'id': n, 'label': i.get('label') or i['uuid']} for n, i in enumerate(items, 1)]
        labels[key_of(section_id)] = section.label or section_id
    return entries, labels


def export_sections(db, selection) -> dict:
    """The ``plugin_data`` block of an export. ``selection`` is the export's ``{key: [uuid]}`` or ``None`` (everything)."""
    out = {}
    for section_id, (plugin_id, section) in sorted(registry.sections().items()):
        key = key_of(section_id)
        if selection is None:
            uuids = None
        elif key in selection and selection[key]:
            uuids = set(selection[key])
        else:
            continue
        try:
            rows = section.export_rows(db, uuids)
        except Exception:
            logger.exception('The data section %s could not be exported', section_id)
            continue
        info = registry.loaded().get(plugin_id, {})
        out[section_id] = {'plugin': plugin_id, 'version': info.get('version', ''), 'label': section.label or section_id, 'rows': rows}
    return out


def import_manifest(db, data: dict) -> tuple:
    """``(entries, labels)`` for the import tree: the file's plugin data that this instance can take."""
    entries, labels = {}, {}
    for section_id, block in sorted((data.get('plugin_data') or {}).items()):
        known = registry.sections().get(section_id)
        if known is None or not isinstance(block, dict):
            continue
        section = known[1]
        try:
            existing = section.existing_uuids(db)
        except Exception:
            logger.exception('The data section %s could not list its rows', section_id)
            existing = set()
        rows = [r for r in (block.get('rows') or []) if isinstance(r, dict) and r.get('uuid')]
        entries[key_of(section_id)] = [
            {'uuid': r['uuid'], 'id': n, 'label': str(r.get('label') or r.get('name') or r['uuid']), 'conflict': r['uuid'] in existing}
            for n, r in enumerate(rows, 1)
        ]
        labels[key_of(section_id)] = section.label or section_id
    return entries, labels


def import_sections(db, data: dict, selection, mode: str, conflict_resolution) -> tuple:
    """Apply the file's plugin data. Returns ``({key: rows written}, [ids of the sections left out: their plugin is not active])``."""
    counts, skipped = {}, []
    default = conflict_resolution.get('default', 'skip') if isinstance(conflict_resolution, dict) else (conflict_resolution or 'skip')
    for section_id, block in (data.get('plugin_data') or {}).items():
        known = registry.sections().get(section_id)
        if known is None:
            skipped.append(section_id)
            continue
        key = key_of(section_id)
        rows = [r for r in (block.get('rows') or []) if isinstance(r, dict)]
        if selection is not None:
            wanted = set(selection.get(key) or [])
            rows = [r for r in rows if r.get('uuid') in wanted]
            if not wanted:
                continue
        section = known[1]
        if mode == 'reset':
            section.clear(db)
        counts[key] = section.import_rows(db, rows, mode, default)
    return counts, skipped
