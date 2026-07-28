"""Pretalx schedule + table rendering helpers for the admin Content page.

Self-contained rendering routines consumed by ``content.helper.render_content_fields``
to turn Pretalx API data (and generic table field values) into HTML. Kept in a separate
module so the general content element renderer stays focused and this Pretalx-specific logic
can be read and tested on its own.
"""

import json
import logging
from html import escape as _html_escape

logger = logging.getLogger(__name__)


def _parse_eod(eod_str: str):
    """Parse 'HH:MM' end_of_day string, return (hour, minute). Defaults to (23, 59)."""
    try:
        h, m = str(eod_str or '23:59').strip().split(':')
        return int(h), int(m)
    except Exception:
        return 23, 59


def _pretalx_day_key(talk_start, eod_h: int, eod_m: int):
    """Return the day_start datetime of the Pretalx day this talk belongs to."""
    from datetime import timedelta
    eod_at_date = talk_start.replace(hour=eod_h, minute=eod_m, second=0, microsecond=0)
    if talk_start < eod_at_date:
        return eod_at_date - timedelta(hours=24)
    return eod_at_date


def _tokens_to_strftime(fmt: str) -> str:
    """Convert Moment.js-style tokens (HH, mm, …) to Python strftime codes."""
    for token, code in [
        ('YYYY', '%Y'), ('YY', '%y'),
        ('dddd', '%A'), ('ddd', '%a'),
        ('DD', '%d'), ('MM', '%m'),
        ('HH', '%H'), ('mm', '%M'), ('ss', '%S'),
    ]:
        fmt = fmt.replace(token, code)
    return fmt


def _talk_times(talk: dict, sim_now=None):
    """Return (start, end, now) datetimes for a talk, or None on failure."""
    date_str = talk.get('date', '')
    if not date_str:
        return None
    try:
        from datetime import datetime, timedelta, timezone
        start = datetime.fromisoformat(date_str)
        duration_str = str(talk.get('duration', '') or '')
        if duration_str:
            h, _, m = duration_str.partition(':')
            delta = timedelta(hours=int(h or 0), minutes=int(m or 0))
        else:
            delta = timedelta()
        end = start + delta
        if sim_now is not None:
            tz = start.tzinfo or timezone.utc
            now = sim_now.replace(tzinfo=tz) if sim_now.tzinfo is None else sim_now
        else:
            now = datetime.now(tz=start.tzinfo or timezone.utc)
        return start, end, now
    except Exception:
        return None


def _talk_has_ended(talk: dict, sim_now=None) -> bool:
    """Return True if date + duration is in the past."""
    t = _talk_times(talk, sim_now=sim_now)
    return t is not None and t[1] < t[2]


def _talk_is_current(talk: dict, sim_now=None) -> bool:
    """Return True if the talk is currently running (start <= now < end)."""
    t = _talk_times(talk, sim_now=sim_now)
    return t is not None and t[0] <= t[2] < t[1]


def _talk_is_upcoming(talk: dict, sim_now=None) -> bool:
    """Return True if the talk has not started yet."""
    t = _talk_times(talk, sim_now=sim_now)
    return t is not None and t[2] < t[0]



def _extract_talk_value(talk: dict, field_key: str, date_fmt: str = '%H:%M') -> str:
    """Extract a display value from a Pretalx talk dict for any field key."""
    if field_key == 'color':
        # Pre-resolved from conference.tracks (injected as _track_color)
        resolved = talk.get('_track_color')
        if resolved:
            return str(resolved)
        # Fallback: track is an object with a color key
        track = talk.get('track')
        if isinstance(track, dict):
            return str(track.get('color', '') or '')
        return ''
    if field_key == 'person':
        persons = talk.get('persons') or []
        if persons and isinstance(persons, list):
            first = persons[0]
            if isinstance(first, dict):
                return str(first.get('public_name', '') or first.get('name', ''))
            return str(first)
        return ''
    val = talk.get(field_key)
    if val is None:
        return ''
    if field_key == 'date':
        try:
            from datetime import datetime
            return datetime.fromisoformat(str(val)).strftime(date_fmt)
        except Exception:
            return str(val)
    if isinstance(val, dict):
        return str(val.get('name', '') or val.get('public_name', '') or '')
    if isinstance(val, list):
        parts = []
        for item in val:
            if isinstance(item, dict):
                parts.append(str(item.get('public_name', '') or item.get('name', '')))
            else:
                parts.append(str(item))
        return ', '.join(p for p in parts if p)
    return str(val)



