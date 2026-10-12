"""JSON log lines (LOG_FORMAT=json): one JSON object per line on stderr, for log
collectors (Loki, ELK, journald fields …). The default stays the readable text
format. Standard library only, so gunicorn's logging config can load it too
(gunicorn-logging.json in the repository root)."""

import json
import logging
from datetime import datetime, timezone

# Everything a LogRecord has by itself; anything else was passed as `extra=`.
_STANDARD = set(logging.LogRecord('', 0, '', 0, '', (), None).__dict__) | {'message', 'asctime', 'taskName'}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            'time': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        if record.exc_info:
            entry['exception'] = self.formatException(record.exc_info)
        if record.stack_info:
            entry['stack'] = self.formatStack(record.stack_info)
        for key, value in record.__dict__.items():
            if key not in _STANDARD and not key.startswith('_'):
                entry[key] = value
        return json.dumps(entry, ensure_ascii=False, default=str)


def wanted(environ) -> str:
    """'json' or 'text' (the default, also for an unknown LOG_FORMAT)."""
    return 'json' if (environ.get('LOG_FORMAT') or '').strip().lower() == 'json' else 'text'
