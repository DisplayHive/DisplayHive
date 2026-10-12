"""Server startup settings in app.py: open files limit and the DB connection pool."""

import resource

import pytest


@pytest.mark.parametrize('soft, hard, expected', [
    (1024, 524288, 65536),     # typical systemd service default → capped at 65536
    (1024, 4096, 4096),        # hard limit below the cap → up to the hard limit
    (100000, 524288, None),    # already high enough → left alone
])
def test_open_files_limit_is_raised(flask_app, monkeypatch, soft, hard, expected):
    calls = []
    monkeypatch.setattr(resource, 'getrlimit', lambda which: (soft, hard))
    monkeypatch.setattr(resource, 'setrlimit', lambda which, limits: calls.append(limits))
    flask_app._raise_open_files_limit()
    assert calls == ([] if expected is None else [(expected, hard)])


def test_open_files_limit_failure_is_not_fatal(flask_app, monkeypatch):
    def refuse(which, limits):
        raise ValueError('not permitted')
    monkeypatch.setattr(resource, 'getrlimit', lambda which: (1024, 524288))
    monkeypatch.setattr(resource, 'setrlimit', refuse)
    flask_app._raise_open_files_limit()  # logs a warning, doesn't raise


def test_db_pool_defaults_and_env(flask_app, monkeypatch):
    options = flask_app.app.config['SQLALCHEMY_ENGINE_OPTIONS']
    assert (options['pool_size'], options['max_overflow']) == (10, 20)
    assert options['pool_pre_ping'] is True
    monkeypatch.setenv('DB_POOL_SIZE', '25')
    monkeypatch.setenv('DB_MAX_OVERFLOW', 'nonsense')
    assert flask_app._env_int('DB_POOL_SIZE', 10) == 25
    assert flask_app._env_int('DB_MAX_OVERFLOW', 20) == 20
