"""What a QR code says: the text a phone's camera app turns into an action, for each kind of code.

Every function takes the field's values (a dict of strings, the keys named in ``FIELDS``) and returns the
text to encode, or ``''`` when something required is missing or not valid (then no code is drawn).
"""

import re
from datetime import datetime
from urllib.parse import quote

# type id -> (label, the keys of its values). `text` is the field's own value (url, text); the others are
# stored as <name>__<key>.
TYPES = {
    'url': ('Link / website', ['url']),
    'text': ('Plain text', ['text']),
    'vcard': ('Contact (vCard / MeCard)', ['vc_first', 'vc_last', 'vc_org', 'vc_title', 'vc_phone', 'vc_mobile',
                                          'vc_email', 'vc_web', 'vc_street', 'vc_zip', 'vc_city', 'vc_country', 'vc_note', 'vc_format']),
    'wifi': ('Wi-Fi', ['wifi_ssid', 'wifi_password', 'wifi_security', 'wifi_hidden']),
    'email': ('E-mail', ['mail_to', 'mail_subject', 'mail_body']),
    'sms': ('SMS', ['sms_number', 'sms_message']),
    'phone': ('Phone number', ['tel_number']),
    'geo': ('Map position', ['geo_lat', 'geo_lon']),
    'event': ('Calendar event', ['ev_title', 'ev_start', 'ev_end', 'ev_location', 'ev_description']),
    'sepa': ('SEPA payment (GiroCode)', ['pay_name', 'pay_iban', 'pay_bic', 'pay_amount', 'pay_reference']),
}

URL_TYPE = 'url'


def _clean(value) -> str:
    return str(value if value is not None else '').strip()


def _truthy(value) -> bool:
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _backslash(value: str, chars: str) -> str:
    return re.sub(f'([{re.escape(chars)}])', r'\\\1', value)


def wifi(v: dict) -> str:
    ssid = _clean(v.get('wifi_ssid'))
    if not ssid:
        return ''
    security = _clean(v.get('wifi_security')).upper() or 'WPA'
    if security not in ('WPA', 'WEP', 'NOPASS'):
        security = 'WPA'
    esc = lambda s: _backslash(s, r'\;,:"')       # noqa: E731
    parts = [f'T:{"nopass" if security == "NOPASS" else security}', f'S:{esc(ssid)}']
    password = _clean(v.get('wifi_password'))
    if security != 'NOPASS' and password:
        parts.append(f'P:{esc(password)}')
    if _truthy(v.get('wifi_hidden')):
        parts.append('H:true')
    return 'WIFI:' + ';'.join(parts) + ';;'


def vcard(v: dict) -> str:
    first, last = _clean(v.get('vc_first')), _clean(v.get('vc_last'))
    org = _clean(v.get('vc_org'))
    if not (first or last or org):
        return ''
    fields = {k: _clean(v.get(k)) for k in ('vc_title', 'vc_phone', 'vc_mobile', 'vc_email', 'vc_web', 'vc_street',
                                           'vc_zip', 'vc_city', 'vc_country', 'vc_note')}
    if _clean(v.get('vc_format')).lower() == 'mecard':
        esc = lambda s: _backslash(s, r'\;,:"')   # noqa: E731
        parts = [f'N:{esc(last)},{esc(first)}']
        if fields['vc_phone']:
            parts.append(f'TEL:{esc(fields["vc_phone"])}')
        if fields['vc_mobile']:
            parts.append(f'TEL:{esc(fields["vc_mobile"])}')
        if fields['vc_email']:
            parts.append(f'EMAIL:{esc(fields["vc_email"])}')
        if fields['vc_web']:
            parts.append(f'URL:{esc(fields["vc_web"])}')
        if any(fields[k] for k in ('vc_street', 'vc_zip', 'vc_city', 'vc_country')):
            parts.append('ADR:,,' + ','.join(esc(fields[k]) for k in ('vc_street', 'vc_city')) + ',,' + ','.join(esc(fields[k]) for k in ('vc_zip', 'vc_country')))
        if org:
            parts.append(f'ORG:{esc(org)}')
        if fields['vc_note']:
            parts.append(f'NOTE:{esc(fields["vc_note"])}')
        return 'MECARD:' + ';'.join(parts) + ';;'
    esc = lambda s: _backslash(s, r'\;,').replace('\n', '\\n')   # noqa: E731
    lines = ['BEGIN:VCARD', 'VERSION:3.0', f'N:{esc(last)};{esc(first)};;;', f'FN:{esc((first + " " + last).strip() or org)}']
    if org:
        lines.append(f'ORG:{esc(org)}')
    if fields['vc_title']:
        lines.append(f'TITLE:{esc(fields["vc_title"])}')
    if fields['vc_phone']:
        lines.append(f'TEL;TYPE=WORK,VOICE:{esc(fields["vc_phone"])}')
    if fields['vc_mobile']:
        lines.append(f'TEL;TYPE=CELL:{esc(fields["vc_mobile"])}')
    if fields['vc_email']:
        lines.append(f'EMAIL:{esc(fields["vc_email"])}')
    if fields['vc_web']:
        lines.append(f'URL:{esc(fields["vc_web"])}')
    if any(fields[k] for k in ('vc_street', 'vc_zip', 'vc_city', 'vc_country')):
        lines.append(f'ADR;TYPE=WORK:;;{esc(fields["vc_street"])};{esc(fields["vc_city"])};;{esc(fields["vc_zip"])};{esc(fields["vc_country"])}')
    if fields['vc_note']:
        lines.append(f'NOTE:{esc(fields["vc_note"])}')
    lines.append('END:VCARD')
    return '\n'.join(lines)


