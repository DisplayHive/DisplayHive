"""`flask dh check-config`: read-only diagnosis of the configuration, database, backups, accounts and SSO."""

import os
import stat
import sys

import click

from .group import dh


class _Report:
    LABELS = {'ok': (' OK ', 'green'), 'info': ('INFO', 'blue'), 'warn': ('WARN', 'yellow'), 'fail': ('FAIL', 'red')}

    def __init__(self):
        self.failures = 0
        self.warnings = 0

    def __call__(self, level, message):
        if level == 'fail':
            self.failures += 1
        elif level == 'warn':
            self.warnings += 1
        label, color = self.LABELS[level]
        click.echo(click.style(f'[{label}]', fg=color, bold=True) + f' {message}')

    def section(self, title):
        click.echo(click.style(f'\n{title}', bold=True))


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def _check_dir(report, label, path, private):
    if not os.path.isdir(path):
        report('warn', f'{label}: {path} does not exist yet (the server creates it on start)')
        return
    if not os.access(path, os.W_OK):
        report('fail', f'{label}: {path} is not writable by {_whoami()}')
        return
    mode = _mode(path)
    if private and mode & 0o077:
        report('warn', f'{label}: {path} is mode {mode:o}, expected 700 (it can hold secrets)')
    elif mode & 0o002:
        report('warn', f'{label}: {path} is world-writable (mode {mode:o})')
    else:
        report('ok', f'{label}: {path}')


def _whoami():
    try:
        import pwd
        return pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        return f'uid {os.getuid()}'


@dh.command('check-config')
@click.option('--online', is_flag=True, help="Also contact each enabled SSO provider's discovery endpoint.")
def check_config(online):
    """Check configuration, data directories, database and accounts.

    Exits with status 1 if anything is broken (FAIL), so it can run in
    health checks or before a deploy.
    """
    from flask import current_app
    app = current_app
    db = app.extensions['sqlalchemy']
    from application.core import paths as data_paths
    import logging
    logging.getLogger('alembic').setLevel(logging.WARNING)  # its INFO lines would drown the report
    report = _Report()

    report.section('Configuration')
    secret = app.config.get('SECRET_KEY') or ''   # SECRET_KEY or the contents of SECRET_KEY_FILE
    if app.config.get('SECRET_KEY_IS_DEFAULT') or not secret:
        report('fail', 'SECRET_KEY is the insecure default — set it (e.g. openssl rand -hex 32)')
    elif len(secret) < 32:
        report('warn', f'SECRET_KEY is only {len(secret)} characters — use at least 32')
    else:
        report('ok', 'SECRET_KEY is set')
    public_url = app.config.get('PUBLIC_URL')
    if public_url:
        report('ok', f'PUBLIC_URL={public_url}')
    else:
        report('warn', 'PUBLIC_URL is unset — set it to the address people reach DisplayHive at '
                       '(the SSO redirect URI then comes from each request\'s Host header)')
    if app.config.get('CORS_WILDCARD'):
        report('warn', 'CORS allows any origin — set PUBLIC_URL (or CORS_ALLOWED_ORIGINS)')
    else:
        report('ok', 'CORS is restricted')
    if public_url and public_url.startswith('http://'):
        report('warn', f'PUBLIC_URL {public_url} is not https — the admin session cookie is then sent without '
                       'the Secure flag and travels in the clear; put DisplayHive behind TLS')
    elif not public_url:
        report('info', 'The admin session cookie is marked Secure when a request arrives over https '
                       '(behind a proxy: TRUSTED_PROXY_COUNT) or PUBLIC_URL is https')
    if os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes', 'on'):
        report('warn', 'FLASK_DEBUG is on — the Werkzeug debugger allows code execution; never on a reachable host')
    proxies = os.environ.get('TRUSTED_PROXY_COUNT', '0') or '0'
    report('info', f'TRUSTED_PROXY_COUNT={proxies} — must equal the number of reverse proxies in front of the app')
    report('info', f"Deployment: {app.config.get('DEPLOYMENT_KIND', 'manual')}")
    from application.core import version
    report('info', f'Version: {version.display()}')
    from application.security import net
    if net.private_allowed():
        report('warn', 'Outgoing requests to private networks are allowed (Settings / OUTBOUND_ALLOW_PRIVATE) — '
                       'Pretalx and SSO URLs can reach internal addresses; fine if they must, e.g. an internal Pretalx')
    else:
        report('ok', 'Outgoing requests to private networks are blocked')

    report.section('Data directory')
    paths = app.DATA_PATHS if hasattr(app, 'DATA_PATHS') else data_paths.resolve()
    report('info', f'DATA_DIR: {paths.data_dir}')
    _check_dir(report, 'data dir', paths.data_dir, private=False)
    for name in data_paths.MEDIA_DIRS:
        _check_dir(report, name, getattr(paths, name), private=False)
    _check_dir(report, 'import-staging', paths.import_staging, private=True)
    _check_dir(report, 'backups', paths.backups, private=True)
    for legacy in paths.legacy:
        report('warn', f"{legacy['kind']} still in the legacy location {legacy['path']} — see "
                       "'Moving data to DATA_DIR' in the installation docs")

    report.section('Database')
    schema_ok = _check_database(report, app, db, paths)

    report.section('Backups')
    _check_backups(report, app, db)

    report.section('Accounts')
    if schema_ok:
        _check_accounts(report, db)
    else:
        report('info', 'skipped — the database schema is not up to date')

    report.section('SSO login providers')
    if schema_ok:
        _check_sso(report, db, online)
    else:
        report('info', 'skipped — the database schema is not up to date')

    report.section('Frontend')
    admin_index = os.path.join(app.root_path, 'dist', 'admin', 'index.html')
    if os.path.isfile(admin_index):
        report('ok', 'Admin frontend is built (dist/admin)')
    else:
        report('warn', 'Admin frontend is not built — run npm run build in frontends/admin')

    click.echo()
    summary = f'{report.failures} problem(s), {report.warnings} warning(s)'
    if report.failures:
        click.secho(summary, fg='red', bold=True)
        sys.exit(1)
    click.secho(summary, fg='yellow' if report.warnings else 'green', bold=True)


