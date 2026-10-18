"""One place for "now" — the convention for time stamps in DisplayHive.

* **Stored time stamps are naive UTC.** Every ``DateTime`` column without a time zone (created, last seen, last login …)
  holds the UTC wall clock. Write them with :func:`utcnow_naive`; never with ``datetime.now()`` (the server's local time).
  The exceptions are the content schedule (``ContentElement.start_time`` / ``end_time`` / weekly windows), which is wall
  clock time in the *instance's* time zone (Settings → Time) on purpose.
* **Computing with time is aware UTC.** Compare, subtract and send ISO strings with :func:`utcnow`; a value read from a
  naive column is made aware with ``value.replace(tzinfo=timezone.utc)`` first.

``tests/core/test_time_conventions.py`` fails on ``datetime.now()`` without a zone anywhere in the code.
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """The current time as an aware UTC ``datetime`` (for comparisons, durations, ISO strings)."""
    return datetime.now(timezone.utc)


def utcnow_naive() -> datetime:
    """The current UTC wall clock without a time zone: what the database's ``DateTime`` columns hold."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