def email(v: dict) -> str:
    to = _clean(v.get('mail_to'))
    if not to:
        return ''
    query = []
    if _clean(v.get('mail_subject')):
        query.append('subject=' + quote(_clean(v.get('mail_subject')), safe=''))
    if _clean(v.get('mail_body')):
        query.append('body=' + quote(_clean(v.get('mail_body')), safe=''))
    return 'mailto:' + quote(to, safe='@+') + ('?' + '&'.join(query) if query else '')


def sms(v: dict) -> str:
    number = re.sub(r'[^\d+]', '', _clean(v.get('sms_number')))
    if not number:
        return ''
    return f'SMSTO:{number}:{_clean(v.get("sms_message"))}'


def phone(v: dict) -> str:
    number = re.sub(r'[^\d+]', '', _clean(v.get('tel_number')))
    return f'tel:{number}' if number else ''


def geo(v: dict) -> str:
    try:
        lat = float(_clean(v.get('geo_lat')).replace(',', '.'))
        lon = float(_clean(v.get('geo_lon')).replace(',', '.'))
    except ValueError:
        return ''
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return ''
    return f'geo:{lat:g},{lon:g}'


def _ical_time(value: str) -> str:
    """``2027-03-17T09:00`` (what the editor stores) as an iCalendar floating time, or ``''``."""
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(value.strip(), fmt).strftime('%Y%m%dT%H%M%S')
        except ValueError:
            continue
    return ''


def event(v: dict) -> str:
    title = _clean(v.get('ev_title'))
    start = _ical_time(_clean(v.get('ev_start')))
    if not title or not start:
        return ''
    esc = lambda s: _backslash(s, r'\;,').replace('\n', '\\n')   # noqa: E731
    end = _ical_time(_clean(v.get('ev_end')))
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'BEGIN:VEVENT', f'SUMMARY:{esc(title)}', f'DTSTART:{start}']
    if end:
        lines.append(f'DTEND:{end}')
    if _clean(v.get('ev_location')):
        lines.append(f'LOCATION:{esc(_clean(v.get("ev_location")))}')
    if _clean(v.get('ev_description')):
        lines.append(f'DESCRIPTION:{esc(_clean(v.get("ev_description")))}')
    lines += ['END:VEVENT', 'END:VCALENDAR']
    return '\n'.join(lines)


def sepa(v: dict) -> str:
    """An EPC QR code ("GiroCode", EPC069-12) for a SEPA credit transfer in euro."""
    name = _clean(v.get('pay_name'))[:70]
    iban = re.sub(r'\s+', '', _clean(v.get('pay_iban'))).upper()
    if not name or not re.fullmatch(r'[A-Z]{2}\d{2}[A-Z0-9]{11,30}', iban):
        return ''
    bic = re.sub(r'\s+', '', _clean(v.get('pay_bic'))).upper()
    if bic and not re.fullmatch(r'[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?', bic):
        return ''
    amount = ''
    raw = _clean(v.get('pay_amount')).replace(',', '.')
    if raw:
        try:
            value = float(raw)
        except ValueError:
            return ''
        if not 0.01 <= value <= 999999999.99:
            return ''
        amount = f'EUR{value:.2f}'
    reference = _clean(v.get('pay_reference'))[:140]
    return '\n'.join(['BCD', '002', '1', 'SCT', bic, name, iban, amount, '', '', reference, ''])


_BUILDERS = {'wifi': wifi, 'vcard': vcard, 'email': email, 'sms': sms, 'phone': phone, 'geo': geo, 'event': event, 'sepa': sepa}


def payload_for(kind: str, values: dict) -> str:
    """The text of the code of *kind*; ``values`` holds the main value (``url`` / ``text``) and the type's keys."""
    if kind == 'url':
        return _clean(values.get('url'))
    if kind == 'text':
        return _clean(values.get('text'))
    builder = _BUILDERS.get(kind)
    return builder(values) if builder else ''
