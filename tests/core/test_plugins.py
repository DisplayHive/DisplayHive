"""The plugin system (application/plugins/): manifests, the registry, loading and unloading at run time."""

import json
import shutil
import sys
from pathlib import Path

import pytest

from application.plugins import loader
from application.plugins.manifest import PluginError, host_accepts, parse_manifest
from application.plugins.registry import registry

BUNDLED = {
    'displayhive.textklein': 'textklein', 'displayhive.textbig': 'textbig', 'displayhive.link': 'link',
    'displayhive.wysiwyg': 'wysiwyg', 'displayhive.numbers': 'numbers', 'displayhive.checkbox': 'checkbox',
    'displayhive.table': 'table', 'displayhive.image': 'image', 'displayhive.icon': 'icon',
    'displayhive.arrows': 'arrows', 'displayhive.datetime-format': 'datetime_format',
    'displayhive.countdown': 'countdown', 'displayhive.marquee': 'marquee', 'displayhive.rawhtml': 'rawhtml',
    'displayhive.iframe': 'iframe', 'displayhive.pretalx': 'pretalx_table', 'displayhive.qrcode': 'qrcode',
}


def manifest_data(**over):
    data = {'id': 'acme.demo', 'name': 'Demo', 'kind': 'fieldhandler', 'version': '1.0.0', 'plugin_api': 1,
            'provides': {'fieldhandlers': ['demo']}, 'backend': 'backend'}
    data.update(over)
    return data


def write_plugin(root: Path, plugin_id='acme.demo', handler='demo', version='1.0.0', register_body=None, extra=None):
    folder = root / plugin_id
    (folder / 'backend').mkdir(parents=True)
    data = manifest_data(id=plugin_id, version=version, provides={'fieldhandlers': [handler]}, **(extra or {}))
    (folder / 'plugin.json').write_text(json.dumps(data))
    body = register_body if register_body is not None else (
        'from application.plugins.handlers import FieldHandler\n\n'
        f'class H(FieldHandler):\n    id = {handler!r}\n    def render(self, rc):\n        return "demo:" + str(rc.value)\n\n'
        'def register(api):\n    api.fieldhandlers.add(H())\n'
    )
    (folder / 'backend' / '__init__.py').write_text(body)
    return folder


@pytest.fixture(autouse=True)
def keep_the_registry_intact(flask_app, db_session):
    """Tests here load and unload plugins; afterwards the registry matches the database again."""
    yield
    db_session.rollback()
    loader.reconcile(flask_app.db, host_version='1.0.0', write=False)


# --- Manifest ---------------------------------------------------------------------------------


def test_a_valid_manifest_is_read():
    m = parse_manifest(manifest_data(preinstalled=True, requires_host='>=1.0.0'))
    assert (m.id, m.kind, m.version, m.plugin_api, m.fieldhandlers, m.preinstalled) == (
        'acme.demo', 'fieldhandler', '1.0.0', 1, ('demo',), True)


@pytest.mark.parametrize('over', [
    {'id': 'demo'}, {'id': 'Acme.Demo'}, {'id': ''}, {'kind': 'addon'}, {'version': '1.0'}, {'version': 'x'},
    {'plugin_api': '1'}, {'plugin_api': True}, {'provides': []}, {'provides': {'fieldhandlers': 'demo'}},
    {'provides': {'fieldhandlers': ['Bad-Id']}}, {'provides': {'fieldhandlers': ['a', 'b']}},
    {'backend': '../outside'}, {'backend': '/etc'}, {'name': ''},
])
def test_an_invalid_manifest_is_refused(over):
    with pytest.raises(PluginError):
        parse_manifest(manifest_data(**over))


def test_an_integration_may_provide_several_handlers_or_none():
    assert parse_manifest(manifest_data(kind='integration', provides={'fieldhandlers': ['a', 'b']})).fieldhandlers == ('a', 'b')
    assert parse_manifest(manifest_data(kind='integration', provides={})).fieldhandlers == ()


