"""The screen page (frontends/screen/templates/index.html) as the browser parses it."""

import re


def test_the_design_css_script_is_one_complete_script(flask_app):
    """A closing script tag inside the inline script (even in a comment) ends it early and the rest
    of the script is shown as text on every screen."""
    html = flask_app.app.test_client().get('/').get_data(as_text=True)
    start = html.index('<script>')
    end = html.index('</script>', start)
    script = html[start:end]
    assert "getElementById('design-css')" in script
    assert 'console.warn' in script  # the end of the script, i.e. nothing cut it short


def test_design_css_with_script_end_tag_stays_inside_the_string(flask_app, db_session):
    from application.models import Design, db
    design = Design(name='evil', html='', css='</script><b id="x">hi</b>', isDefault=True)
    for d in db_session.execute(db.select(Design)).scalars():
        d.isDefault = False
    db_session.add(design)
    db_session.commit()
    html = flask_app.app.test_client().get('/').get_data(as_text=True)
    assert '<b id="x">' not in html
    assert re.search(r'\\u003c/script\\u003e|<\\/script>', html)


def test_service_worker_is_served_from_the_root_and_never_cached(flask_app, tmp_path, monkeypatch):
    from application.web import static_routes
    (tmp_path / 'sw.js').write_text('// worker')
    monkeypatch.setattr(static_routes, '_DIST_SCREEN', tmp_path)
    response = flask_app.app.test_client().get('/screen-sw.js?v=1.2.3')
    assert response.status_code == 200
    assert response.mimetype == 'text/javascript'
    assert response.headers['Cache-Control'] == 'no-cache'
    assert response.headers['Service-Worker-Allowed'] == '/'
    assert response.get_data(as_text=True) == '// worker'


def test_page_names_its_release_for_the_service_worker(flask_app):
    html = flask_app.app.test_client().get('/').get_data(as_text=True)
    assert re.search(r'<meta name="asset-version" content="[^"]+">', html)


def test_device_config_carries_the_reload_time_and_zone(db_session):
    from application.models import SystemSetting, db
    from application.socketio_handlers import devconfig

    class Capture:
        def emit(self, event, payload, **kwargs):
            self.payload = payload

    def config():
        capture = Capture()
        devconfig.send_upd_deviceconfig(capture, db, room='device_nobody')
        return capture.payload['deviceconfig']

    assert (config()['reloadat'], config()['timezone']) == ('', 'UTC')
    db_session.add(SystemSetting(key='screen_reload_at', value='04:30'))
    db_session.add(SystemSetting(key='timezone', value='Europe/Berlin'))
    db_session.commit()
    assert (config()['reloadat'], config()['timezone']) == ('04:30', 'Europe/Berlin')
