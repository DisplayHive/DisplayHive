"""`flask dh …` — maintenance commands for a DisplayHive instance.

    flask --app app dh create-admin USERNAME
    flask --app app dh reset-password USERNAME
    flask --app app dh check-config [--online]
    flask --app app dh rerender [--missing-only]
    flask --app app dh rerender-content [--contenttype ID]

(The Docker image sets FLASK_APP, so `flask dh …` is enough there; the
NixOS module installs a `displayhive-<instance>` wrapper.)

Run them as the user the server runs as, with the same environment
(DATABASE_URL, DATA_DIR, SECRET_KEY …) — they open the same database. Safe
next to a running server: app.py skips its startup side effects (resetting
devices to offline, background jobs, creating directories) when loaded for
one of these commands, see _loaded_for_flask_cli_command there.
"""

import os
import stat
import sys

import click
from flask.cli import AppGroup

dh = AppGroup('dh', help='DisplayHive maintenance commands.')


def _read_password(from_stdin: bool, prompt: str) -> str:
    """Read a new password: one line from stdin (for scripts), or a hidden,
    confirmed prompt. Never as a command-line argument — that would end up in
    shell history and the process list."""
    if from_stdin:
        password = sys.stdin.readline().rstrip('\r\n')
    else:
        password = click.prompt(prompt, hide_input=True, confirmation_prompt=True)
    from application.auth import password_problem
    problem = password_problem(password)
    if problem:
        raise click.ClickException(problem)
    return password


def _find_user(db, username):
    from application.models import AdminUser
    user = db.session.execute(db.select(AdminUser).where(AdminUser.username == username)).scalar_one_or_none()
    if user is None:
        raise click.ClickException(f"No user named '{username}'.")
    return user


# --- create-admin ---------------------------------------------------------------


@dh.command('create-admin')
@click.argument('username')
@click.option('--password-stdin', is_flag=True, help='Read the password from stdin instead of prompting.')
@click.option('--no-superadmin', is_flag=True, help="Don't add the account to the Superadmin group.")
@click.option('--force-change', is_flag=True, help='Make the user choose a new password on first login.')
def create_admin(username, password_stdin, no_superadmin, force_change):
    """Create an admin account (a Superadmin unless --no-superadmin)."""
    from flask import current_app
    from application.models import AdminUser, Group, UserGroup
    from application.auth import hash_password
    from application.permissions import sync_right_definitions, ensure_superadmin_group

    db = current_app.extensions['sqlalchemy']
    username = username.strip()
    if not username:
        raise click.ClickException('Username is required.')
    if db.session.execute(db.select(AdminUser.id).where(AdminUser.username == username)).first():
        raise click.ClickException(f"A user named '{username}' already exists — use reset-password instead.")
    password = _read_password(password_stdin, f'Password for {username}')

    if not no_superadmin:
        # The server does this on start; a fresh database may not have run it
        # yet. Before creating the user: creating the group adds every
        # existing account to it.
        sync_right_definitions(db)
        ensure_superadmin_group(db)

    user = AdminUser(
        username=username,
        password_hash=hash_password(password),
        is_active=True,
        must_change_password=force_change,
    )
    db.session.add(user)
    db.session.flush()
    if not no_superadmin:
        group = db.session.execute(db.select(Group).where(Group.is_superadmin.is_(True))).scalar_one()
        already = db.session.execute(
            db.select(UserGroup).where(UserGroup.user_id == user.id, UserGroup.group_id == group.id)
        ).first()
        if not already:
            db.session.add(UserGroup(user_id=user.id, group_id=group.id))
    db.session.commit()
    role = 'admin account' if no_superadmin else 'Superadmin'
    click.echo(f"Created {role} '{username}'." + (' It must choose a new password on first login.' if force_change else ''))


# --- reset-password -------------------------------------------------------------


@dh.command('reset-password')
@click.argument('username')
@click.option('--password-stdin', is_flag=True, help='Read the password from stdin instead of prompting.')
@click.option('--force-change', is_flag=True, help='Make the user choose another password on next login.')
@click.option('--activate', is_flag=True, help='Also reactivate the account if it is deactivated.')
def reset_password(username, password_stdin, force_change, activate):
    """Set a new password for USERNAME and log it out everywhere.

    Also turns password login on for the account — the way back in when
    every SSO provider is down or the last Superadmin is locked out.
    """
    from flask import current_app
    from application.auth import hash_password

    db = current_app.extensions['sqlalchemy']
    user = _find_user(db, username)
    password = _read_password(password_stdin, f'New password for {username}')

    user.password_hash = hash_password(password)
    user.password_login_allowed = True
    user.must_change_password = force_change
    user.token_version = (user.token_version or 0) + 1  # revoke existing sessions
    if activate:
        user.is_active = True
    db.session.commit()

    click.echo(f"Password for '{username}' reset; existing sessions are logged out.")
    if not user.is_active:
        click.secho('Note: the account is deactivated — add --activate to log in with it.', fg='yellow')


# --- rerender (media) ---------------------------------------------------------------


