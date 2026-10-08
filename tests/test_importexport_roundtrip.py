"""Export -> import round trips through application/admin/importexport/helper.py.

The seed is the bundled example content (examplecontent/event.zip), so the
data covers every entity type with real relations, not hand-built rows.

A reset import wipes every table (and reads the engine URL), so these tests
run on a factory-built app with its own empty SQLite file instead of the
shared, transaction-wrapped default app. (They therefore cover SQLite only.)
"""

import copy
import io
import json
import zipfile
from pathlib import Path

import pytest

from application.admin.importexport.helper import export_database, import_database
from application.factory import create_app
from application.models import db

EXAMPLE_ZIP = Path(__file__).resolve().parent.parent / 'examplecontent' / 'event.zip'
ENTITY_KEYS = [
    'screens', 'screengroups', 'designs', 'gradients', 'layouts', 'contentcontainers',
    'contenttypes', 'tagconfigs', 'content_elements', 'media',
]


def _example_payload():
    with zipfile.ZipFile(io.BytesIO(EXAMPLE_ZIP.read_bytes())) as zf:
        return json.loads(zf.read('db.json').decode('utf-8'))


def _stable(export):
    """An export without its timestamp, so two exports can be compared."""
    export = copy.deepcopy(export)
    export.pop('exported_at', None)
    return export


class _Seeded:
    def __init__(self, app):
        self.app = app
        self.db = db


@pytest.fixture()
def seeded(tmp_path):
    """A fresh app whose database holds the example content."""
    app, _ = create_app(
        {'SQLALCHEMY_DATABASE_URI': f"sqlite:///{tmp_path / 'roundtrip.db'}", 'SQLITE_IN_USE': True, 'TESTING': True},
        startup=False,
    )
    with app.app_context():
        db.create_all()
    result = import_database(app, db, _example_payload(), mode='reset')
    assert result.get('success'), result
    return _Seeded(app)


def test_the_example_content_actually_has_data_to_round_trip():
    payload = _example_payload()
    assert payload['contenttypes'] and payload['content_elements'] and payload['designs']


def test_import_then_export_keeps_every_entity(seeded):
    source = _example_payload()
    exported = export_database(seeded.app, seeded.db)
    for key in ENTITY_KEYS:
        assert {r['uuid'] for r in exported[key] if 'uuid' in r} == {r['uuid'] for r in source[key] if 'uuid' in r}, key
        assert len(exported[key]) == len(source[key]), key


def test_export_import_export_is_stable(seeded):
    first = export_database(seeded.app, seeded.db)
    result = import_database(seeded.app, seeded.db, copy.deepcopy(first), mode='reset')
    assert result.get('success'), result
    second = export_database(seeded.app, seeded.db)
    assert _stable(second) == _stable(first)


def test_merge_import_of_the_same_export_adds_no_duplicates(seeded):
    first = export_database(seeded.app, seeded.db)
    result = import_database(seeded.app, seeded.db, copy.deepcopy(first), mode='merge', conflict_resolution='skip')
    assert result.get('success'), result
    after = export_database(seeded.app, seeded.db)
    for key in ENTITY_KEYS:
        assert len(after[key]) == len(first[key]), key


def _without_child_row_ids(export):
    """Overwriting an entity rewrites its child rows (style rows, tag configs,
    gradient links), which only changes their surrogate ids and order — rows
    without a uuid that nothing references. Compare those as sorted rows
    without ids; entities with a uuid are compared as they are."""
    export = _stable(export)
    for key, value in export.items():
        if isinstance(value, list) and value and isinstance(value[0], dict) and 'uuid' not in value[0] and 'id' in value[0]:
            export[key] = sorted(
                ({k: v for k, v in row.items() if k != 'id'} for row in value),
                key=lambda r: json.dumps(r, sort_keys=True),
            )
    return export


def test_overwrite_merge_of_the_same_export_changes_no_content(seeded):
    first = export_database(seeded.app, seeded.db)
    result = import_database(seeded.app, seeded.db, copy.deepcopy(first), mode='merge', conflict_resolution='overwrite')
    assert result.get('success'), result
    assert _without_child_row_ids(export_database(seeded.app, seeded.db)) == _without_child_row_ids(first)


def test_selective_export_includes_the_dependency_closure_and_imports_cleanly(seeded):
    full = export_database(seeded.app, seeded.db)
    one = full['content_elements'][0]['uuid']
    partial = export_database(seeded.app, seeded.db, {'content_elements': [one]})
    assert [r['uuid'] for r in partial['content_elements']] == [one]
    # The element's content type (and its design/layout chain) comes along.
    assert partial['contenttypes']
    result = import_database(seeded.app, seeded.db, copy.deepcopy(partial), mode='reset')
    assert result.get('success'), result
    again = export_database(seeded.app, seeded.db)
    assert [r['uuid'] for r in again['content_elements']] == [one]
