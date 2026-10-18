"""Shared Telegram alert sender for the DisplayHive alerting system."""

import logging

import requests

from application.core.timeutil import utcnow

logger = logging.getLogger(__name__)

ALERT_TYPES = [
    ('screen_offline',       'Screen Offline'),
    ('screen_online',        'Screen Online'),
    ('screen_not_maximized', 'Screen Not Maximized'),
    ('screen_maximized',     'Screen Maximized'),
    ('screen_debug_on',      'Screen in Debug Mode'),
    ('screen_debug_off',     'Screen no longer in Debug Mode'),
    ('screen_find_on',       'Screen in Find Mode'),
    ('screen_find_off',      'Screen no longer in Find Mode'),
    ('device_offline',       'Device Offline'),
    ('device_online',        'Device Online'),
]

ALERT_LABELS = dict(ALERT_TYPES)


def fire_alert(db, alert_type: str, subject: str) -> None:
    """Send a Telegram message to all users subscribed to *alert_type*.

    subject — human-readable name of the affected screen or device.
    All errors are caught and logged; callers must not handle exceptions.
    """
    try:
        from application.models import SystemSetting, TelegramUser, AlertSubscription

        token_row = db.session.execute(
            db.select(SystemSetting).where(SystemSetting.key == 'telegram_token')
        ).scalar_one_or_none()
        if not token_row or not token_row.value:
            return

        token = token_row.value
        label = ALERT_LABELS.get(alert_type, alert_type)
        now = utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        text = f'[DisplayHive] {label}\n{subject}\n{now}'

        recipients = db.session.execute(
            db.select(TelegramUser)
            .join(AlertSubscription, AlertSubscription.user_id == TelegramUser.id)
            .where(AlertSubscription.alert_type == alert_type)
        ).scalars().all()

        for user in recipients:
            try:
                requests.post(
                    f'https://api.telegram.org/bot{token}/sendMessage',
                    json={'chat_id': user.chat_id, 'text': text},
                    timeout=5,
                )
            except Exception:
                logger.warning('[Alert] Failed to send to %s', user.name)

    except Exception:
        logger.exception('[Alert] Error firing alert "%s"', alert_type)
