"""Pretalx: conference schedules from a Pretalx API as list, current/next session, event day or track list.

The plugin brings its field handler (``pretalx_table``), its page (admin/), the events that page talks to
and the poller that fetches the schedules (events.py), its tables (models.py, adopted from older versions
of DisplayHive) and its rights (plugin.json).
"""

import json
import logging

from markupsafe import Markup

from application.plugins.handlers import FieldHandler, RenderContext

logger = logging.getLogger(__name__)


class Handler(FieldHandler):
    id = 'pretalx_table'
    refresh_after_show = True        # live schedule data: the screen asks for a fresh render after each display

    def render(self, rc: RenderContext):
        from .render import _get_pretalx_data, _render_pretalx_table
        field_name, ctx, db = rc.field_name, rc.values, rc.db
        pretalx_data = _get_pretalx_data(str(ctx.get(field_name, '')).strip(), db)
        _ps_no_session  = 'No session running'
        _ps_coming_up   = 'Coming up next'
        _ps_invalid     = 'Invalid API data'
        _ps_time_format = 'HH:mm'
        _ps_end_of_day  = '23:59'
        _ps_sim_dt      = ''
        try:
            if db is not None:
                from .models import load_models
                _ps = db.session.execute(db.select(load_models().PretalxSettings)).scalar_one_or_none()
                if _ps:
                    _ps_no_session  = _ps.no_session_text or _ps_no_session
                    _ps_coming_up   = _ps.coming_up_text  or _ps_coming_up
                    _ps_invalid     = _ps.invalid_data_text or _ps_invalid
                    _ps_time_format = _ps.time_format or _ps_time_format
                    _ps_end_of_day  = _ps.end_of_day  or _ps_end_of_day
                    _ps_sim_dt      = _ps.sim_datetime or ''
        except Exception:
            logger.debug('Failed to load pretalx settings, using defaults', exc_info=True)
        _el_invalid = str(ctx.get(f'{field_name}__invalid_data_text', '')).strip()
        if _el_invalid:
            _ps_invalid = _el_invalid
        return Markup(_render_pretalx_table(
            data=pretalx_data,
            roomname=str(ctx.get(f'{field_name}__roomname', '')).strip(),
            linecount=ctx.get(f'{field_name}__linecount', 10),
            fields_config=str(ctx.get(f'{field_name}__fields', '')).strip(),
            display_author=bool(ctx.get(f'{field_name}__author_under_title', False)),
            display_type=str(ctx.get(f'{field_name}__type', 'list')).strip() or 'list',
            empty_text=str(ctx.get(f'{field_name}__empty_text', '')).strip(),
            tracklist_columns=str(ctx.get(f'{field_name}__tracklist_columns', 'name|Name,color|Color')).strip(),
            tracklist_layout=str(ctx.get(f'{field_name}__tracklist_layout', 'list')).strip() or 'list',
            tracklist_exclude=str(ctx.get(f'{field_name}__tracklist_exclude', '')).strip(),
            invalid_data_text=_ps_invalid,
            no_session_text=_ps_no_session,
            coming_up_text=_ps_coming_up,
            time_format=_ps_time_format,
            end_of_day=_ps_end_of_day,
            sim_datetime=_ps_sim_dt,
            today_only=bool(ctx.get(f'{field_name}__today_only', False)),
            separate_days=bool(ctx.get(f'{field_name}__separate_days', False)),
            day_prefix=str(ctx.get(f'{field_name}__day_prefix', '')).strip(),
            tracks_by_color=bool(ctx.get(f'{field_name}__tracks_by_color', False)),
        ))

    def default_values(self, packed: str) -> dict:
        try:
            parsed = json.loads(packed)
        except (ValueError, TypeError):
            parsed = {}
        return {
            'default': parsed.get('url', ''),
            'default__type': parsed.get('type', 'list'),
            'default__roomname': parsed.get('roomname', ''),
            'default__fields': parsed.get('fields', ''),
            'default__linecount': parsed.get('linecount', 10),
            'default__author_under_title': parsed.get('author_under_title', False),
            'default__tracks_by_color': parsed.get('tracks_by_color', False),
            'default__today_only': parsed.get('today_only', False),
            'default__separate_days': parsed.get('separate_days', False),
            'default__day_prefix': parsed.get('day_prefix', ''),
            'default__empty_text': parsed.get('empty_text', ''),
            'default__tracklist_columns': parsed.get('tracklist_columns', 'name|Name,color|Color'),
            'default__tracklist_layout': parsed.get('tracklist_layout', 'list'),
            'default__tracklist_exclude': parsed.get('tracklist_exclude', ''),
            'default__invalid_data_text': parsed.get('invalid_data_text', ''),
        }


def register(api):
    from .events import register_events
    from .models import load_models
    load_models()
    from .data import PretalxData
    api.fieldhandlers.add(Handler())
    api.data.add(PretalxData())
    api.help.add('page.pretalx', 'Connect to a Pretalx conference schedule to automatically display session and talk information.')
    register_events(api)
