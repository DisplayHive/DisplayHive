"""`flask dh create-admin` and `reset-password`."""

import sys

import click

from .group import dh


def _read_password(from_stdin: bool, prompt: str) -> str:
    """Read a new password: one line from stdin (for scripts), or a hidden,
    confirmed prompt. Never as a command-line argument — that would end up in
    shell history and the process list."""
    if from_stdin:
        password = sys.stdin.readline().rstrip('\r\n')
    else:
        password = click.prompt(prompt, hide_input=True, confirmation_prompt=True)
    from application.security.auth import password_problem
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
    from application.security.auth import hash_password
    from application.security.permissions import sync_right_definitions, ensure_superadmin_group

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
    from application.security.auth import hash_password

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
