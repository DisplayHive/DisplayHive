"""Installing, removing and running plugins: the installer, the service, the Plugins page's socket handlers,
the plugin routes and a plugin's own events, rights and tables."""

import hashlib
import io
import json
import sys
import zipfile

import pytest
import sqlalchemy

from application.plugins import installer, loader, service
from application.plugins.manifest import PluginError
from application.plugins.registry import registry
from application.security.auth import create_token

PLUGIN_CODE = '''
from application.plugins.handlers import FieldHandler, DataSection


class H(FieldHandler):
    id = "demo"

    def render(self, rc):
        return "demo:" + str(rc.value)


class Section(DataSection):
    id = "acme.demo"
    label = "Demo"


def register(api):
    api.fieldhandlers.add(H())
    api.routes.add("hello", lambda: {"hello": "world"})
    api.events.on("ping", lambda data: {"success": True, "pong": data})
    api.data.add(Section())
    api.on_unload(lambda: UNLOADED.append(1))


UNLOADED = []
'''

MIGRATION = '''
def upgrade(connection):
    connection.exec_driver_sql("CREATE TABLE plg_acme_demo_notes (id INTEGER PRIMARY KEY, text VARCHAR(50))")
'''


def build_zip(version='1.0.0', root='', extra=None, manifest=None, files=None):
    data = {'id': 'acme.demo', 'name': 'Demo', 'kind': 'integration', 'version': version, 'plugin_api': 1,
            'provides': {'fieldhandlers': ['demo']}, 'backend': 'backend', 'admin': 'admin/index.js',
            'rights': [{'id': 'acme.demo.use', 'group': 'demo', 'label': 'Use the demo'}], 'migrations': 'migrations'}
    data.update(manifest or {})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr(f'{root}plugin.json', json.dumps(data))
        archive.writestr(f'{root}backend/__init__.py', PLUGIN_CODE)
        archive.writestr(f'{root}admin/index.js', 'export default {}')
        archive.writestr(f'{root}migrations/0001_notes.py', MIGRATION)
        for name, content in (files or {}).items():
            archive.writestr(f'{root}{name}', content)
        for info, content in (extra or []):
            archive.writestr(info, content)
    return buffer.getvalue()


@pytest.fixture()
def app(flask_app, tmp_path, db_session):
    flask_app.app.config['PLUGINS_FOLDER'] = str(tmp_path / 'plugins')
    yield flask_app.app
    db_session.rollback()
    registry.remove_plugin('acme.demo')
    loader.reconcile(flask_app.db, host_version='1.0.0', write=False)


@pytest.fixture()
def admin(flask_app, db_session, make_user, make_group, app):
    from application.models import UserGroup
    user = make_user()
    group = make_group(is_superadmin=True)
    db_session.add(UserGroup(user_id=user.id, group_id=group.id))
    db_session.commit()
    client = flask_app.socketio.test_client(flask_app.app, auth={'token': create_token(flask_app.app, user)})
    client.get_received()
    yield client
    client.disconnect()


def call(client, event, data=None):
    return client.emit(event, data, callback=True)


# --- The installer ----------------------------------------------------------------------------

def test_a_zip_is_installed_and_read_back(tmp_path):
    manifest = installer.install_zip(build_zip(), tmp_path, host_version='1.0.0')
    assert (manifest.id, manifest.version) == ('acme.demo', '1.0.0')
    assert (tmp_path / 'acme.demo' / 'backend' / '__init__.py').is_file()
    assert not [p for p in tmp_path.iterdir() if p.name.startswith('.')]          # nothing left behind


def test_a_zip_with_the_plugin_in_a_folder_is_accepted(tmp_path):
    assert installer.install_zip(build_zip(root='demo-1.0/'), tmp_path).id == 'acme.demo'


def test_an_update_replaces_the_files(tmp_path):
    installer.install_zip(build_zip('1.0.0', files={'old.txt': 'x'}), tmp_path)
    installer.install_zip(build_zip('1.1.0'), tmp_path)
    assert not (tmp_path / 'acme.demo' / 'old.txt').exists()
    assert json.loads((tmp_path / 'acme.demo' / 'plugin.json').read_text())['version'] == '1.1.0'


@pytest.mark.parametrize('problem, kwargs', [
    ('unsafe path', {'extra': [('../evil.py', 'x')]}),
    ('unsafe path', {'extra': [('/etc/evil.py', 'x')]}),
    ('plugin API', {'manifest': {'plugin_api': 7}}),
    ('needs DisplayHive', {'manifest': {'requires_host': '>=9.0.0'}}),
])
def test_a_bad_archive_is_refused_and_leaves_nothing(tmp_path, problem, kwargs):
    with pytest.raises(PluginError, match=problem):
        installer.install_zip(build_zip(**kwargs), tmp_path, host_version='1.0.0')
    assert not (tmp_path / 'acme.demo').exists()


