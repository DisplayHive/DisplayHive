"""The persistent screen log: storing, paging, filtering, retention (application/screen_logs.py)
and the socket handler that feeds it."""

from datetime import datetime, timedelta

import pytest

from application import screen_logs
from application.models import Screen, ScreenLog, SystemSetting, db
from application.socketio_handlers import logger as logger_handlers


@pytest.fixture()
def screens(db_session):
    a, b = Screen(name='log-a', active=True, lastseen=datetime.now()), Screen(name='log-b', active=True, lastseen=datetime.now())
    db_session.add_all([a, b])
    db_session.commit()
    return a, b


def test_normalize_entry_clips_and_defaults():
    assert screen_logs.normalize_entry({'severity': 'WARNING', 'message': 'x' * 5000, 'function': 'f'}) == {
        'severity': 'warn', 'message': 'x' * 2000, 'function': 'f'}
    assert screen_logs.normalize_entry({'severity': 'bogus', 'data': 'old key'})['severity'] == 'info'
    assert screen_logs.normalize_entry({'data': 'old key'})['message'] == 'old key'
    assert screen_logs.normalize_entry('not a dict') == {'severity': 'info', 'message': '', 'function': ''}


def test_record_and_query_newest_page_oldest_first(screens):
    a, _ = screens
    for i in range(5):
        screen_logs.record(db, a.id, {'severity': 'info', 'message': f'm{i}', 'function': ''})
    page, more = screen_logs.query(db, screen_id=a.id, limit=3)
    assert [e['message'] for e in page] == ['m2', 'm3', 'm4']
    assert more is True
    older, more = screen_logs.query(db, screen_id=a.id, limit=3, before_id=page[0]['id'])
    assert [e['message'] for e in older] == ['m0', 'm1']
    assert more is False
    assert page[0]['screen'] == 'log-a' and page[0]['timestamp'].endswith('Z')


def test_query_filters(screens):
    a, b = screens
    screen_logs.record(db, a.id, {'severity': 'error', 'message': 'disk 100% full', 'function': ''})
    screen_logs.record(db, a.id, {'severity': 'info', 'message': 'hello', 'function': ''})
    screen_logs.record(db, b.id, {'severity': 'error', 'message': 'other screen', 'function': ''})
    messages = lambda **kw: [e['message'] for e in screen_logs.query(db, **kw)[0]]
    assert messages(screen_id=a.id, severities=['error']) == ['disk 100% full']
    assert messages(search='100%') == ['disk 100% full']
    assert messages(search='%') == ['disk 100% full']
    assert sorted(messages(severities=['error'])) == ['disk 100% full', 'other screen']


def test_retention_defaults_and_validation(db_session):
    assert screen_logs.retention_limits(db) == (72, 250_000)
    assert screen_logs.validate_retention_setting('screen_log_max_rows', ' 5000 ') == '5000'
    for bad in ('abc', '0', '10'):
        with pytest.raises(ValueError):
            screen_logs.validate_retention_setting('screen_log_max_rows', bad)
    db_session.add(SystemSetting(key='screen_log_max_age_hours', value='6'))
    db_session.add(SystemSetting(key='screen_log_max_rows', value='garbage'))
    db_session.commit()
    assert screen_logs.retention_limits(db) == (6, 250_000)


def test_prune_by_age_and_by_row_cap(screens, db_session):
    a, _ = screens
    for i in range(4):
        screen_logs.record(db, a.id, {'severity': 'info', 'message': f'm{i}', 'function': ''})
    oldest = db_session.execute(db.select(ScreenLog).order_by(ScreenLog.id)).scalars().first()
    oldest.timestamp = oldest.timestamp - timedelta(hours=100)
    db_session.commit()
    assert screen_logs.prune(db) == (1, 0)

    db_session.add(SystemSetting(key='screen_log_max_rows', value='1000'))
    db_session.commit()
    # Seed more than the (minimum) cap of 1000 rows
    db_session.add_all(ScreenLog(screen_id=a.id, timestamp=screen_logs._now(), severity='info', message='x', function='')
                       for _ in range(1005))
    db_session.commit()
    by_age, by_cap = screen_logs.prune(db)
    assert by_age == 0 and by_cap == 8  # 3 left + 1005 - 1000


def test_rate_limit_drops_a_flood():
    sid = 'rate-test-sid'
    allowed = [logger_handlers._within_rate_limit(sid, now=1000.0) for _ in range(logger_handlers.RATE_LIMIT + 5)]
    assert allowed.count(True) == logger_handlers.RATE_LIMIT
    # a new window starts counting again
    assert logger_handlers._within_rate_limit(sid, now=1000.0 + logger_handlers.RATE_WINDOW_SECONDS + 1) is True
