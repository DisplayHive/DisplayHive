"""Environment parsing in application/config.py (pure functions + apply_config)."""

import pytest
from flask import Flask

from application import paths as data_paths
from application.db_url import DatabaseConfigError
from application.config import (
    DEV_CORS_ORIGINS, ConfigError, apply_config, engine_options, env_int, is_truthy,
    resolve_cors_origins, resolve_public_url, trusted_proxy_count,
)


def test_cors_defaults_to_local_dev_origins():
    assert resolve_cors_origins({}) == DEV_CORS_ORIGINS


def test_cors_adds_this_instances_port_when_it_is_not_5000():
    origins = resolve_cors_origins({'FLASK_PORT': '5099'})
    assert 'http://localhost:5099' in origins and 'http://127.0.0.1:5099' in origins
    assert resolve_cors_origins({'FLASK_PORT': '5000'}) == DEV_CORS_ORIGINS


def test_cors_wildcard_and_explicit_list():
    assert resolve_cors_origins({'CORS_ALLOWED_ORIGINS': ' * '}) == '*'
    assert resolve_cors_origins({'CORS_ALLOWED_ORIGINS': 'https://a.example, https://b.example,'}) == [
        'https://a.example', 'https://b.example',
    ]
    assert resolve_cors_origins({'CORS_ALLOWED_ORIGINS': ''}) == []   # set but empty: allow nothing


def test_public_url_is_normalised_and_optional():
    assert resolve_public_url({}) is None
    assert resolve_public_url({'PUBLIC_URL': '  '}) is None
    assert resolve_public_url({'PUBLIC_URL': 'https://signage.example.com/'}) == 'https://signage.example.com'
    assert resolve_public_url({'PUBLIC_URL': 'http://host:8080/dh'}) == 'http://host:8080/dh'


@pytest.mark.parametrize('raw', ['signage.example.com', 'ftp://x.example', 'https://', 'https://a.example/?x=1', 'https://a.example/#f'])
def test_public_url_rejects_values_the_app_cannot_use(raw):
    with pytest.raises(ConfigError, match='PUBLIC_URL'):
        resolve_public_url({'PUBLIC_URL': raw})


def test_cors_defaults_to_the_origin_of_public_url():
    assert resolve_cors_origins({'PUBLIC_URL': 'https://signage.example.com/dh'}) == ['https://signage.example.com']
    # An explicit setting still wins, including the wildcard and "allow nothing".
    assert resolve_cors_origins({'PUBLIC_URL': 'https://a.example', 'CORS_ALLOWED_ORIGINS': '*'}) == '*'
    assert resolve_cors_origins({'PUBLIC_URL': 'https://a.example', 'CORS_ALLOWED_ORIGINS': ''}) == []
    assert resolve_cors_origins({'PUBLIC_URL': 'https://a.example', 'CORS_ALLOWED_ORIGINS': 'https://b.example/x'}) == ['https://b.example']


def test_apply_config_exposes_public_url(tmp_path):
    app, cors = _apply({'PUBLIC_URL': 'https://signage.example.com/', 'SECRET_KEY': 'a-real-long-random-secret-key-123456'}, tmp_path)
    assert app.config['PUBLIC_URL'] == 'https://signage.example.com'
    assert cors == ['https://signage.example.com'] and app.config['CORS_WILDCARD'] is False
    app2, _ = _apply({'SECRET_KEY': 'a-real-long-random-secret-key-123456'}, tmp_path)
    assert app2.config['PUBLIC_URL'] is None


@pytest.mark.parametrize('raw, expected', [
    ('0', 0), ('2', 2), ('', 0), ('abc', 0), ('-3', 0), (None, 0),
])
def test_trusted_proxy_count(raw, expected):
    env = {} if raw is None else {'TRUSTED_PROXY_COUNT': raw}
    assert trusted_proxy_count(env) == expected


@pytest.mark.parametrize('raw, expected', [('1', True), ('TRUE', True), (' yes ', True), ('on', True),
                                           ('0', False), ('no', False), ('', False), (None, False)])
def test_is_truthy(raw, expected):
    assert is_truthy(raw) is expected


def test_env_int_falls_back_for_unset_invalid_and_non_positive():
    assert env_int('X', 7, {}) == 7
    assert env_int('X', 7, {'X': '12'}) == 12
    assert env_int('X', 7, {'X': 'nonsense'}) == 7
    assert env_int('X', 7, {'X': '0'}) == 7
    assert env_int('X', 7, {'X': '-4'}) == 7


