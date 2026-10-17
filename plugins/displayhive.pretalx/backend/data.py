"""What the Pretalx plugin puts into an export, and takes from an import: the API addresses and the display settings.

The cached answers are not exported (they are fetched again). A row is recognised across instances by its
address (``uuid`` is derived from it), so importing the same address twice does not make two.

Content refers to an address by its number (``serialized_input`` holds ``7`` for the address with id 7). An
import in *reset* mode keeps the numbers, so that content works as before. A *merge* gives new addresses new
numbers: content imported along with them still points at the old ones and has to be pointed at the new address once.
"""

import logging
import uuid as uuidlib

from application.plugins.handlers import DataSection

from .models import load_models

logger = logging.getLogger(__name__)

SECTION_ID = 'displayhive.pretalx'
SETTINGS_UUID = 'settings'
_NAMESPACE = uuidlib.UUID('0b6c1c64-6a56-5b3b-9a7e-5d7e1a4f6f10')


def url_uuid(url: str) -> str:
    return str(uuidlib.uuid5(_NAMESPACE, (url or '').strip()))


class PretalxData(DataSection):
    id = SECTION_ID
    label = 'Pretalx sources'

    def items(self, db):
        m = load_models()
        rows = db.session.execute(db.select(m.PretalxApiUrl).order_by(m.PretalxApiUrl.id)).scalars().all()
        items = [{'uuid': url_uuid(u.url), 'label': u.name} for u in rows]
        if db.session.execute(db.select(m.PretalxSettings)).first() is not None:
            items.append({'uuid': SETTINGS_UUID, 'label': 'Display texts and times'})
        return items

    def existing_uuids(self, db):
        return {i['uuid'] for i in self.items(db)}

    def export_rows(self, db, uuids=None):
        m = load_models()
        out = []
        for u in db.session.execute(db.select(m.PretalxApiUrl).order_by(m.PretalxApiUrl.id)).scalars().all():
            key = url_uuid(u.url)
            if uuids is None or key in uuids:
                out.append({'uuid': key, 'label': u.name, 'kind': 'url', 'id': u.id, 'name': u.name, 'url': u.url,
                            'polling_enabled': bool(u.polling_enabled), 'polling_interval': u.polling_interval})
        if uuids is None or SETTINGS_UUID in uuids:
            s = db.session.execute(db.select(m.PretalxSettings)).scalars().first()
            if s is not None:
                out.append({'uuid': SETTINGS_UUID, 'label': 'Display texts and times', 'kind': 'settings',
                            'time_format': s.time_format, 'end_of_day': s.end_of_day, 'no_session_text': s.no_session_text,
                            'coming_up_text': s.coming_up_text, 'invalid_data_text': s.invalid_data_text,
                            'sim_datetime': s.sim_datetime})
        return out

    def clear(self, db):
        m = load_models()
        db.session.query(m.PretalxApiCache).delete()
        db.session.query(m.PretalxApiUrl).delete()
        db.session.query(m.PretalxSettings).delete()
        db.session.flush()

    def import_rows(self, db, rows, mode, conflict_resolution):
        m = load_models()
        written = 0
        for row in rows:
            if row.get('kind') == 'settings':
                current = db.session.execute(db.select(m.PretalxSettings)).scalars().first()
                if current is not None and (mode != 'reset' and conflict_resolution != 'overwrite'):
                    continue
                if current is None:
                    current = m.PretalxSettings()
                    db.session.add(current)
                for key in ('time_format', 'end_of_day', 'no_session_text', 'coming_up_text', 'invalid_data_text', 'sim_datetime'):
                    if key in row:
                        setattr(current, key, row[key])
                written += 1
                continue
            url = (row.get('url') or '').strip()
            name = (row.get('name') or '').strip()
            if not url or not name:
                continue
            existing = next((u for u in db.session.execute(db.select(m.PretalxApiUrl)).scalars().all() if url_uuid(u.url) == url_uuid(url)), None)
            if existing is not None:
                if mode != 'reset' and conflict_resolution != 'overwrite':
                    continue
                existing.name = name
                existing.polling_enabled = bool(row.get('polling_enabled'))
                existing.polling_interval = max(30, int(row.get('polling_interval') or 300))
                written += 1
                continue
            new = m.PretalxApiUrl(name=name, url=url, polling_enabled=bool(row.get('polling_enabled')),
                                  polling_interval=max(30, int(row.get('polling_interval') or 300)))
            if mode == 'reset' and isinstance(row.get('id'), int):
                new.id = row['id']
            db.session.add(new)
            written += 1
        db.session.flush()
        self._reset_sequence(db)
        return written

    @staticmethod
    def _reset_sequence(db):
        if db.session.get_bind().dialect.name != 'postgresql':
            return
        db.session.execute(db.text(
            "SELECT setval(pg_get_serial_sequence('pretalx_api_url', 'id'), COALESCE((SELECT MAX(id) FROM pretalx_api_url), 1), "
            "(SELECT MAX(id) FROM pretalx_api_url) IS NOT NULL)"))
