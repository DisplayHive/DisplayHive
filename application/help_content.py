"""Built-in in-app help content: single source of truth for the initial
HelpTopic/HelpTranslation seed data, kept in sync with the DB on every
startup (see sync_help_topics), mirroring how application.permissions
keeps right_definition in sync with RIGHTS.

Topic metadata (category/context/docs_url) is always synced from PAGE_HELP
below, since it's structural. Translation bodies are only backfilled when
missing — once a topic has an 'en' translation row, sync_help_topics() will
not overwrite it, so an admin (or a future help-editing UI) can safely
change help text without it reverting on the next deploy.

Naming convention: "page.<route name>" for whole-page help. Field-level
help (e.g. "field.pretalx.api_key") can be added the same way once needed.
"""

import logging

logger = logging.getLogger(__name__)

DEFAULT_LOCALE = 'en'

# (key, category, context, docs_url, title, body)
PAGE_HELP = [
    ('page.home', 'page', 'home', None, None,
     'Overview of your DisplayHive system — connected devices, recent activity, and quick links to get started.'),
    ('page.demo', 'page', 'demo', None, None,
     'A guided walkthrough that sets up sample devices, content, and screens so you can explore DisplayHive without touching your real data.'),
    ('page.devices', 'page', 'devices', None, None,
     'Manage the physical screens/players registered to this system: pair new devices, monitor their status, and assign content.'),
    ('page.screens', 'page', 'screens', None, None,
     'Define individual screens — the logical displays that devices show content on — and configure their layout and resolution.'),
    ('page.screengroups', 'page', 'screengroups', None, None,
     'Group multiple screens together so you can manage and assign content to them all at once.'),
    ('page.content', 'page', 'content', None, None,
     'Browse and manage the content items (slides, playlists, etc.) that get shown on your screens.'),
    ('page.contenttypes', 'page', 'contenttypes', None, None,
     'Define reusable templates that describe what fields a piece of content has and how it should be structured.'),
    ('page.designs', 'page', 'designs', None, None,
     'Create and edit the visual designs used to render content — backgrounds, styling, and placement of elements.'),
    ('page.layouts', 'page', 'layouts', None, None,
     'Arrange designs and content zones into layouts that can be assigned to screens.'),
    ('page.magictags', 'page', 'magictags', None, None,
     'Manage placeholder tags (and their value lists) that get automatically substituted with dynamic data inside your content.'),
    ('page.settings', 'page', 'settings', None, None,
     'Configure system-wide options for this DisplayHive installation.'),
    ('page.logger', 'page', 'logger', None, None,
     'View system logs to monitor activity and troubleshoot issues.'),
    ('page.media', 'page', 'media', None, None,
     'Upload and manage images, videos, and other media files used in your content.'),
    ('page.matrix', 'page', 'matrix', None, None,
     'See at a glance which content is assigned to which screens across your whole device fleet.'),
    ('page.importexport', 'page', 'importexport', None, None,
     'Back up your configuration or move content, designs, and settings between DisplayHive installations.'),
    ('page.alerting', 'page', 'alerting', None, None,
     'Configure alerts that notify you when devices go offline or other important events occur.'),
    ('page.pretalx', 'page', 'pretalx', None, None,
     'Connect to a Pretalx conference schedule to automatically display session and talk information.'),
    ('page.users', 'page', 'users', None, None,
     'Manage user accounts and the permissions (rights) they have within DisplayHive.'),
]


def sync_help_topics(db):
    """Ensure help_topic contains exactly the rows described by PAGE_HELP,
    and backfill an 'en' help_translation for any topic that doesn't have
    one yet. Idempotent — safe to call on every startup.
    """
    from application.models import HelpTopic, HelpTranslation

    existing = {
        t.key: t for t in db.session.execute(db.select(HelpTopic)).scalars().all()
    }
    changed = False
    for key, category, context, docs_url, title, body in PAGE_HELP:
        topic = existing.get(key)
        if topic is None:
            topic = HelpTopic(key=key, category=category, context=context, docs_url=docs_url)
            db.session.add(topic)
            db.session.flush()
            changed = True
        elif topic.category != category or topic.context != context or topic.docs_url != docs_url:
            topic.category = category
            topic.context = context
            topic.docs_url = docs_url
            changed = True

        has_translation = db.session.execute(
            db.select(HelpTranslation).where(
                HelpTranslation.topic_id == topic.id,
                HelpTranslation.locale == DEFAULT_LOCALE,
            )
        ).first() is not None
        if not has_translation:
            db.session.add(HelpTranslation(
                topic_id=topic.id, locale=DEFAULT_LOCALE, title=title, body=body,
            ))
            changed = True

    if changed:
        db.session.commit()
