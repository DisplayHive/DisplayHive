"""Socket handlers for the admin Users page (account management, no roles)."""

import logging

from flask import request

logger = logging.getLogger(__name__)


def register_admin_user_handlers(socketio, app, db):
    """Register socket handlers for listing/creating/updating/deleting admin users."""
    from application.socketio_handlers.auth import require_right, current_admin_user, fields, is_impersonating
    from application.socketio_handlers.actions import admin_action, get_or_fail, Fail, ok
    from application.models import AdminUser, AdminUserLogin, AdminUserIdentity
    from application.auth import hash_password, create_token, password_problem
    from application.permissions import password_superadmin_exists, PASSWORD_SUPERADMIN_ERROR

    def _commit_keeping_break_glass(had_break_glass):
        """Commit, unless the pending change removed the last active Superadmin
        with password login (and there was one before): then ``Fail``."""
        if had_break_glass and not password_superadmin_exists(db):
            raise Fail(PASSWORD_SUPERADMIN_ERROR)
        db.session.commit()

    def _emit_users(sid=None):
        """Build the full user list payload and emit it (never includes password_hash)."""
        users = db.session.execute(
            db.select(AdminUser).order_by(AdminUser.username)
        ).scalars().all()
        payload = {'users': [u.to_dict() for u in users]}
        socketio.emit('displayhive:admin:users:stc:users', payload, room=sid or 'admins')

    @socketio.on('displayhive:admin:users:cts:get_users')
    @require_right('users.page')
    def handle_get_users(data=None):
        _emit_users(getattr(request, 'sid', None))

    @socketio.on('displayhive:admin:users:cts:get_user_logins')
    @admin_action('users.page')
    def handle_get_user_logins(data=None):
        """Return a user's 5 most recent logins, newest first. data: {id}."""
        (user_id,) = fields(data, 'id')
        if not user_id:
            raise Fail('Missing id')

        logins = db.session.execute(
            db.select(AdminUserLogin)
            .where(AdminUserLogin.user_id == user_id)
            .order_by(AdminUserLogin.logged_in_at.desc())
            .limit(5)
        ).scalars().all()
        return ok(logins=[{'logged_in_at': l.logged_in_at.isoformat() if l.logged_in_at else None} for l in logins])

    @socketio.on('displayhive:admin:users:cts:create_user')
    @admin_action('users.create')
    def handle_create_user(data):
        """Create a new admin user. data: {username, password, must_change_password?}."""
        username = str((data or {}).get('username', '')).strip()
        password = str((data or {}).get('password', ''))

        if not username:
            raise Fail('Username is required')
        if password_problem(password):
            raise Fail(password_problem(password))

        existing = db.session.execute(
            db.select(AdminUser).where(AdminUser.username == username)
        ).scalar_one_or_none()
        if existing:
            raise Fail('Username already exists')

        user = AdminUser(
            username=username,
            password_hash=hash_password(password),
            must_change_password=bool((data or {}).get('must_change_password')),
        )
        db.session.add(user)
        db.session.commit()

        _emit_users()
        return ok(id=user.id)

    @socketio.on('displayhive:admin:users:cts:update_user')
    @admin_action()
    def handle_update_user(data):
        """Update an account. data: {id, username?, password?, must_change_password?,
        password_login_allowed?}.

        The fields are gated by separate rights (users.edit for username,
        users.set_password for password, must_change_password and
        password_login_allowed),
        so each requested field is checked independently and silently dropped if the
        caller lacks the right for that specific field — same pattern as
        media.rename/media.tag and device.rename/device.enable.
        """
        from application.permissions import has_right
        caller = current_admin_user()

        user = get_or_fail(db, AdminUser, (data or {}).get('id'), 'User')
        had_break_glass = password_superadmin_exists(db)
        can_set_password = has_right(db, caller, 'users.set_password')

        new_username = (data or {}).get('username')
        if new_username is not None and not has_right(db, caller, 'users.edit'):
            new_username = None
        if new_username is not None:
            new_username = str(new_username).strip()
            if not new_username:
                raise Fail('Username is required')
            if new_username != user.username:
                existing = db.session.execute(
                    db.select(AdminUser).where(AdminUser.username == new_username)
                ).scalar_one_or_none()
                if existing:
                    raise Fail('Username already exists')
                user.username = new_username

        new_password = (data or {}).get('password')
        if new_password and not can_set_password:
            new_password = None
        if new_password:
            if password_problem(new_password):
                raise Fail(password_problem(new_password))
            user.password_hash = hash_password(new_password)
            # Invalidate every JWT issued before this password change.
            user.token_version = (user.token_version or 0) + 1

        password_login = (data or {}).get('password_login_allowed')
        if password_login is not None and can_set_password:
            password_login = bool(password_login)
        elif new_password:
            # Giving an account a password (e.g. an SSO-created one) is what
            # an admin does to let it log in with one.
            password_login = True
        else:
            password_login = None
        if password_login is not None:
            if password_login and not user.password_hash:
                raise Fail('Set a password before allowing password login')
            user.password_login_allowed = password_login
            if not password_login:
                user.must_change_password = False

        must_change = (data or {}).get('must_change_password')
        if must_change is not None and can_set_password:
            must_change = bool(must_change)
            if must_change and not user.password_login_allowed:
                raise Fail('A password reset needs password login to be allowed')
            if must_change and not user.must_change_password:
                # Log the account out everywhere, so its next login (not some
                # half-dead existing session) is what asks for the new password.
                user.token_version = (user.token_version or 0) + 1
            user.must_change_password = must_change

        _commit_keeping_break_glass(had_break_glass)
        _emit_users()
        return ok()

    @socketio.on('displayhive:admin:users:cts:unlink_identity')
    @admin_action('users.edit')
    def handle_unlink_identity(data):
        """Remove one SSO identity from its account. data: {id} (identity id).

        Its next SSO login creates a fresh account again.
        """
        identity = get_or_fail(db, AdminUserIdentity, (data or {}).get('id'), 'Identity')
        db.session.delete(identity)
        db.session.commit()
        _emit_users()
        return ok()

    @socketio.on('displayhive:admin:users:cts:merge_user')
    @admin_action()
    def handle_merge_user(data):
        """Move every SSO identity of *source* onto *target*, then delete *source*.
        data: {source_id, target_id}.

        The admin-side way to link an SSO login to an existing account: the
        account its first login created is folded into the real one.
        Needs both users.edit and users.delete.
        """
        from application.permissions import has_right
        caller = current_admin_user()
        if not (has_right(db, caller, 'users.edit') and has_right(db, caller, 'users.delete')):
            raise Fail('Permission denied')

        source_id, target_id = fields(data, 'source_id', 'target_id')
        source = get_or_fail(db, AdminUser, source_id, 'User')
        target = get_or_fail(db, AdminUser, target_id, 'User')
        if source.id == target.id:
            raise Fail('Choose a different user to merge into')
        if caller and source.id == caller.id:
            raise Fail('You cannot merge away your own account')
        if not source.identities:
            raise Fail('This account has no SSO login to move')
        if source.password_hash:
            # Merging deletes the source; only throwaway accounts an SSO login
            # created (which never have a password) qualify. A real local
            # account's SSO login can be unlinked instead.
            raise Fail('Only accounts created by an SSO login (without a password) can be merged')

        had_break_glass = password_superadmin_exists(db)
        for identity in list(source.identities):
            identity.user = target
        db.session.flush()
        db.session.delete(source)
        _commit_keeping_break_glass(had_break_glass)
        logger.info("Merged SSO account '%s' into '%s'", source.username, target.username)
        _emit_users()
        return ok()

    @socketio.on('displayhive:admin:users:cts:set_active')
    @admin_action('users.activate')
    def handle_set_active(data):
        """Activate/deactivate a user. data: {id, is_active}. Refuses to leave zero active admins."""
        user_id, is_active = fields(data, 'id', 'is_active')
        is_active = bool(is_active)
        user = get_or_fail(db, AdminUser, user_id, 'User')

        if not is_active:
            active_count = db.session.execute(
                db.select(db.func.count()).select_from(AdminUser).where(AdminUser.is_active.is_(True))
            ).scalar()
            if user.is_active and active_count <= 1:
                raise Fail('Cannot deactivate the last remaining active admin user')

        had_break_glass = password_superadmin_exists(db)
        user.is_active = is_active
        _commit_keeping_break_glass(had_break_glass)
        _emit_users()
        return ok()

    @socketio.on('displayhive:admin:users:cts:delete_user')
    @admin_action('users.delete')
    def handle_delete_user(data):
        """Delete a user. Refuses to delete the last remaining admin account."""
        user = get_or_fail(db, AdminUser, (data or {}).get('id'), 'User')

        total = db.session.execute(
            db.select(db.func.count()).select_from(AdminUser)
        ).scalar()
        if total <= 1:
            raise Fail('Cannot delete the last remaining admin user')

        had_break_glass = password_superadmin_exists(db)
        db.session.delete(user)
        _commit_keeping_break_glass(had_break_glass)
        _emit_users()
        return ok()

    @socketio.on('displayhive:admin:users:cts:impersonate')
    @admin_action('special.impersonate')
    def handle_impersonate(data):
        """Issue an impersonation token: log the caller in as another user, with
        that user's own rights. data: {user_id}.

        Refuses to chain — a session already running under an impersonation
        token cannot start a second one, even if the impersonated user also
        holds special.impersonate (see application.socketio_handlers.auth.is_impersonating).
        """
        from flask import current_app
        from application.auth import begin_impersonation
        actor = current_admin_user()
        token, target, error = begin_impersonation(
            current_app._get_current_object(), db, actor, (data or {}).get('user_id'), is_impersonating())
        if error:
            raise Fail(error)
        logger.info("Admin '%s' started impersonating '%s'", actor.username, target.username)
        return ok(token=token, username=target.username, impersonator_username=actor.username)
