"""Date / time: a clock the screen keeps ticking, in the instance's time zone (frontends/screen/ts/screen/clock.ts)."""

import logging
from html import escape as _html_escape

from markupsafe import Markup

from application.plugins.handlers import FieldHandler, RenderContext

logger = logging.getLogger(__name__)


class Handler(FieldHandler):
    id = 'datetime_format'

    def render(self, rc: RenderContext):
        fmt_str = str(rc.values.get(rc.field_name, 'HH:mm:ss')).strip()
        tz_name = 'UTC'
        if rc.db is not None:
            try:
                from application.models import SystemSetting
                tz_row = rc.db.session.execute(
                    rc.db.select(SystemSetting).where(SystemSetting.key == 'timezone')
                ).scalar_one_or_none()
                if tz_row and tz_row.value:
                    tz_name = tz_row.value
            except Exception:
                logger.debug('Failed to load the timezone setting, defaulting to UTC', exc_info=True)
        return Markup(
            f'<div class="dh-clock"'
            f' data-dh-clock="{_html_escape(fmt_str)}"'
            f' data-dh-timezone="{_html_escape(tz_name)}"></div>'
        )


def register(api):
    api.fieldhandlers.add(Handler())