def _render_pretalx_eventday(data: dict, day_prefix: str = '', sim_datetime: str = '') -> str:
    """Return the current event day number relative to conference start as an HTML span.

    Day 1 = conference start date, Day 0 = day before conference start, Day -1 = two days before, etc.
    The current date is resolved in the conference's own timezone (time_zone_name).
    """
    from datetime import datetime, timezone
    conf = data.get('schedule', {}).get('conference', {})
    start_str = str(conf.get('start', '') or '')
    tz_name = str(conf.get('time_zone_name', '') or '')
    if not start_str:
        return '<span class="pretalx-eventday pretalx-error">?</span>'
    try:
        from datetime import date
        start_date = date.fromisoformat(start_str)
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(tz_name) if tz_name else timezone.utc
        except Exception:
            tz = timezone.utc
        if sim_datetime:
            try:
                sim_dt = datetime.fromisoformat(sim_datetime.strip())
                today = sim_dt.astimezone(tz).date() if sim_dt.tzinfo else sim_dt.date()
            except Exception:
                today = datetime.now(tz=tz).date()
        else:
            today = datetime.now(tz=tz).date()
        day_num = (today - start_date).days + 1
        prefix = (day_prefix.strip() or 'Day')
        label = _html_escape(f'{prefix} {day_num}')
        return f'<span class="pretalx-eventday">{label}</span>'
    except Exception:
        logger.exception('pretalx eventday calculation failed')
        return '<span class="pretalx-eventday pretalx-error">?</span>'


def _render_pretalx_tracklist(data: dict, columns_config: str, layout: str, exclude: str = '') -> str:
    """Render the conference track list from a parsed Pretalx schedule JSON dict."""
    conference = data.get('schedule', {}).get('conference', {})
    tracks = [t for t in (conference.get('tracks') or []) if isinstance(t, dict)]

    if exclude:
        excluded = {e.strip().lower() for e in exclude.split(',') if e.strip()}
        tracks = [t for t in tracks if t.get('name', '').lower() not in excluded and t.get('slug', '').lower() not in excluded]

    if not tracks:
        return '<p class="pretalx-empty">No tracks found.</p>'

    columns = []
    for part in (columns_config or 'name|Name,color|Color').split(','):
        part = part.strip()
        if not part:
            continue
        if '|' in part:
            key, _, header = part.partition('|')
            columns.append((key.strip(), header.strip()))
        else:
            columns.append((part, part))
    if not columns:
        columns = [('name', 'Name'), ('color', 'Color')]

    def _track_cells(track):
        cells = []
        for col, _ in columns:
            val = str(track.get(col, '') or '')
            if col == 'color':
                cells.append(f'<td class="pt-color" style="--pt-color:{_html_escape(val)};"></td>')
                cells.append('<td class="pretalx_spacer"></td>')
            else:
                cells.append(f'<td class="pt-{_html_escape(col)}">{_html_escape(val)}</td>')
        return cells

    if layout == 'row':
        # All tracks in a single table row, one <td> per field per track
        cells = []
        for track in tracks:
            cells.extend(_track_cells(track))
        return (
            '<table class="pretalx-table pretalx-tracklist pretalx-tracklist-row">'
            '<tbody><tr>' + ''.join(cells) + '</tr></tbody>'
            '</table>'
        )

    # list layout: one track per row
    header_row = ''.join(f'<th>{_html_escape(h)}</th>' for _, h in columns)
    rows = []
    for track in tracks:
        rows.append(f'<tr>{"".join(_track_cells(track))}</tr>')
    return (
        '<table class="pretalx-table pretalx-tracklist">'
        f'<thead><tr>{header_row}</tr></thead>'
        '<tbody>' + ''.join(rows) + '</tbody>'
        '</table>'
    )