def test_host_version_requirements():
    assert host_accepts('', '1.0.0')
    assert host_accepts('>=1.0.0', '1.0.0')
    assert host_accepts('>=1.0.0', '1.0.0-rc1')          # a release candidate counts as its release
    assert host_accepts('>=1.0.0', '2.3.4')
    assert not host_accepts('>=1.1.0', '1.0.9')
    with pytest.raises(PluginError):
        host_accepts('~1.0', '1.0.0')


# --- Registry ---------------------------------------------------------------------------------


def test_every_bundled_plugin_is_there_and_loads():
    found = loader.discover()
    assert {pid: m.fieldhandlers[0] for pid, (m, _) in found.items() if pid in BUNDLED} == BUNDLED
    for pid, (manifest, source) in found.items():
        assert source == 'bundled'
        assert manifest.directory.name == pid
        loader.load(manifest, '1.0.0')
        assert registry.owner_of(BUNDLED[pid]) == pid


def test_two_plugins_cannot_share_a_handler_id(tmp_path):
    write_plugin(tmp_path, 'acme.one', 'shared')
    write_plugin(tmp_path, 'acme.two', 'shared')
    found = loader.discover(tmp_path)
    loader.load(found['acme.one'][0])
    with pytest.raises(PluginError):
        loader.load(found['acme.two'][0])
    assert registry.owner_of('shared') == 'acme.one'
    assert not registry.is_loaded('acme.two')


# --- Loading and unloading --------------------------------------------------------------------


def test_a_plugin_is_loaded_and_unloaded_at_run_time(tmp_path):
    write_plugin(tmp_path)
    manifest = loader.discover(tmp_path)['acme.demo'][0]
    loader.load(manifest, '1.0.0')
    handler = registry.fieldhandler('demo')
    assert handler is not None and registry.loaded()['acme.demo']['version'] == '1.0.0'
    loader.unload('acme.demo')
    assert registry.fieldhandler('demo') is None and not registry.is_loaded('acme.demo')
    assert ('acme.demo', '1.0.0') in registry.retired()
    assert not [n for n in sys.modules if n.startswith('dh_plugin_acme_demo')]
    loader.load(manifest, '1.0.0')                       # and again, from the files
    assert registry.fieldhandler('demo') is not None


def test_a_new_version_loads_next_to_the_old_one(tmp_path):
    write_plugin(tmp_path, version='1.0.0')
    loader.load(loader.discover(tmp_path)['acme.demo'][0])
    old_handler = registry.fieldhandler('demo')
    loader.unload('acme.demo')
    shutil.rmtree(tmp_path / 'acme.demo')
    write_plugin(tmp_path, version='1.1.0')
    loader.load(loader.discover(tmp_path)['acme.demo'][0])
    assert registry.fieldhandler('demo') is not old_handler
    assert registry.loaded()['acme.demo']['version'] == '1.1.0'


@pytest.mark.parametrize('body, message', [
    ('def nothing():\n    pass\n', 'register'),
    ('raise RuntimeError("boom")\n', 'failed to load'),
    ('def register(api):\n    pass\n', 'did not register'),
    ('from application.plugins.handlers import FieldHandler\n\nclass H(FieldHandler):\n    id = "other"\n\n'
     'def register(api):\n    api.fieldhandlers.add(H())\n', 'does not declare'),
])
def test_a_broken_plugin_leaves_nothing_behind(tmp_path, body, message):
    write_plugin(tmp_path, register_body=body)
    manifest = loader.discover(tmp_path)['acme.demo'][0]
    with pytest.raises(PluginError, match=message):
        loader.load(manifest)
    assert not registry.is_loaded('acme.demo') and registry.fieldhandler('demo') is None
    assert not [n for n in sys.modules if n.startswith('dh_plugin_acme_demo')]