def test_a_symbolic_link_in_the_archive_is_refused(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('plugin.json', json.dumps({'id': 'acme.demo', 'name': 'D', 'kind': 'integration', 'version': '1.0.0', 'plugin_api': 1}))
        link = zipfile.ZipInfo('link')
        link.external_attr = (0o120777 << 16)
        archive.writestr(link, '/etc/passwd')
    with pytest.raises(PluginError, match='link'):
        installer.install_zip(buffer.getvalue(), tmp_path)


def test_things_that_are_not_plugins_are_refused(tmp_path):
    with pytest.raises(PluginError, match='ZIP'):
        installer.install_zip(b'not a zip', tmp_path)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('readme.txt', 'x')
    with pytest.raises(PluginError, match='plugin.json'):
        installer.install_zip(buffer.getvalue(), tmp_path)


def test_the_checksum_is_checked_before_anything_is_unpacked(tmp_path):
    data = build_zip()
    installer.install_zip(data, tmp_path, sha256=hashlib.sha256(data).hexdigest())
    other = tmp_path / 'other'
    with pytest.raises(PluginError, match='checksum'):
        installer.install_zip(data, other, sha256='0' * 64)
    assert not other.exists()


def test_a_download_needs_a_checksum(tmp_path):
    with pytest.raises(PluginError, match='SHA-256'):
        installer.install_url('https://example.org/p.zip', tmp_path, sha256='')


def test_the_expected_id_must_match(tmp_path):
    with pytest.raises(PluginError, match='not acme.other'):
        installer.install_zip(build_zip(), tmp_path, expected_id='acme.other')


def test_only_installed_plugins_can_be_removed(tmp_path):
    installer.install_zip(build_zip(), tmp_path)
    installer.remove(tmp_path, 'acme.demo')
    assert not (tmp_path / 'acme.demo').exists()
    with pytest.raises(PluginError):
        installer.remove(tmp_path, 'displayhive.countdown')
    with pytest.raises(PluginError):
        installer.remove(tmp_path, '../escape')


def test_the_catalog_keeps_only_valid_entries(monkeypatch):
    body = json.dumps({'plugins': [
        {'id': 'a.b', 'name': 'B', 'version': '1.0.0', 'url': 'https://x/y.zip', 'sha256': 'ab', 'evil': 1},
        {'id': 'broken'},
    ]}).encode()
    monkeypatch.setattr(installer, 'download', lambda url, max_bytes=0: body)
    entries = installer.fetch_catalog('https://example.org/catalog.json')
    assert [e['id'] for e in entries] == ['a.b'] and 'evil' not in entries[0]
    assert installer.fetch_catalog('') == []


# --- Running an installed plugin --------------------------------------------------------------

def test_installing_loads_the_plugin_and_its_tables_rights_and_routes(flask_app, app, db_session):
    manifest = service.install_zip(flask_app.db, app, build_zip())
    assert registry.is_loaded('acme.demo') and registry.fieldhandler('demo') is not None
    from application.models import Plugin, RightDefinition
    row = db_session.get(Plugin, 'acme.demo')
    assert (row.source, row.enabled, row.schema_version) == ('installed', True, 1)
    assert db_session.execute(sqlalchemy.text('SELECT count(*) FROM plg_acme_demo_notes')).scalar() == 0
    assert db_session.execute(sqlalchemy.select(RightDefinition).where(RightDefinition.key == 'acme.demo.use')).scalar_one().category == 'demo'
    assert manifest.id == 'acme.demo'


def test_removing_unloads_it_runs_the_hooks_and_keeps_the_tables(flask_app, app, db_session):
    service.install_zip(flask_app.db, app, build_zip())
    module = next(m for n, m in sys.modules.items() if n.startswith('dh_plugin_acme_demo'))
    service.remove(flask_app.db, app, 'acme.demo')
    assert module.UNLOADED == [1]
    assert not registry.is_loaded('acme.demo') and registry.fieldhandler('demo') is None
    from application.models import Plugin
    assert db_session.get(Plugin, 'acme.demo') is None
    assert db_session.execute(sqlalchemy.text('SELECT count(*) FROM plg_acme_demo_notes')).scalar() == 0


def test_a_plugin_that_cannot_load_is_reported_and_not_switched_on(flask_app, app):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('plugin.json', json.dumps({'id': 'acme.demo', 'name': 'D', 'kind': 'integration', 'version': '1.0.0',
                                                    'plugin_api': 1, 'backend': 'backend'}))
        archive.writestr('backend/__init__.py', 'raise RuntimeError("boom")')
    with pytest.raises(PluginError, match='failed to load'):
        service.install_zip(flask_app.db, app, buffer.getvalue())
    assert not registry.is_loaded('acme.demo')


def test_the_core_rights_cannot_be_claimed_by_a_plugin():
    from application.plugins.manifest import parse_manifest
    with pytest.raises(PluginError, match='must start with'):
        parse_manifest({'id': 'acme.demo', 'name': 'D', 'kind': 'integration', 'version': '1.0.0', 'plugin_api': 1,
                        'rights': [{'id': 'users.delete', 'group': 'g', 'label': 'l'}]})


# --- The Plugins page's handlers --------------------------------------------------------------

def test_the_page_lists_toggles_and_installs(flask_app, app, admin):
    state = call(admin, 'displayhive:admin:cts:get_plugins')
    assert state['success'] and {p['id'] for p in state['plugins']} >= {'displayhive.countdown', 'displayhive.pretalx'}
    assert state['retired'] >= 0 and 'catalog_url' in state

    off = call(admin, 'displayhive:admin:cts:set_plugin_enabled', {'id': 'displayhive.marquee', 'enabled': False})
    assert off == {'success': True} and registry.fieldhandler('marquee') is None
    assert call(admin, 'displayhive:admin:cts:set_plugin_enabled', {'id': 'displayhive.marquee', 'enabled': True})['success']
    assert registry.fieldhandler('marquee') is not None
    assert not call(admin, 'displayhive:admin:cts:set_plugin_enabled', {'id': 'acme.nothing', 'enabled': True})['success']
    received = [r['name'] for r in admin.get_received()]
    assert 'displayhive:admin:stc:plugins' in received and 'displayhive:admin:stc:active_plugins' in received


def test_a_plugins_own_events_go_through_the_one_dispatcher(flask_app, app, admin):
    service.install_zip(flask_app.db, app, build_zip())
    ok = call(admin, 'displayhive:plugin:call', {'plugin': 'acme.demo', 'event': 'ping', 'data': 5})
    assert ok == {'success': True, 'pong': 5}
    assert not call(admin, 'displayhive:plugin:call', {'plugin': 'acme.demo', 'event': 'nothing'})['success']
    service.set_enabled(flask_app.db, app, 'acme.demo', False)
    assert call(admin, 'displayhive:plugin:call', {'plugin': 'acme.demo', 'event': 'ping'}) == {
        'success': False, 'error': 'This plugin is not active.'}


def test_an_admin_without_the_right_cannot_manage_plugins(flask_app, app, db_session, make_user):
    client = flask_app.socketio.test_client(flask_app.app, auth={'token': create_token(flask_app.app, make_user())})
    try:
        for event, data in [('displayhive:admin:cts:set_plugin_enabled', {'id': 'displayhive.marquee', 'enabled': False}),
                            ('displayhive:admin:cts:restart_server', None),
                            ('displayhive:admin:cts:install_plugin_url', {'url': 'https://x/y.zip', 'sha256': 'ab'})]:
            assert client.emit(event, data, callback=True) == {'success': False, 'error': 'Permission denied'}
    finally:
        client.disconnect()
    assert registry.fieldhandler('marquee') is not None


def test_restarting_is_refused_where_the_server_cannot_do_it(flask_app, app, admin, monkeypatch):
    monkeypatch.setattr(service, '_restart_method', lambda: '')
    answer = call(admin, 'displayhive:admin:cts:restart_server')
    assert answer['success'] is False and 'restart' in answer['error']


# --- The routes -------------------------------------------------------------------------------

def test_a_plugins_route_and_files_are_served_under_its_id(flask_app, app):
    service.install_zip(flask_app.db, app, build_zip())
    client = flask_app.app.test_client()
    assert client.get('/api/plugins/acme.demo/hello').get_json() == {'hello': 'world'}
    assert client.post('/api/plugins/acme.demo/hello').status_code == 405
    assert client.get('/api/plugins/acme.demo/missing').status_code == 404
    asset = client.get('/api/plugins/acme.demo/assets/1.0.0/admin/index.js')
    assert asset.status_code == 200 and asset.mimetype == 'text/javascript'
    assert 'immutable' in asset.headers['Cache-Control']
    assert client.get('/api/plugins/acme.demo/assets/1.0.0/backend/__init__.py').status_code == 404
    assert client.get('/api/plugins/acme.demo/assets/1.0.0/admin/../backend/__init__.py').status_code == 404
    assert client.get('/api/plugins/acme.demo/assets/9.9.9/admin/index.js').status_code == 404
    listed = client.get('/api/plugins/_active').get_json()['plugins']
    assert {'id': 'acme.demo', 'admin': 'admin/index.js'}.items() <= next(p for p in listed if p['id'] == 'acme.demo').items()
    service.set_enabled(flask_app.db, app, 'acme.demo', False)
    assert client.get('/api/plugins/acme.demo/hello').status_code == 404


def test_the_upload_route_needs_the_right(flask_app, app):
    response = flask_app.app.test_client().post('/admin/api/plugins/upload', data={'file': (io.BytesIO(build_zip()), 'p.zip')})
    assert response.status_code in (401, 403)


def test_a_missing_python_package_is_named_and_shown(flask_app, app):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('plugin.json', json.dumps({'id': 'acme.demo', 'name': 'D', 'kind': 'integration', 'version': '1.0.0', 'plugin_api': 1, 'backend': 'backend'}))
        archive.writestr('backend/__init__.py', 'import a_package_nobody_installed\n')
    with pytest.raises(PluginError, match='needs the Python package "a_package_nobody_installed"'):
        service.install_zip(flask_app.db, app, buffer.getvalue())
    listed = {p['id']: p for p in service.describe(flask_app.db, app)['plugins']}
    assert 'a_package_nobody_installed' in listed['acme.demo']['error']


def test_installing_a_plugin_that_needs_a_missing_package_is_refused_and_shown(flask_app, app, tmp_path):
    data = build_zip(manifest={'requires_python_packages': ['no-such-package-here>=2']})
    with pytest.raises(PluginError, match='nothing was installed'):
        service.install_zip(flask_app.db, app, data)
    assert not (tmp_path / 'plugins' / 'acme.demo').exists()
    listed = {p['id']: p for p in service.describe(flask_app.db, app)['plugins']}
    assert listed['displayhive.qrcode']['missing_packages'] == []


# --- Help topics ----------------------------------------------------------------------------------

HELP_PLUGIN = 'def register(api):\n    api.help.add("page.acme-demo", "Help for the demo page.", title="Demo")\n'


def _help_plugin_zip(code=HELP_PLUGIN):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('plugin.json', json.dumps({'id': 'acme.demo', 'name': 'D', 'kind': 'integration', 'version': '1.0.0', 'plugin_api': 1, 'backend': 'backend'}))
        archive.writestr('backend/__init__.py', code)
    return buffer.getvalue()


def _all_help(client):
    client.get_received()
    client.emit('displayhive:admin:cts:get_all_help', {})
    return next(r['args'][0] for r in client.get_received() if r['name'] == 'displayhive:admin:stc:all_help')


def test_a_plugins_help_topic_is_served_only_while_it_is_active(flask_app, app, admin):
    assert 'page.pretalx' not in _all_help(admin)              # Pretalx is off: its page help is not offered
    service.install_zip(flask_app.db, app, _help_plugin_zip())
    topic = _all_help(admin)['page.acme-demo']
    assert (topic['body'], topic['title'], topic['context']) == ('Help for the demo page.', 'Demo', 'acme.demo')
    service.set_enabled(flask_app.db, app, 'acme.demo', False)
    assert 'page.acme-demo' not in _all_help(admin)


def test_pretalx_brings_its_page_help_when_it_is_on(flask_app, app, admin):
    service.set_enabled(flask_app.db, app, 'displayhive.pretalx', True)
    try:
        assert 'Pretalx' in _all_help(admin)['page.pretalx']['body']
    finally:
        registry.remove_plugin('displayhive.pretalx')


def test_a_plugin_cannot_take_a_help_topic_of_the_host(flask_app, app):
    with pytest.raises(PluginError, match='one of the host'):
        service.install_zip(flask_app.db, app, _help_plugin_zip('def register(api):\n    api.help.add("page.devices", "x")\n'))


def test_a_help_topic_the_core_used_to_have_is_removed_from_the_database(flask_app, db_session):
    from application.admin.help.content import sync_help_topics
    from application.models import HelpTopic
    db_session.add(HelpTopic(key='page.pretalx', category='page', context='pretalx'))
    db_session.commit()
    sync_help_topics(flask_app.db)
    assert db_session.execute(db_session.query(HelpTopic).filter_by(key='page.pretalx').exists().select()).scalar() is False