def _build_talk_table(talks, visible_columns, author_mode, date_fmt, tracks_by_color=False):
    """Build a <table> HTML string from a list of talks."""
    header_row = ''.join(f'<th>{_html_escape(h)}</th>' for _, h in visible_columns)
    rows = []
    for talk in talks:
        cells_html = []
        for k, _ in visible_columns:
            val = _extract_talk_value(talk, k, date_fmt=date_fmt)
            if k == 'color' or (k == 'track' and tracks_by_color):
                color = _html_escape(val if k == 'color' else _extract_talk_value(talk, 'color'))
                extra = ' rowspan="2"' if author_mode else ''
                cells_html.append(
                    f'<td class="pt-color"{extra} style="--pt-color:{color};"></td>'
                )
            elif k == 'title':
                cells_html.append(f'<td class="pt-title">{_html_escape(val)}</td>')
            else:
                extra = ' rowspan="2"' if author_mode else ''
                cells_html.append(
                    f'<td class="pt-{_html_escape(k)}"{extra}>{_html_escape(val)}</td>'
                )
        rows.append(f'<tr>{"".join(cells_html)}</tr>')
        if author_mode:
            person = _html_escape(_extract_talk_value(talk, 'person'))
            rows.append(f'<tr><td class="pt-author">{person}</td></tr>')
    return (
        '<table class="pretalx-table">'
        f'<thead><tr>{header_row}</tr></thead>'
        '<tbody>' + ''.join(rows) + '</tbody>'
        '</table>'
    )