def rerender_media(db, media_root, previews_root, renditions_root, missing_only=False, progress=None) -> dict:
    """Recreate the preview and FHD/4K/8K renditions of every Media row.

    *missing_only* only fills gaps (what the Media page's "Sync previews"
    does); otherwise everything is rendered from scratch — e.g. after
    changing the preview or rendition settings, or to repair corrupt files.
    *progress* is called once per media item. Returns counts.
    """
    from application import media_renditions
    from application.models import Media

    stats = {'media': 0, 'previews': 0, 'renditions': 0, 'missing_source': 0}
    rows = db.session.execute(db.select(Media).order_by(Media.id)).scalars().all()
    for m in rows:
        stats['media'] += 1
        rel = f'{m.folder_path}/{m.filename}' if m.folder_path else m.filename
        source = os.path.join(media_root, rel)
        if progress:
            progress(rel)
        if not os.path.isfile(source):
            stats['missing_source'] += 1
            continue
        is_video = bool(m.mime_type and m.mime_type.startswith('video/'))

        preview = media_renditions.preview_path(previews_root, rel)
        if not (missing_only and os.path.exists(preview)):
            if os.path.exists(preview):
                os.remove(preview)  # so a failed re-render shows up as missing, not as stale
            media_renditions.create_preview(source, preview, is_video)
            if os.path.exists(preview) and not is_video:
                stats['previews'] += 1

        if not is_video:
            if not missing_only:
                media_renditions.remove_renditions(renditions_root, rel)
            stats['renditions'] += len(media_renditions.render_renditions(source, renditions_root, rel))
    return stats


@dh.command('rerender')
@click.option('--missing-only', is_flag=True, help='Only create previews/renditions that are missing.')
def rerender(missing_only):
    """Re-render the previews and FHD/4K/8K renditions of all media files.

    Without --missing-only every preview and rendition is rendered again from
    the original upload. Originals are never touched.
    """
    from flask import current_app
    from application.models import Media

    app = current_app
    db = app.extensions['sqlalchemy']
    total = db.session.execute(db.select(db.func.count()).select_from(Media)).scalar()
    with click.progressbar(length=total, label='Rendering media', show_pos=True,
                           item_show_func=lambda rel: rel) as bar:
        def _step(rel):
            bar.update(1, rel)
        stats = rerender_media(
            db, app.config['MEDIA_FOLDER'], app.config['PREVIEW_FOLDER'], app.config['MEDIA_RENDITIONS_FOLDER'],
            missing_only=missing_only, progress=_step,
        )
    click.echo(f"Done: {stats['media']} media file(s), {stats['previews']} preview(s) and "
               f"{stats['renditions']} rendition(s) written.")
    if stats['missing_source']:
        click.secho(f"{stats['missing_source']} media file(s) are missing on disk and were skipped.", fg='yellow')


# --- rerender-content --------------------------------------------------------------


def rerender_all(db, contenttype_ids=None, echo=click.echo) -> int:
    """Re-render the stored HTML of every content element (of *contenttype_ids*,
    or of all content types). Returns how many elements were updated."""
    from application.models import Contenttype
    from application.admin.content.helper import rerender_content_element_for_contenttype

    if not contenttype_ids:
        contenttype_ids = db.session.execute(db.select(Contenttype.id).order_by(Contenttype.id)).scalars().all()
    total = 0
    for ct_id in contenttype_ids:
        if db.session.get(Contenttype, ct_id) is None:
            echo(f'Content type {ct_id}: not found, skipped')
            continue
        updated = rerender_content_element_for_contenttype(db, ct_id)
        total += len(updated)
        echo(f'Content type {ct_id}: re-rendered {len(updated)} content element(s)')
    echo(f'Done. Re-rendered {total} content element(s).')
    return total


@dh.command('rerender-content')
@click.option('--contenttype', 'contenttype_ids', type=int, multiple=True,
              help='Only this content type ID (repeatable). Default: all.')
def rerender_content(contenttype_ids):
    """Re-render the stored HTML of all content.

    Refreshes field rendering after an update, magic tags and Pretalx tables.
    Running screens get the new HTML with their next content push (e.g. the
    next content change or reconnect) — this command can't reach them itself.
    """
    from flask import current_app
    rerender_all(current_app.extensions['sqlalchemy'], list(contenttype_ids))


# --- check-config --------------------------------------------------------------


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
    from application import paths as data_paths
    import logging
    logging.getLogger('alembic').setLevel(logging.WARNING)  # its INFO lines would drown the report
    report = _Report()

    report.section('Configuration')
    secret = os.environ.get('SECRET_KEY', '')
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
    if os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes', 'on'):
        report('warn', 'FLASK_DEBUG is on — the Werkzeug debugger allows code execution; never on a reachable host')
    proxies = os.environ.get('TRUSTED_PROXY_COUNT', '0') or '0'
    report('info', f'TRUSTED_PROXY_COUNT={proxies} — must equal the number of reverse proxies in front of the app')
    report('info', f"Deployment: {app.config.get('DEPLOYMENT_KIND', 'manual')}")

    report.section('Data directory')
    paths = app.DATA_PATHS if hasattr(app, 'DATA_PATHS') else data_paths.resolve()
    report('info', f'DATA_DIR: {paths.data_dir}')
    _check_dir(report, 'data dir', paths.data_dir, private=False)
    for name in data_paths.MEDIA_DIRS:
        _check_dir(report, name, getattr(paths, name), private=False)
    _check_dir(report, 'import-staging', paths.import_staging, private=True)
    for legacy in paths.legacy:
        report('warn', f"{legacy['kind']} still in the legacy location {legacy['path']} — see "
                       "'Moving data to DATA_DIR' in the installation docs")

    report.section('Database')
    schema_ok = _check_database(report, app, db, paths)

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
    from application import paths as data_paths
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    uri = app.config['SQLALCHEMY_DATABASE_URI']
    if app.config.get('SQLITE_IN_USE'):
        report('warn', f'SQLite ({paths.db_path}) — fine for testing, use PostgreSQL (DATABASE_URL) in production')
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


def _check_accounts(report, db):
    from application.models import AdminUser
    from application.permissions import password_superadmin_exists

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
    from application import oidc

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


def register_cli(app):
    app.cli.add_command(dh)