def _check_database(report, app, db, paths) -> bool:
    """Connection, schema revision, SQLite file permissions. True if the schema is current."""
    from application.core import paths as data_paths
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    uri = app.config['SQLALCHEMY_DATABASE_URI']
    if app.config.get('SQLITE_IN_USE'):
        report('warn', f'SQLite ({paths.db_path}) — for development only, use PostgreSQL (DATABASE_URL) in production')
        if paths.db_path and data_paths.db_exposed(paths.db_path):
            report('warn', f'{paths.db_path} is readable by other users — it holds password hashes and '
                           f'secrets: chmod 600 {paths.db_path}')
    else:
        report('ok', f"PostgreSQL ({uri.split('@')[-1]})")

    try:
        current = MigrationContext.configure(db.session.connection()).get_current_revision()
    except Exception as e:
        report('fail', f'Cannot connect to the database: {e}')
        return False

    config = Config(os.path.join(app.root_path, 'alembic.ini'))
    config.set_main_option('script_location', os.path.join(app.root_path, 'migrations'))
    heads = set(ScriptDirectory.from_config(config).get_heads())
    if current in heads:
        report('ok', f'Schema is up to date (revision {current})')
        return True
    if current is None:
        report('fail', 'The database has no schema revision — run: alembic upgrade head')
    else:
        report('fail', f"Schema revision {current} is not the latest ({', '.join(sorted(heads))}) — run: alembic upgrade head")
    return False


def _check_backups(report, app, db):
    """Is there a recent backup, and can the tools make the next one?"""
    import shutil
    from datetime import datetime, timezone
    from application.core import backup

    settings = app.config['BACKUP_SETTINGS']
    directory = app.config['BACKUP_DIR']
    if db.engine.dialect.name == 'postgresql':
        for tool in ('pg_dump', 'pg_restore'):
            if shutil.which(tool):
                report('ok', f'{tool} is available')
            else:
                report('fail' if settings.interval_hours > 0 or settings.migration_backup else 'warn',
                       f'{tool} not found — backups (and the backup before migrating) cannot be made; '
                       'install the PostgreSQL client tools')
    if not settings.migration_backup:
        report('warn', 'MIGRATION_BACKUP is off — updates migrate the database without a backup first')
    if settings.interval_hours <= 0:
        report('warn', 'Scheduled backups are off (BACKUP_INTERVAL_HOURS=0) — make sure you back up some other way')
        return
    scheduled = [b for b in backup.list_backups(directory) if b.kind == 'scheduled']
    if not scheduled:
        report('warn', f'No scheduled backup yet in {directory} (the first one runs shortly after the app has started)')
        return
    age_hours = (datetime.now(timezone.utc) - scheduled[0].created).total_seconds() / 3600
    if age_hours > settings.interval_hours * 2 + 1:
        report('warn', f'The newest scheduled backup is {age_hours / 24:.1f} days old — see the log for backup errors')
    else:
        report('ok', f'Newest scheduled backup: {scheduled[0].path.name} (every {settings.interval_hours:g} h, keeping {settings.keep})')
    report('info', f'Backups are in {directory}, on the same disk as the data. Copy them elsewhere too.')


def _check_accounts(report, db):
    from application.models import AdminUser
    from application.security.permissions import password_superadmin_exists

    active = db.session.execute(
        db.select(db.func.count()).select_from(AdminUser).where(AdminUser.is_active.is_(True))
    ).scalar()
    if not active:
        report('fail', 'No active admin account — create one: flask dh create-admin <name>')
        return
    report('ok', f'{active} active admin account(s)')
    if password_superadmin_exists(db):
        report('ok', 'At least one active Superadmin can log in with a password (fallback when SSO is down)')
    else:
        report('fail', 'No active Superadmin with password login — fix it: flask dh reset-password <name> --activate')


def _check_sso(report, db, online):
    from application.models import AuthProvider
    from application.security import oidc

    providers = db.session.execute(
        db.select(AuthProvider).where(AuthProvider.enabled.is_(True)).order_by(AuthProvider.name)
    ).scalars().all()
    if not providers:
        report('info', 'No SSO provider enabled')
        return
    for provider in providers:
        if not online:
            report('info', f'{provider.name}: {provider.issuer} (add --online to test it)')
            continue
        try:
            oidc.discover(provider.issuer, force=True)
            report('ok', f'{provider.name}: {provider.issuer} reachable')
        except oidc.OidcError as e:
            report('fail', f'{provider.name}: {e}')
