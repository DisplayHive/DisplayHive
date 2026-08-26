"""Socket handlers for the admin Users page (account management, no roles)."""

import logging

from flask import request

logger = logging.getLogger(__name__)


def register_admin_user_handlers(socketio, app, db):
    """Register socket handlers for listing/creating/updating/deleting admin users."""
    from application.socketio_handlers.auth import require_right, admin_handler, current_admin_user, is_impersonating
    from application.models import AdminUser, AdminUserLogin
    from application.auth import hash_password, create_token

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
    @require_right('users.page')
    def handle_get_user_logins(data=None):
        """Return a user's 5 most recent logins, newest first. data: {id}."""
        user_id = (data or {}).get('id')
        if not user_id:
            return {'success': False, 'error': 'Missing id'}

        logins = db.session.execute(
            db.select(AdminUserLogin)
            .where(AdminUserLogin.user_id == user_id)
            .order_by(AdminUserLogin.logged_in_at.desc())
            .limit(5)
        ).scalars().all()
        return {'success': True, 'logins': [{'logged_in_at': l.logged_in_at.isoformat() if l.logged_in_at else None} for l in logins]}

    @socketio.on('displayhive:admin:users:cts:create_user')
    @require_right('users.create')
    def handle_create_user(data):
        """Create a new admin user. data: {username, password}."""
        username = str((data or {}).get('username', '')).strip()
        password = str((data or {}).get('password', ''))

        if not username:
            return {'success': False, 'error': 'Username is required'}
        if len(password) < 8:
            return {'success': False, 'error': 'Password must be at least 8 characters'}

        existing = db.session.execute(
            db.select(AdminUser).where(AdminUser.username == username)
        ).scalar_one_or_none()
        if existing:
            return {'success': False, 'error': 'Username already exists'}

        user = AdminUser(username=username, password_hash=hash_password(password))
        db.session.add(user)
        db.session.commit()

        _emit_users()
        return {'success': True, 'id': user.id}

    @socketio.on('displayhive:admin:users:cts:update_user')
    @admin_handler
    def handle_update_user(data):
        """Update username and/or reset password. data: {id, username?, password?}.

        The two fields are gated by separate rights (users.edit / users.set_password),
        so each requested field is checked independently and silently dropped if the
        caller lacks the right for that specific field — same pattern as
        media.rename/media.tag and device.rename/device.enable.
        """
        from application.permissions import has_right
        caller = current_admin_user()

        user_id = (data or {}).get('id')
        if not user_id:
            return {'success': False, 'error': 'Missing id'}

        user = db.session.get(AdminUser, user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}

        new_username = (data or {}).get('username')
        if new_username is not None and not has_right(db, caller, 'users.edit'):
            new_username = None
        if new_username is not None:
            new_username = str(new_username).strip()
            if not new_username:
                return {'success': False, 'error': 'Username is required'}
            if new_username != user.username:
                existing = db.session.execute(
                    db.select(AdminUser).where(AdminUser.username == new_username)
                ).scalar_one_or_none()
                if existing:
                    return {'success': False, 'error': 'Username already exists'}
                user.username = new_username

        new_password = (data or {}).get('password')
        if new_password and not has_right(db, caller, 'users.set_password'):
            new_password = None
        if new_password:
            if len(new_password) < 8:
                return {'success': False, 'error': 'Password must be at least 8 characters'}
            user.password_hash = hash_password(new_password)
            # Invalidate every JWT issued before this password change.
            user.token_version = (user.token_version or 0) + 1

        db.session.commit()
        _emit_users()
        return {'success': True}

    @socketio.on('displayhive:admin:users:cts:set_active')
    @require_right('users.activate')
    def handle_set_active(data):
        """Activate/deactivate a user. data: {id, is_active}. Refuses to leave zero active admins."""
        user_id = (data or {}).get('id')
        is_active = bool((data or {}).get('is_active'))
        if not user_id:
            return {'success': False, 'error': 'Missing id'}

        user = db.session.get(AdminUser, user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}

        if not is_active:
            active_count = db.session.execute(
                db.select(db.func.count()).select_from(AdminUser).where(AdminUser.is_active.is_(True))
            ).scalar()
            if user.is_active and active_count <= 1:
                return {'success': False, 'error': 'Cannot deactivate the last remaining active admin user'}

        user.is_active = is_active
        db.session.commit()
        _emit_users()
        return {'success': True}

    @socketio.on('displayhive:admin:users:cts:delete_user')
    @require_right('users.delete')
    def handle_delete_user(data):
        """Delete a user. Refuses to delete the last remaining admin account."""
        user_id = (data or {}).get('id')
        if not user_id:
            return {'success': False, 'error': 'Missing id'}

        user = db.session.get(AdminUser, user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}

        total = db.session.execute(
            db.select(db.func.count()).select_from(AdminUser)
        ).scalar()
        if total <= 1:
            return {'success': False, 'error': 'Cannot delete the last remaining admin user'}

        db.session.delete(user)
        db.session.commit()
        _emit_users()
        return {'success': True}

    @socketio.on('displayhive:admin:users:cts:impersonate')
    @require_right('special.impersonate')
    def handle_impersonate(data):
        """Issue an impersonation token: log the caller in as another user, with
        that user's own rights. data: {user_id}.

        Refuses to chain — a session already running under an impersonation
        token cannot start a second one, even if the impersonated user also
        holds special.impersonate (see application.socketio_handlers.auth.is_impersonating).
        """
        if is_impersonating():
            return {'success': False, 'error': 'Cannot impersonate while already impersonating'}

        data = data or {}
        target_id = data.get('user_id')
        if not target_id:
            return {'success': False, 'error': 'Missing user_id'}

        actor = current_admin_user()
        if actor and int(target_id) == actor.id:
            return {'success': False, 'error': 'Cannot impersonate yourself'}

        target = db.session.get(AdminUser, target_id)
        if not target:
            return {'success': False, 'error': 'User not found'}
        if not target.is_active:
            return {'success': False, 'error': 'Cannot impersonate a deactivated user'}

        from flask import current_app
        token = create_token(current_app._get_current_object(), target, impersonator_id=actor.id)
        logger.info("Admin '%s' started impersonating '%s'", actor.username, target.username)
        return {
            'success': True,
            'token': token,
            'username': target.username,
            'impersonator_username': actor.username,
        }
