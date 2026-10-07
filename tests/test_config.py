"""Environment parsing in application/config.py (pure functions + apply_config)."""

import pytest
from flask import Flask

from application import paths as data_paths
from application.config import (
    DEV_CORS_ORIGINS, apply_config, engine_options, env_int, is_truthy,
    resolve_cors_origins, trusted_proxy_count,
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


def _apply(env, tmp_path):
    app = Flask('t')
    paths = data_paths.resolve({'DATA_DIR': str(tmp_path), **env}, app_root=str(tmp_path / 'root'))
    cors = apply_config(app, paths, env)
    return app, cors


def test_apply_config_database_url_is_made_explicit(tmp_path):
    app, _ = _apply({'DATABASE_URL': 'postgresql://u:p@db/x', 'SECRET_KEY': 's' * 32}, tmp_path)
    assert app.config['SQLALCHEMY_DATABASE_URI'] == 'postgresql+psycopg2://u:p@db/x'
    assert app.config['SQLITE_IN_USE'] is False


def test_apply_config_sqlite_fallback_and_media_folders(tmp_path):
    app, _ = _apply({'SECRET_KEY': 's' * 32}, tmp_path)
    assert app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite:///')
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
