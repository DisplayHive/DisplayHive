"""Weekly time windows of a content element (application/admin/content/recurrence.py)."""

import copy
import json

import pytest

from application.admin.content.recurrence import (
    MAX_WINDOWS, dump_recurrence, load_recurrence, normalize_recurrence,
)
from application.admin.importexport.exporter import export_database
from application.admin.importexport.importer import import_database
from tests.admin.test_importexport_roundtrip import _example_payload, seeded  # noqa: F401  (fixture)

OFFICE = {'days': [1, 2, 3, 4, 5], 'from': '08:00', 'to': '18:00'}


def test_nothing_means_always():
    for empty in (None, '', [], '[]'):
        assert normalize_recurrence(empty) == []
    assert dump_recurrence([]) is None


def test_a_valid_window_is_cleaned_and_stored_as_json():
    windows = normalize_recurrence([{'days': [5, '1', 3, 3], 'from': ' 08:00', 'to': '18:00 '}])
    assert windows == [{'days': [1, 3, 5], 'from': '08:00', 'to': '18:00'}]
    assert json.loads(dump_recurrence(windows)) == windows
    assert normalize_recurrence(dump_recurrence(windows)) == windows


def test_a_window_may_run_past_midnight():
    assert normalize_recurrence([{'days': [5], 'from': '22:00', 'to': '02:00'}])[0]['to'] == '02:00'


@pytest.mark.parametrize('bad', [
    [{'days': [], 'from': '08:00', 'to': '18:00'}],            # no weekday
    [{'days': [0], 'from': '08:00', 'to': '18:00'}],           # weekday out of range
    [{'days': [8], 'from': '08:00', 'to': '18:00'}],
    [{'days': ['x'], 'from': '08:00', 'to': '18:00'}],
    [{'days': [1], 'from': '8:00', 'to': '18:00'}],            # not HH:MM
    [{'days': [1], 'from': '08:00', 'to': '24:00'}],
    [{'days': [1], 'from': '08:00', 'to': '08:00'}],           # empty window
    ['monday'],                                                # not an object
    'not json',
    {'days': [1]},                                             # not a list
    [OFFICE] * (MAX_WINDOWS + 1),
])
def test_invalid_windows_are_refused_with_a_message(bad):
    with pytest.raises(ValueError) as problem:
        normalize_recurrence(bad)
    assert str(problem.value)


def test_unreadable_stored_data_counts_as_always():
    assert load_recurrence('garbage') == []
    assert load_recurrence(None) == []
    assert load_recurrence(json.dumps([OFFICE])) == [OFFICE]


def test_windows_survive_an_export_and_import(seeded):  # noqa: F811
    payload = _example_payload()
    payload['content_elements'][0]['recurrence'] = [OFFICE]
    result = import_database(seeded.app, seeded.db, copy.deepcopy(payload), mode='reset')
    assert result.get('success'), result
    exported = export_database(seeded.app, seeded.db)
    by_uuid = {r['uuid']: r for r in exported['content_elements']}
    assert by_uuid[payload['content_elements'][0]['uuid']]['recurrence'] == [OFFICE]
    assert all(r['recurrence'] == [] for u, r in by_uuid.items() if u != payload['content_elements'][0]['uuid'])


def test_a_file_from_before_the_windows_imports_as_always(seeded):  # noqa: F811
    payload = _example_payload()
    for row in payload['content_elements']:
        row.pop('recurrence', None)
    result = import_database(seeded.app, seeded.db, payload, mode='reset')
    assert result.get('success'), result
    assert all(r['recurrence'] == [] for r in export_database(seeded.app, seeded.db)['content_elements'])
