"""create_app(): independent apps, config overrides, and the startup switch."""

import pytest

from application.factory import create_app
from application.models import Design, Device, db


@pytest.fixture()
def fresh_app(tmp_path):
    """A factory-built app on its own empty SQLite file, without startup work."""
    uri = f"sqlite:///{tmp_path / 'factory.db'}"
    app, socketio = create_app({'SQLALCHEMY_DATABASE_URI': uri, 'SQLITE_IN_USE': True, 'TESTING': True}, startup=False)
    with app.app_context():
        db.create_all()
    return app, socketio


def test_overrides_are_applied_and_the_app_is_complete(fresh_app, flask_app):
    app, socketio = fresh_app
    assert app.config['TESTING'] is True
    assert app.config['SQLALCHEMY_DATABASE_URI'].endswith('factory.db')
    # Same HTTP surface as the default app: nothing is registered only by app.py.
    rules = lambda a: sorted((r.rule, tuple(sorted(r.methods))) for r in a.url_map.iter_rules())  # noqa: E731
    assert rules(app) == rules(flask_app.app)
    assert app.extensions['socketio'] is socketio
    assert socketio.async_mode == 'threading'


def test_two_apps_do_not_share_a_database(tmp_path):
    apps = []
    for name in ('a', 'b'):
        app, _ = create_app({'SQLALCHEMY_DATABASE_URI': f"sqlite:///{tmp_path / (name + '.db')}"}, startup=False)
        with app.app_context():
            db.create_all()
        apps.append(app)
    app_a, app_b = apps
    with app_a.app_context():
        db.session.add(Design(name='only in A', html='', css=''))
        db.session.commit()
    with app_b.app_context():
        assert db.session.execute(db.select(db.func.count()).select_from(Design)).scalar() == 0
    with app_a.app_context():
        assert db.session.execute(db.select(db.func.count()).select_from(Design)).scalar() == 1


def test_startup_false_leaves_the_data_alone(tmp_path):
    uri = f"sqlite:///{tmp_path / 'live.db'}"
    app, _ = create_app({'SQLALCHEMY_DATABASE_URI': uri}, startup=False)
    with app.app_context():
        db.create_all()
        db.session.add(Device(devicekey='dk-live', is_online=True, is_active=True))
        db.session.commit()
    # A second app built the way `flask dh …` builds it must not reset devices.
    app2, _ = create_app({'SQLALCHEMY_DATABASE_URI': uri}, startup=False)
    with app2.app_context():
        assert db.session.execute(db.select(Device).where(Device.devicekey == 'dk-live')).scalar_one().is_online is True


def test_startup_steps_reset_devices_and_enforce_a_default_design(tmp_path):
    from application.startup import run_startup_steps

    uri = f"sqlite:///{tmp_path / 'boot.db'}"
    app, _ = create_app({'SQLALCHEMY_DATABASE_URI': uri}, startup=False)
    with app.app_context():
        db.create_all()
        db.session.add(Device(devicekey='dk-boot', is_online=True, is_active=True))
        db.session.add(Design(id=1, name='first', html='', css='', isDefault=False))
        db.session.commit()
    run_startup_steps(app, db)
    with app.app_context():
        assert db.session.execute(db.select(Device).where(Device.devicekey == 'dk-boot')).scalar_one().is_online is False
        assert db.session.get(Design, 1).isDefault is True


def test_sqlite_foreign_keys_are_enforced_on_factory_apps(fresh_app):
    app, _ = fresh_app
    with app.app_context():
        assert db.session.execute(db.text('PRAGMA foreign_keys')).scalar() == 1


def test_the_socketio_server_gets_no_client_reconnection_options(fresh_app):
    """reconnection / reconnection_attempts / reconnection_delay* are options of the
    Socket.IO *client* (frontends/*/ useSocket.ts, socket-connection.ts); on the
    server they do nothing but suggest a retry policy that does not exist."""
    _app, socketio = fresh_app
    assert not [key for key in socketio.server_options if key.startswith('reconnection')]
