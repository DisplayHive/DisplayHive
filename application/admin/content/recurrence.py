"""Weekly time windows of a content element.

A content element normally runs from its start time to its end time (the validity range). On top
of that it can carry *weekly windows*: it is only shown inside them, e.g. Monday to Friday from
08:00 to 18:00. Both must hold (the range AND a window); no windows means "always".

A window is ``{'days': [1, 2, 3, 4, 5], 'from': '08:00', 'to': '18:00'}`` — days are ISO weekdays
(1 = Monday … 7 = Sunday), times are wall-clock in the instance's time zone (the ``timezone``
setting). A window whose ``to`` is not after ``from`` runs past midnight into the next day.

Stored as JSON text in ``content_element.recurrence`` (NULL = no windows). The screen evaluates
the windows itself (frontends/screen/ts/screen/recurrence.ts); the admin has the same arithmetic
in frontends/admin/src/utils/content/recurrence.ts — keep the three in step.
"""

import json
import re

MAX_WINDOWS = 14
_TIME = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')


def _clean_window(raw) -> dict:
    if not isinstance(raw, dict):
        raise ValueError('A weekly window must be an object with days, from and to')
    days = raw.get('days')
    if not isinstance(days, (list, tuple)) or not days:
        raise ValueError('Pick at least one weekday for every weekly window')
    try:
        cleaned_days = sorted({int(d) for d in days})
    except (TypeError, ValueError):
        raise ValueError('Weekdays must be numbers from 1 (Monday) to 7 (Sunday)') from None
    if any(d < 1 or d > 7 for d in cleaned_days):
        raise ValueError('Weekdays must be numbers from 1 (Monday) to 7 (Sunday)')
    start, end = str(raw.get('from') or '').strip(), str(raw.get('to') or '').strip()
    if not _TIME.match(start) or not _TIME.match(end):
        raise ValueError('Times of a weekly window must look like 08:00')
    if start == end:
        raise ValueError('A weekly window must not start and end at the same time')
    return {'days': cleaned_days, 'from': start, 'to': end}


def normalize_recurrence(value) -> list:
    """The windows as a clean list; raises ``ValueError`` (with a message for the person) if invalid.

    Accepts a list, a JSON string, or nothing (``None``/``''``/``[]`` → no windows).
    """
    if value is None or value == '' or value == []:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            raise ValueError('The weekly windows are not valid JSON') from None
    if not isinstance(value, (list, tuple)):
        raise ValueError('The weekly windows must be a list')
    if len(value) > MAX_WINDOWS:
        raise ValueError(f'At most {MAX_WINDOWS} weekly windows are allowed')
    return [_clean_window(item) for item in value]


def dump_recurrence(windows: list):
    """The value for the database column: JSON text, or ``None`` for no windows."""
    return json.dumps(windows, separators=(',', ':')) if windows else None


def load_recurrence(text) -> list:
    """The windows stored in a column; unreadable or invalid data counts as no windows (never raises)."""
    try:
        return normalize_recurrence(text)
    except ValueError:
        return []
