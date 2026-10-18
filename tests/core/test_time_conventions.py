"""Time stamps: naive UTC in the database, aware UTC for computing, never the server's local time (application/core/timeutil.py)."""

import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from application.core.timeutil import utcnow, utcnow_naive

ROOT = Path(__file__).resolve().parents[2]


def test_the_two_clocks_agree_and_do_not_follow_the_servers_zone(monkeypatch):
    monkeypatch.setenv('TZ', 'Pacific/Kiritimati')          # UTC+14: a local-time bug would be a day off
    time.tzset()
    try:
        aware, naive = utcnow(), utcnow_naive()
    finally:
        monkeypatch.undo()
        time.tzset()
    assert aware.tzinfo is not None and aware.utcoffset().total_seconds() == 0
    assert naive.tzinfo is None
    assert abs((aware.replace(tzinfo=None) - naive).total_seconds()) < 2
    assert abs((datetime.now(timezone.utc) - aware).total_seconds()) < 2


FORBIDDEN = [
    (re.compile(r'datetime\.now\(\s*\)'), 'datetime.now() is the server\'s local time: use utcnow() / utcnow_naive()'),
    (re.compile(r'\b(?:datetime|_dt)\.utcnow\('), 'datetime.utcnow() is deprecated and naive: use utcnow() / utcnow_naive()'),
]


def _sources():
    for folder in ('application', 'plugins'):
        for path in (ROOT / folder).rglob('*.py'):
            if 'migrations' in path.parts or '__pycache__' in path.parts or path.name == 'timeutil.py':
                continue
            yield path, path.read_text(encoding='utf-8')


def test_no_code_reads_the_servers_local_time():
    problems = []
    for path, text in _sources():
        for number, line in enumerate(text.splitlines(), 1):
            code = line.split('#', 1)[0]
            for pattern, message in FORBIDDEN:
                if pattern.search(code):
                    problems.append(f'{path.relative_to(ROOT)}:{number}: {message}')
            if '.fromtimestamp(' in code and 'tz=' not in code and 'timezone' not in code:
                problems.append(f'{path.relative_to(ROOT)}:{number}: fromtimestamp() without a time zone is local time')
    assert not problems, '\n'.join(problems)