def test_engine_options_defaults_and_overrides():
    assert engine_options({}) == {'pool_size': 10, 'max_overflow': 20, 'pool_timeout': 30, 'pool_pre_ping': True}
    assert engine_options({'DB_POOL_SIZE': '25', 'DB_MAX_OVERFLOW': 'x'})['pool_size'] == 25
    assert engine_options({'DB_POOL_SIZE': '25', 'DB_MAX_OVERFLOW': 'x'})['max_overflow'] == 20


def _apply(env, tmp_path, database=True):
    """apply_config on a bare Flask app. DATABASE_URL is required, so by
    default a throw-away SQLite URL is supplied (database=False omits it)."""
    if database:
        env = {'DATABASE_URL': f'sqlite:///{tmp_path}/t.db', **env}
    app = Flask('t')
    paths = data_paths.resolve({'DATA_DIR': str(tmp_path), **env}, app_root=str(tmp_path / 'root'))
    cors = apply_config(app, paths, env)
    return app, cors


def test_apply_config_database_url_is_made_explicit(tmp_path):
    app, _ = _apply({'DATABASE_URL': 'postgresql://u:p@db/x', 'SECRET_KEY': 's' * 32}, tmp_path)
    assert app.config['SQLALCHEMY_DATABASE_URI'] == 'postgresql+psycopg2://u:p@db/x'
    assert app.config['SQLITE_IN_USE'] is False


def test_apply_config_sqlite_only_when_asked_for_and_media_folders(tmp_path):
    app, _ = _apply({'SECRET_KEY': 's' * 32}, tmp_path)
    assert app.config['SQLALCHEMY_DATABASE_URI'] == f'sqlite:///{tmp_path}/t.db'
    assert app.config['SQLITE_IN_USE'] is True
    assert app.config['MEDIA_FOLDER'].startswith(str(tmp_path))
    assert app.config['MEDIA_RENDITIONS_FOLDER'].startswith(str(tmp_path))


def test_apply_config_flags_the_default_secret_key_and_wildcard_cors(tmp_path):
    with pytest.warns(RuntimeWarning, match='SECRET_KEY'):
        app, cors = _apply({'CORS_ALLOWED_ORIGINS': '*'}, tmp_path)
    assert app.config['SECRET_KEY_IS_DEFAULT'] is True
    assert app.config['CORS_WILDCARD'] is True and cors == '*'
    app2, _ = _apply({'SECRET_KEY': 'a-real-long-random-secret-key-123456'}, tmp_path)
    assert app2.config['SECRET_KEY_IS_DEFAULT'] is False
    assert app2.config['CORS_WILDCARD'] is False


def test_apply_config_screen_dev_server_flag(tmp_path):
    app, _ = _apply({'SECRET_KEY': 's' * 32, 'SCREEN_DEV_SERVER': 'yes'}, tmp_path)
    assert app.config['SCREEN_DEV_SERVER'] is True


# --- DATABASE_URL is required -------------------------------------------------


def test_apply_config_refuses_to_start_without_database_url(tmp_path):
    with pytest.raises(DatabaseConfigError, match='DATABASE_URL is not set'):
        _apply({'SECRET_KEY': 's' * 32}, tmp_path, database=False)


def test_the_missing_url_error_names_an_existing_sqlite_file_and_the_way_out(tmp_path):
    old = tmp_path / 'db'
    old.mkdir()
    (old / 'project.db').write_bytes(b'x')
    with pytest.raises(DatabaseConfigError) as error:
        _apply({'SECRET_KEY': 's' * 32, 'DATA_DIR': str(tmp_path)}, tmp_path, database=False)
    message = str(error.value)
    assert str(old / 'project.db') in message
    assert f'sqlite:///{old / "project.db"}' in message and 'copy-database' in message
    assert (old / 'project.db').read_bytes() == b'x'   # nothing moved or deleted


@pytest.mark.parametrize('kind, where', [('docker', 'Docker image'), ('nixos', 'NixOS module')])
def test_sqlite_is_refused_in_docker_and_nixos(tmp_path, kind, where):
    with pytest.raises(DatabaseConfigError, match=where):
        _apply({'SECRET_KEY': 's' * 32, 'DISPLAYHIVE_DEPLOYMENT': kind}, tmp_path)
    # PostgreSQL is fine there.
    app, _ = _apply({'SECRET_KEY': 's' * 32, 'DISPLAYHIVE_DEPLOYMENT': kind,
                     'DATABASE_URL': 'postgresql://u:p@db/x'}, tmp_path)
    assert app.config['SQLITE_IN_USE'] is False
