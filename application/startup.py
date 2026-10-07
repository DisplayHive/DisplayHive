"""What a server process does once when it starts: raise limits, run the
best-effort startup steps, start background tasks.

`create_app(startup=False)` skips all of it — for `flask dh …` maintenance
commands that run next to a live instance (where, say, resetting every device
to offline would do real damage) and for tests that build their own state.
"""

import logging

from application import media_renditions

logger = logging.getLogger(__name__)


def raise_open_files_limit() -> None:
    """Raise the soft limit on open files to the hard limit (capped at 65536).

    Every connected screen or admin tab is an open socket, and many systems
    start services with a soft limit of 1024 — reached at a few hundred screens
    plus database connections and media files. The hard limit is usually far
    higher (the NixOS module sets LimitNOFILE explicitly).
    """
    try:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        target = 65536 if hard == resource.RLIM_INFINITY else min(hard, 65536)
        if soft != resource.RLIM_INFINITY and soft < target:
            resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))
            logger.info('Raised the open files limit from %s to %s', soft, target)
    except Exception:
        logger.warning('Could not raise the open files limit', exc_info=True)


def startup_step(db, label, fn) -> None:
    """Run a best-effort startup step, logging success/failure without aborting boot.

    Rolls the DB session back on failure so a broken step cannot poison the
    session for the next one.
    """
    try:
        fn()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.warning('Startup step failed (%s): %s', label, e)


def reset_devices_online(db) -> None:
    from application.models import Device
    db.session.execute(db.update(Device).values(is_online=False))
    db.session.commit()
    logger.info('Reset Device.is_online for all devices to False on startup')


def enforce_default_design(db) -> None:
    from application.models import Design
    has_default = db.session.execute(db.select(Design).where(Design.isDefault == True)).scalar()  # noqa: E712
    if not has_default:
        d1 = db.session.get(Design, 1)
        if d1:
            d1.isDefault = True
            db.session.commit()
            logger.info('No default design found on startup; set Design ID 1 as default')


def prune_screen_logs_startup(db) -> None:
    from application.utils import prune_screen_logs
    deleted_by_age, deleted_by_cap = prune_screen_logs(db)
    if deleted_by_age or deleted_by_cap:
        logger.info('Pruned screen_log on startup: %s by age, %s by row cap', deleted_by_age, deleted_by_cap)


def run_startup_steps(app, db) -> None:
    """Create tables (SQLite dev convenience) and run the server's startup steps."""
    from application.auth import ensure_bootstrap_admin
    from application.help_content import sync_help_topics
    from application.permissions import ensure_superadmin_group, sync_right_definitions

    with app.app_context():
        # In production "alembic upgrade head" manages the schema. create_all()
        # is a development convenience for SQLite; a no-op when all tables exist.
        if not app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql'):
            db.create_all()

        startup_step(db, 'reset Device.is_online', lambda: reset_devices_online(db))
        startup_step(db, 'enforce default design', lambda: enforce_default_design(db))
        startup_step(db, 'prune screen_log', lambda: prune_screen_logs_startup(db))
        startup_step(db, 'ensure bootstrap admin user', lambda: ensure_bootstrap_admin(app, db))
        startup_step(db, 'sync right definitions', lambda: sync_right_definitions(db))
        startup_step(db, 'ensure superadmin group', lambda: ensure_superadmin_group(db))
        startup_step(db, 'sync help topics', lambda: sync_help_topics(db))


def screen_log_retention_loop(app, db, socketio) -> None:
    """Periodically re-enforce screen_log retention while the process is running."""
    from application.utils import prune_screen_logs
    while True:
        socketio.sleep(3600)  # hourly
        try:
            with app.app_context():
                deleted_by_age, deleted_by_cap = prune_screen_logs(db)
                if deleted_by_age or deleted_by_cap:
                    logger.info('Pruned screen_log: %s by age, %s by row cap', deleted_by_age, deleted_by_cap)
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            logger.warning('Failed to prune screen_log: %s', e)


def start_background_tasks(app, db, socketio, paths) -> None:
    """Hourly log retention, and a backfill of FHD/4K/8K renditions for every
    already-uploaded image (uploads from before renditions existed, restored
    backups, copied files). The backfill only renders what's missing, so it's
    cheap on every start after the first."""
    socketio.start_background_task(screen_log_retention_loop, app, db, socketio)
    media_renditions.schedule_backfill(socketio, app, db, paths.media, paths.media_renditions)
