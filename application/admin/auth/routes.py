"""HTTP routes for admin authentication: login + session check.

Mounted under /admin/api/auth/* so they stay inside the same URL prefix an
operator's reverse-proxy (htaccess, nginx, ...) already protects, in addition
to the JWT check performed here. Also provides `require_jwt_auth`, the
decorator used to protect the existing export/import routes in app.py.
"""

from functools import wraps

from flask import request, jsonify

from application.auth import (
    verify_password,
    create_token,
    user_from_token,
    is_rate_limited,
    record_failed_attempt,
    clear_failed_attempts,
)


def require_jwt_auth(app):
    """Return a decorator that requires a valid `Authorization: Bearer <jwt>` header."""
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            token = auth_header[7:] if auth_header.startswith('Bearer ') else None
            # Re-validate the account on every request: a token stays
            # cryptographically valid for its full TTL, so reject it here if the
            # user has since been deleted, deactivated, or changed their password.
            from application.models import db
            if not user_from_token(app, db, token):
                return jsonify({'success': False, 'error': 'Unauthorized'}), 401
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def require_http_right(app, right_key):
    """Return a decorator requiring both a valid JWT and *right_key*.

    Stack this under `@require_jwt_auth(app)` on Flask routes that need a
    specific right, not just any authenticated admin — e.g. the database
    import/export routes in app.py. Fails closed: missing/invalid token or
    missing right both return 401.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            token = auth_header[7:] if auth_header.startswith('Bearer ') else None
            from application.models import db
            from application.permissions import has_right
            user = user_from_token(app, db, token)
            if not user or not has_right(db, user, right_key):
                return jsonify({'success': False, 'error': 'Unauthorized'}), 401
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def register_auth_routes(app, db):
    """Register the login and session-check HTTP routes."""
    from application.models import AdminUser, AdminUserLogin
    from datetime import datetime, timezone

    @app.route('/admin/api/auth/login', methods=['POST'])
    def admin_auth_login():
        """Authenticate a username/password pair and return a JWT."""
        data = request.get_json(silent=True) or {}
        username = str(data.get('username', '')).strip()
        password = str(data.get('password', ''))

        rate_key = f'{request.remote_addr}:{username.lower()}'
        if is_rate_limited(rate_key):
            return jsonify({'success': False, 'error': 'Too many failed attempts. Try again shortly.'}), 429

        if not username or not password:
            return jsonify({'success': False, 'error': 'Username and password are required'}), 400

        user = db.session.execute(
            db.select(AdminUser).where(AdminUser.username == username)
        ).scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            record_failed_attempt(rate_key)
            return jsonify({'success': False, 'error': 'Invalid username or password'}), 401

        if not user.is_active:
            record_failed_attempt(rate_key)
            return jsonify({'success': False, 'error': 'This account has been deactivated'}), 403

        clear_failed_attempts(rate_key)
        user.last_login_at = datetime.now(timezone.utc)
        db.session.add(AdminUserLogin(
            user_id=user.id,
            logged_in_at=user.last_login_at,
            ip_address=request.remote_addr,
        ))

        # Cap storage at the 50 most recent logins per user.
        keep_ids = db.session.execute(
            db.select(AdminUserLogin.id)
            .where(AdminUserLogin.user_id == user.id)
            .order_by(AdminUserLogin.logged_in_at.desc())
            .limit(50)
        ).scalars().all()
        db.session.execute(
            db.delete(AdminUserLogin).where(
                AdminUserLogin.user_id == user.id,
                AdminUserLogin.id.not_in(keep_ids),
            )
        )

        db.session.commit()

        token = create_token(app, user)
        return jsonify({'success': True, 'token': token, 'username': user.username})

    @app.route('/admin/api/auth/me', methods=['GET'])
    @require_jwt_auth(app)
    def admin_auth_me():
        """Validate the current token and return the associated username.

        Used by the SPA on load to confirm a stored token is still valid
        (e.g. the user hasn't been deleted) before restoring the session.
        """
        auth_header = request.headers.get('Authorization', '')
        token = auth_header[7:] if auth_header.startswith('Bearer ') else None

        user = user_from_token(app, db, token)
        if not user:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        return jsonify({'success': True, 'username': user.username})