def test_a_plugin_for_another_api_or_host_is_refused(tmp_path):
    write_plugin(tmp_path, 'acme.api', 'apitest', extra={'plugin_api': 99})
    write_plugin(tmp_path, 'acme.host', 'hosttest', extra={'requires_host': '>=9.0.0'})
    found = loader.discover(tmp_path)
    with pytest.raises(PluginError, match='plugin API'):
        loader.load(found['acme.api'][0], '1.0.0')
    with pytest.raises(PluginError, match='needs DisplayHive'):
        loader.load(found['acme.host'][0], '1.0.0')


def test_a_folder_without_a_readable_manifest_is_skipped(tmp_path):
    (tmp_path / 'broken').mkdir()
    (tmp_path / 'broken' / 'plugin.json').write_text('{not json')
    write_plugin(tmp_path)
    assert set(loader.discover(tmp_path)) >= {'acme.demo'}
    assert 'broken' not in loader.discover(tmp_path)


def test_an_installed_plugin_replaces_a_bundled_one_only_when_newer(tmp_path):
    write_plugin(tmp_path, 'displayhive.countdown', 'countdown', version='0.9.0')
    assert loader.discover(tmp_path)['displayhive.countdown'][1] == 'bundled'
    shutil.rmtree(tmp_path / 'displayhive.countdown')
    write_plugin(tmp_path, 'displayhive.countdown', 'countdown', version='2.0.0')
    manifest, source = loader.discover(tmp_path)['displayhive.countdown']
    assert (source, manifest.version) == ('installed', '2.0.0')


# --- The state in the database ---------------------------------------------------------------


def test_first_start_switches_on_the_preinstalled_ones_and_not_pretalx(flask_app, db_session):
    from application.models import Plugin
    db_session.query(Plugin).delete()
    db_session.commit()
    loader.reconcile(flask_app.db, host_version='1.0.0', write=True)
    rows = {r.id: r for r in db_session.query(Plugin).all()}
    assert {pid for pid, r in rows.items() if r.enabled} == set(BUNDLED) - {'displayhive.pretalx'}
    assert rows['displayhive.pretalx'].enabled is False
    assert registry.fieldhandler('textklein') is not None and registry.fieldhandler('pretalx_table') is None


def test_pretalx_is_switched_on_when_content_already_uses_it(flask_app, db_session):
    from application.models import Plugin, TagConfig
    db_session.query(Plugin).delete()
    db_session.add(TagConfig(field_name='schedule', field_handler='pretalx_table', contentcontainer_id=None, order=0))
    db_session.commit()
    loader.reconcile(flask_app.db, host_version='1.0.0', write=True)
    assert db_session.get(Plugin, 'displayhive.pretalx').enabled is True
    assert registry.fieldhandler('pretalx_table') is not None


def test_a_later_start_keeps_what_the_administrator_decided(flask_app, db_session):
    from application.models import Plugin
    loader.reconcile(flask_app.db, host_version='1.0.0', write=True)
    db_session.get(Plugin, 'displayhive.marquee').enabled = False
    db_session.commit()
    loader.reconcile(flask_app.db, host_version='1.0.0', write=True)
    assert registry.fieldhandler('marquee') is None
    assert db_session.get(Plugin, 'displayhive.marquee').enabled is False


def test_switching_a_plugin_off_and_on_takes_effect_at_once(flask_app, db_session):
    from application.admin.content.helper import render_content_fields
    from types import SimpleNamespace

    def render():
        tc = SimpleNamespace(field_name='f', field_handler='marquee', contentcontainer_id=1, option_flags=None,
                             default_value=None, contentcontainer=None)
        return render_content_fields([tc], json.dumps({'f': 'News'}))['1']

    loader.reconcile(flask_app.db, host_version='1.0.0', write=True)
    assert 'News' in render()
    assert loader.set_enabled(flask_app.db, 'displayhive.marquee', False, host_version='1.0.0') == []
    assert render() == ''                                    # the value is kept, the field renders empty
    loader.set_enabled(flask_app.db, 'displayhive.marquee', True, host_version='1.0.0')
    assert 'News' in render()