def _render_pretalx_table(data: dict, roomname: str, linecount, fields_config: str = '',
                           display_author: bool = False, display_type: str = 'list',
                           empty_text: str = '', tracklist_columns: str = 'name|Name,color|Color',
                           tracklist_layout: str = 'list', tracklist_exclude: str = '',
                           invalid_data_text: str = 'Invalid API data',
                           no_session_text: str = 'No session running',
                           coming_up_text: str = 'Coming up next',
                           time_format: str = 'HH:mm', end_of_day: str = '23:59',
                           sim_datetime: str = '', today_only: bool = False,
                           separate_days: bool = False, day_prefix: str = 'Day',
                           tracks_by_color: bool = False) -> str:
    """Render a dynamic HTML table of sessions from a parsed Pretalx schedule JSON dict."""
    if not data:
        return f'<p class="pretalx-error">{_html_escape(invalid_data_text)}</p>'

    try:
        linecount = int(linecount)
    except (ValueError, TypeError):
        linecount = 10

    if display_type == 'eventday':
        return _render_pretalx_eventday(data, day_prefix=day_prefix, sim_datetime=sim_datetime)

    if display_type == 'tracklist':
        return _render_pretalx_tracklist(data, tracklist_columns, tracklist_layout, tracklist_exclude)

    # Resolve simulation time
    _sim_now = None
    if sim_datetime:
        try:
            from datetime import datetime
            _sim_now = datetime.fromisoformat(sim_datetime.strip())
        except Exception:
            pass

    # Parse Field|Name column definitions
    columns = []
    for part in fields_config.split(','):
        part = part.strip()
        if not part:
            continue
        if '|' in part:
            key, _, header = part.partition('|')
            columns.append((key.strip(), header.strip()))
        else:
            columns.append((part, part))

    if not columns:
        columns = [('date', 'Start'), ('title', 'Title'), ('track', 'Track'), ('abstract', 'Abstract')]

    conference = data.get('schedule', {}).get('conference', {})
    track_colors = {
        t['name']: t.get('color', '')
        for t in (conference.get('tracks') or [])
        if isinstance(t, dict) and t.get('name')
    }

    selected_rooms = {r.strip() for r in roomname.split(',') if r.strip()} if roomname else set()
    days = conference.get('days', [])
    talks = []
    for day in days:
        for room, room_talks in (day.get('rooms') or {}).items():
            if selected_rooms and room not in selected_rooms:
                continue
            for talk in (room_talks or []):
                track_name = talk.get('track', '')
                if isinstance(track_name, dict):
                    track_name = track_name.get('name', '')
                talk['_track_color'] = track_colors.get(str(track_name or ''), '')
                talk['_room'] = room
                talks.append(talk)

    talks.sort(key=lambda t: t.get('date', ''))

    # today_only: filter to the current Pretalx day window
    if today_only and display_type == 'list':
        from datetime import datetime, timedelta, timezone
        eod_h, eod_m = _parse_eod(end_of_day)
        ref_now = _sim_now if _sim_now is not None else datetime.now(timezone.utc)
        if ref_now.tzinfo is None:
            ref_now = ref_now.replace(tzinfo=timezone.utc)
        ref_local = ref_now.replace(tzinfo=None)  # strip tz for naive comparison
        eod_today = ref_local.replace(hour=eod_h, minute=eod_m, second=0, microsecond=0)
        if ref_local < eod_today:
            day_start = eod_today - timedelta(hours=24)
        else:
            day_start = eod_today
        day_end = day_start + timedelta(hours=24)
        def _in_today(t):
            tt = _talk_times(t, sim_now=_sim_now)
            if tt is None:
                return False
            s = tt[0].replace(tzinfo=None)
            return day_start <= s < day_end
        talks = [t for t in talks if _in_today(t)]

    if display_type == 'current':
        talks = [t for t in talks if _talk_is_current(t, sim_now=_sim_now)]
    elif display_type == 'coming_up':
        from datetime import datetime as _dt, timedelta as _td2, timezone as _tz2
        eod_h, eod_m = _parse_eod(end_of_day)
        _ref = (_sim_now if _sim_now is not None else _dt.now(_tz2.utc)).replace(tzinfo=None)
        _eod = _ref.replace(hour=eod_h, minute=eod_m, second=0, microsecond=0)
        _day_end = _eod if _ref < _eod else _eod + _td2(hours=24)
        def _valid_coming_up(t):
            if not _talk_is_upcoming(t, sim_now=_sim_now):
                return False
            tt = _talk_times(t, sim_now=_sim_now)
            return tt is not None and tt[0].replace(tzinfo=None) < _day_end
        upcoming = [t for t in talks if _valid_coming_up(t)]
        seen_rooms: set = set()
        per_room = []
        for t in upcoming:
            r = t.get('_room', '')
            if r not in seen_rooms:
                seen_rooms.add(r)
                per_room.append(t)
        talks = per_room
    else:
        talks = [t for t in talks if not _talk_has_ended(t, sim_now=_sim_now)]

    col_keys = [k for k, _ in columns]
    has_title = 'title' in col_keys
    has_person = 'person' in col_keys
    author_mode = display_author and has_title and has_person
    visible_columns = [(k, h) for k, h in columns if not (author_mode and k == 'person')]
    _date_fmt = _tokens_to_strftime(time_format or 'HH:mm')

    # separate_days: group into per-day tables
    if separate_days and display_type == 'list':
        from collections import defaultdict
        from datetime import date as _date_type
        eod_h, eod_m = _parse_eod(end_of_day)
        day_groups: dict = defaultdict(list)
        for talk in talks:
            tt = _talk_times(talk, sim_now=_sim_now)
            if tt is None:
                continue
            day_key = _pretalx_day_key(tt[0].replace(tzinfo=None), eod_h, eod_m)
            day_groups[day_key].append(talk)

        if not day_groups:
            msg = _html_escape(empty_text or no_session_text)
            return f'<p class="pretalx-empty">{msg}</p>'

        conf = data.get('schedule', {}).get('conference', {})
        start_str = str(conf.get('start', '') or '')
        conf_start: _date_type | None = None
        try:
            conf_start = _date_type.fromisoformat(start_str) if start_str else None
        except Exception:
            pass

        row_lines = 2 if author_mode else 1
        remaining = linecount if linecount > 0 else None  # None = unlimited
        sections = []
        for day_start in sorted(day_groups.keys()):
            if remaining is not None:
                # 1 line for the table header row, then row_lines per talk
                available = max(0, (remaining - 1) // row_lines)
                day_talks = day_groups[day_start][:available]
            else:
                day_talks = day_groups[day_start]
            if not day_talks:
                if remaining is not None:
                    break
                continue
            if remaining is not None:
                remaining -= 1 + len(day_talks) * row_lines
            if conf_start is not None:
                from datetime import timedelta as _td
                day_num = ((day_start + _td(hours=24)).date() - conf_start).days
                prefix = day_prefix.strip() if day_prefix and day_prefix.strip() else 'Day'
                day_label = _html_escape(f'{prefix} {day_num}')
            else:
                day_label = _html_escape(day_start.strftime('%d.%m.%Y'))
            table_html = _build_talk_table(day_talks, visible_columns, author_mode, _date_fmt, tracks_by_color)
            sections.append(
                f'<div class="pretalx-day-section">'
                f'<h3 class="pretalx-day-header">{day_label}</h3>'
                f'{table_html}'
                f'</div>'
            )
            if remaining is not None and remaining <= 0:
                break
        if not sections:
            msg = _html_escape(empty_text or no_session_text)
            return f'<p class="pretalx-empty">{msg}</p>'
        return ''.join(sections)

    # Normal single table — linecount budget includes the 1 header row
    row_lines = 2 if author_mode else 1
    if linecount > 0:
        max_talks = max(0, (linecount - 1) // row_lines)
        talks = talks[:max_talks]
    if not talks:
        if empty_text:
            msg = _html_escape(empty_text)
        elif display_type == 'coming_up':
            msg = _html_escape(coming_up_text)
        else:
            msg = _html_escape(no_session_text)
        return f'<p class="pretalx-empty">{msg}</p>'

    return _build_talk_table(talks, visible_columns, author_mode, _date_fmt, tracks_by_color)


def _render_table(raw_value) -> str:
    """Render a table-field_handler field value (JSON) as an HTML <table>."""
    try:
        data = json.loads(str(raw_value or ''))
        columns = data.get('columns', [])
        rows = data.get('rows', [])
        if not isinstance(columns, list) or not isinstance(rows, list):
            return ''
    except Exception:
        return ''

    parts = ['<table class="dh-table">']
    if columns:
        parts.append('<thead><tr>')
        for col in columns:
            parts.append(f'<th>{_html_escape(str(col))}</th>')
        parts.append('</tr></thead>')
    if rows:
        parts.append('<tbody>')
        for row in rows:
            parts.append('<tr>')
            if isinstance(row, list):
                for cell in row:
                    parts.append(f'<td>{_html_escape(str(cell))}</td>')
            parts.append('</tr>')
        parts.append('</tbody>')
    parts.append('</table>')
    return ''.join(parts)


def _get_pretalx_data(url_id_str: str, db) -> dict:
    """Resolve a PretalxApiUrl ID to its cached JSON dict. Returns {} on any failure."""
    if not url_id_str:
        return {}
    try:
        url_id = int(url_id_str)
    except (ValueError, TypeError):
        return {}
    if db is None:
        return {}
    try:
        from application.models import PretalxApiUrl
        url_obj = db.session.get(PretalxApiUrl, url_id)
        if url_obj and url_obj.cache and url_obj.cache.cached_json:
            return json.loads(url_obj.cache.cached_json)
    except Exception:
        logger.exception('failed to load Pretalx cache for id %s', url_id_str)
    return {}
