"""LOG_FORMAT=json (application/logfmt.py), configure_logging, the bootstrap
account's log line, and gunicorn's JSON logging config."""

import io
import json
import logging
import logging.config
import subprocess
import sys
from pathlib import Path

import pytest

from application import logfmt
from application.config import configure_logging

ROOT = Path(__file__).resolve().parents[1]


def _format(message='hello', level=logging.INFO, args=(), exc_info=None, **extra):
    record = logging.LogRecord('application.demo', level, __file__, 1, message, args, exc_info)
    for key, value in extra.items():
        setattr(record, key, value)
    return json.loads(logfmt.JsonFormatter().format(record))


def test_a_record_becomes_one_json_object():
    entry = _format('saved %s items', args=(3,))
    assert entry['message'] == 'saved 3 items' and entry['level'] == 'INFO' and entry['logger'] == 'application.demo'
    assert entry['time'].endswith('Z') and len(entry['time']) == len('2026-10-09T08:15:02.123Z')
    assert set(entry) == {'time', 'level', 'logger', 'message'}


def test_the_output_is_a_single_line_even_with_newlines_and_unicode():
    line = logfmt.JsonFormatter().format(logging.LogRecord('x', logging.INFO, '', 1, 'two\nlines — ünï', (), None))
    assert '\n' not in line and json.loads(line)['message'] == 'two\nlines — ünï'


def test_an_exception_is_included():
    try:
        raise ValueError('boom')
    except ValueError:
        entry = _format('failed', level=logging.ERROR, exc_info=sys.exc_info())
    assert 'ValueError: boom' in entry['exception'] and entry['level'] == 'ERROR'


def test_extra_fields_are_kept_and_unserialisable_ones_stringified():
    entry = _format('x', device='lobby', thing=Path('/tmp'))
    assert entry['device'] == 'lobby' and entry['thing'] == '/tmp'


@pytest.mark.parametrize('value, expected', [('json', 'json'), (' JSON ', 'json'), ('text', 'text'), ('', 'text'), ('xml', 'text'), (None, 'text')])
def test_the_format_choice(value, expected):
    assert logfmt.wanted({} if value is None else {'LOG_FORMAT': value}) == expected


@pytest.fixture()
def clean_root_logger():
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    yield root
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


def test_configure_logging_applies_level_and_json_even_when_logging_is_already_set_up(clean_root_logger, monkeypatch):
    root = clean_root_logger
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)           # as gunicorn's logging config would have installed
    root.handlers[:] = [handler]
    monkeypatch.setenv('LOG_FORMAT', 'json')
    monkeypatch.setenv('LOG_LEVEL', 'WARNING')

    configure_logging()
    logging.getLogger('application.demo').info('not shown')
    logging.getLogger('application.demo').warning('shown')

    lines = stream.getvalue().strip().splitlines()
    assert root.level == logging.WARNING and len(lines) == 1
    assert json.loads(lines[0])['message'] == 'shown'


def test_text_stays_the_default(clean_root_logger, monkeypatch):
    stream = io.StringIO()
    clean_root_logger.handlers[:] = [logging.StreamHandler(stream)]
    monkeypatch.delenv('LOG_FORMAT', raising=False)
    configure_logging()
    assert not isinstance(clean_root_logger.handlers[0].formatter, logfmt.JsonFormatter)


def test_gunicorns_logging_config_is_valid_and_uses_our_formatter(clean_root_logger):
    config = json.loads((ROOT / 'gunicorn-logging.json').read_text())
    logging.config.dictConfig(config)
    handler = logging.getLogger('gunicorn.error').handlers[0]
    assert isinstance(handler.formatter, logfmt.JsonFormatter)


def test_the_bootstrap_account_is_logged_not_printed(monkeypatch, caplog, capsys, db_session):
    from application.auth import ensure_bootstrap_admin
    from application.models import AdminUser

    db_session.query(AdminUser).delete()
    db_session.commit()
    monkeypatch.delenv('ADMIN_BOOTSTRAP_PASSWORD', raising=False)
    with caplog.at_level(logging.WARNING, logger='application.auth'):
        ensure_bootstrap_admin(None, __import__('app').db)
    user = db_session.query(AdminUser).one()
    messages = [r.getMessage() for r in caplog.records]
    assert any('bootstrap account' in m and user.username in m for m in messages)
    assert capsys.readouterr().out == ''


def test_no_print_calls_are_left_in_the_application():
    result = subprocess.run(['grep', '-rnE', r'^\s*print\(', 'application', 'app.py'], cwd=ROOT, capture_output=True, text=True)
    assert result.stdout == ''