def test_a_field_whose_plugin_is_off_renders_empty_not_as_raw_data(flask_app, db_session):
    from application.admin.content.helper import render_content_fields
    from types import SimpleNamespace
    tc = SimpleNamespace(field_name='f', field_handler='no_such_handler', contentcontainer_id=1, option_flags=None,
                         default_value=None, contentcontainer=None)
    assert render_content_fields([tc], json.dumps({'f': '<script>alert(1)</script>'}))['1'] == ''


def test_an_unknown_plugin_cannot_be_switched(flask_app, db_session):
    with pytest.raises(PluginError):
        loader.set_enabled(flask_app.db, 'acme.nothing', True, host_version='1.0.0')


def test_without_a_plugin_table_the_defaults_apply(flask_app, db_session, monkeypatch):
    monkeypatch.setattr(loader, '_states', lambda db: None)
    registry.clear()
    loader.reconcile(flask_app.db, host_version='1.0.0', write=True)
    assert registry.fieldhandler('textklein') is not None and registry.fieldhandler('pretalx_table') is None


def test_a_missing_files_warning(flask_app, db_session):
    from application.models import Plugin
    db_session.add(Plugin(id='acme.gone', version='1.0.0', source='installed', enabled=True))
    db_session.commit()
    problems = loader.reconcile(flask_app.db, host_version='1.0.0', write=False)
    assert any('acme.gone' in p for p in problems)
    db_session.delete(db_session.get(Plugin, 'acme.gone'))
    db_session.commit()



# --- Taking over data from an older version ---------------------------------------------------------

def test_pretalx_is_switched_on_when_the_old_pages_data_is_there(flask_app, db_session):
    from sqlalchemy import text
    from application.models import Plugin
    db_session.query(Plugin).delete()
    # (a database migrated by the core's own migrations has this table; the test database was built from the models)
    db_session.execute(text("CREATE TABLE IF NOT EXISTS pretalx_api_url (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL, "
                            "url TEXT NOT NULL, polling_enabled BOOLEAN NOT NULL DEFAULT FALSE, polling_interval INTEGER NOT NULL DEFAULT 300, "
                            "last_success DATETIME, last_failure DATETIME, is_valid BOOLEAN)"))
    db_session.execute(text("INSERT INTO pretalx_api_url (name, url, polling_enabled, polling_interval) VALUES ('x', 'https://x', FALSE, 300)"))
    db_session.commit()
    loader.reconcile(flask_app.db, host_version='1.0.0', write=True)
    row = db_session.get(Plugin, 'displayhive.pretalx')
    assert row.enabled is True and row.schema_version >= 1
    registry.remove_plugin('displayhive.pretalx')


def test_the_old_pretalx_rights_keep_their_groups_under_the_new_names(flask_app, db_session, make_group):
    from sqlalchemy import select
    from application.models import GroupRight, Plugin, RightDefinition
    db_session.add(RightDefinition(key='pretalx.page', category='pretalx', label='old'))
    db_session.commit()
    old = db_session.execute(select(RightDefinition).where(RightDefinition.key == 'pretalx.page')).scalar_one()
    group = make_group()
    db_session.add(GroupRight(group_id=group.id, right_id=old.id))
    db_session.query(Plugin).delete()
    db_session.commit()
    loader.set_enabled(flask_app.db, 'displayhive.pretalx', True, host_version='1.0.0')
    renamed = db_session.get(RightDefinition, old.id)
    assert renamed.key == 'displayhive.pretalx.page'
    assert db_session.execute(select(GroupRight).where(GroupRight.group_id == group.id)).scalar_one().right_id == old.id
    registry.remove_plugin('displayhive.pretalx')
