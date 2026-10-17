"""A plugin's data in export and import: the Pretalx plugin's addresses and settings, "if selected"."""

import pytest
from sqlalchemy import text

from application.admin.importexport import plugin_data
from application.admin.importexport.exporter import export_database, export_manifest
from application.admin.importexport.importer import import_database, import_manifest
from application.plugins import loader
from application.plugins.registry import registry


@pytest.fixture()
def pretalx(flask_app, db_session):
    loader.set_enabled(flask_app.db, 'displayhive.pretalx', True, host_version='1.0.0')
    db_session.execute(text("DELETE FROM pretalx_api_cache"))
    db_session.execute(text("DELETE FROM pretalx_api_url"))
    db_session.execute(text("INSERT INTO pretalx_api_url (id, name, url, polling_enabled, polling_interval) VALUES "
                            "(7, 'Main', 'https://pretalx.example/api/events/a/', TRUE, 120)"))
    db_session.commit()
    yield
    loader.unload('displayhive.pretalx')


def urls(db_session):
    return db_session.execute(text('SELECT id, name, polling_enabled, polling_interval FROM pretalx_api_url ORDER BY id')).fetchall()


def test_the_section_is_a_node_of_the_tree_next_to_the_core_types(flask_app, pretalx):
    manifest = export_manifest(flask_app.app, flask_app.db)
    key = plugin_data.key_of('displayhive.pretalx')
    assert [i['label'] for i in manifest[key]][0] == 'Main'
    assert manifest['_labels'][key] == 'Pretalx sources'


def test_everything_exports_the_section_and_a_selection_only_what_is_ticked(flask_app, pretalx):
    key = plugin_data.key_of('displayhive.pretalx')
    everything = export_database(flask_app.app, flask_app.db)['plugin_data']['displayhive.pretalx']
    assert [r['name'] for r in everything['rows'] if r['kind'] == 'url'] == ['Main']
    assert 'plugin_data' in export_database(flask_app.app, flask_app.db, {})
    assert export_database(flask_app.app, flask_app.db, {})['plugin_data'] == {}            # nothing ticked
    ticked = export_database(flask_app.app, flask_app.db, {key: [everything['rows'][0]['uuid']]})['plugin_data']
    assert len(ticked['displayhive.pretalx']['rows']) == 1


def test_a_reset_import_keeps_the_numbers_so_content_still_points_at_its_address(flask_app, db_session, pretalx):
    # (a whole-database reset wipes every table, which the shared test database cannot take; the section is what is tested)
    section = registry.sections()['displayhive.pretalx'][1]
    rows = section.export_rows(flask_app.db)
    section.clear(flask_app.db)
    assert urls(db_session) == []
    assert section.import_rows(flask_app.db, rows, 'reset', 'skip') >= 1
    assert urls(db_session) == [(7, 'Main', 1, 120)]


def test_a_merge_import_does_not_make_the_same_address_twice(flask_app, db_session, pretalx):
    data = export_database(flask_app.app, flask_app.db)
    result = import_database(flask_app.app, flask_app.db, data, mode='merge', conflict_resolution='skip')
    assert result['success'], result
    assert len(urls(db_session)) == 1
    data['plugin_data']['displayhive.pretalx']['rows'][0]['name'] = 'Renamed'
    import_database(flask_app.app, flask_app.db, data, mode='merge', conflict_resolution='overwrite')
    assert urls(db_session)[0][1] == 'Renamed'


def test_the_import_tree_marks_what_exists_and_leaves_out_a_plugin_that_is_off(flask_app, db_session, pretalx):
    data = export_database(flask_app.app, flask_app.db)
    key = plugin_data.key_of('displayhive.pretalx')
    assert import_manifest(data, flask_app.app, flask_app.db)[key][0]['conflict'] is True
    registry.remove_plugin('displayhive.pretalx')
    assert key not in import_manifest(data, flask_app.app, flask_app.db)
    result = import_database(flask_app.app, flask_app.db, data, mode='merge')
    assert result['success'] and result['skipped_plugin_data'] == ['displayhive.pretalx']
