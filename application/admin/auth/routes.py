"""HTTP routes for admin authentication: password and SSO (OIDC) login, session check.

Mounted under /admin/api/auth/* so they stay inside the same URL prefix an
operator's reverse-proxy (htaccess, nginx, ...) already protects, in addition
to the JWT check performed here. Also provides `require_jwt_auth`, the
decorator used to protect the existing export/import routes in app.py.
"""

import json
import logging
import urllib.parse
from functools import wraps

from flask import request, jsonify, redirect

from application import version
from application.auth import (
    verify_password,
    hash_password,
    password_problem,
    create_token,
    user_from_token,
    decode_token,
    begin_login_attempt,
    finish_login_attempt,
)

logger = logging.getLogger(__name__)


def require_jwt_auth(app, allow_pending_password_change=False):
    """Return a decorator that requires a valid `Authorization: Bearer <jwt>` header.

    *allow_pending_password_change* lets an account flagged
    `must_change_password` through — only for the self-service routes it
    needs to see and clear that flag (see user_from_token).
    """
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            token = auth_header[7:] if auth_header.startswith('Bearer ') else None
            # Re-validate the account on every request: a token stays
            # cryptographically valid for its full TTL, so reject it here if the
            # user has since been deleted, deactivated, or changed their password.
            from application.models import db
            if not user_from_token(app, db, token, allow_pending_password_change=allow_pending_password_change):
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

    # Self-service preference keys settable via PATCH /admin/api/auth/me/preferences.
    # Same allowlist convention as ALLOWED_SETTING_KEYS in the admin Settings
    # socket handlers: an explicit set, not "anything the client sends".
    ALLOWED_PREFERENCE_KEYS = {'theme'}
    ALLOWED_THEME_VALUES = {'light', 'dark', 'system'}

    def _record_login(user):
        """Stamp last_login_at and add a login-history row (password or SSO)."""
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

    @app.route('/admin/api/auth/login', methods=['POST'])
    def admin_auth_login():
        """Authenticate a username/password pair and return a JWT."""
        data = request.get_json(silent=True) or {}
        username = str(data.get('username', '')).strip()
        password = str(data.get('password', ''))

        if not username or not password:
            return jsonify({'success': False, 'error': 'Username and password are required'}), 400

        # Counted as a failure up front, taken back on success — see
        # begin_login_attempt() for why (parallel guesses).
        attempt = begin_login_attempt(request.remote_addr, username)
        if attempt is None:
            return jsonify({'success': False, 'error': 'Too many failed attempts. Try again shortly.'}), 429

        user = db.session.execute(
            db.select(AdminUser).where(AdminUser.username == username)
        ).scalar_one_or_none()

        # Accounts without password login (e.g. created by an SSO login) get
        # the same answer as a wrong password, so this doesn't reveal them.
        if not user or not user.password_login_allowed or not verify_password(password, user.password_hash):
            return jsonify({'success': False, 'error': 'Invalid username or password'}), 401

        if not user.is_active:
            return jsonify({'success': False, 'error': 'This account has been deactivated'}), 403

        finish_login_attempt(attempt, success=True)
        _record_login(user)
        db.session.commit()

        token = create_token(app, user)
        return jsonify({
            'success': True,
            'token': token,
            'username': user.username,
            'preferences': user.get_preferences(),
            'must_change_password': bool(user.must_change_password),
        })

    @app.route('/admin/api/auth/me', methods=['GET'])
    @require_jwt_auth(app, allow_pending_password_change=True)
    def admin_auth_me():
        """Validate the current token and return the associated username + preferences.

        Used by the SPA on load to confirm a stored token is still valid
        (e.g. the user hasn't been deleted) before restoring the session.
        """
        auth_header = request.headers.get('Authorization', '')
        token = auth_header[7:] if auth_header.startswith('Bearer ') else None

        user = user_from_token(app, db, token, allow_pending_password_change=True)
        if not user:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        # An impersonation session is never asked to change the impersonated
        # account's password (see user_from_token).
        payload = decode_token(app, token) or {}
        return jsonify({
            'success': True,
            'username': user.username,
            'preferences': user.get_preferences(),
            **version.info(),
            'must_change_password': (bool(user.must_change_password)
                                     and 'imp' not in payload and payload.get('am') != 'oidc'),
        })

    @app.route('/admin/api/auth/me/password', methods=['POST'])
    @require_jwt_auth(app, allow_pending_password_change=True)
    def admin_auth_change_password():
        """Change the caller's own password. data: {current_password, new_password}.

        Self-service, and the only thing an account flagged
        `must_change_password` can do. Clears that flag and bumps
        token_version (revoking every other session), then returns a fresh
        token so the caller's own session carries on.
        """
        auth_header = request.headers.get('Authorization', '')
        token = auth_header[7:] if auth_header.startswith('Bearer ') else None
        user = user_from_token(app, db, token, allow_pending_password_change=True)
        if not user:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        if 'imp' in (decode_token(app, token) or {}):
            return jsonify({'success': False, 'error': "Cannot change another user's password while impersonating"}), 403

        data = request.get_json(silent=True) or {}
        current_password = str(data.get('current_password', ''))
        new_password = str(data.get('new_password', ''))

        # Same limiter as the login route: the current-password check is
        # otherwise a brute-force oracle for anyone holding a stolen token.
        attempt = begin_login_attempt(request.remote_addr, user.username)
        if attempt is None:
            return jsonify({'success': False, 'error': 'Too many failed attempts. Try again shortly.'}), 429
        if not verify_password(current_password, user.password_hash):
            return jsonify({'success': False, 'error': 'Current password is incorrect'}), 400
        finish_login_attempt(attempt, success=True)

        if password_problem(new_password):
            return jsonify({'success': False, 'error': password_problem(new_password)}), 400
        if verify_password(new_password, user.password_hash):
            return jsonify({'success': False, 'error': 'New password must differ from the current one'}), 400

        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        user.token_version = (user.token_version or 0) + 1
        db.session.commit()

        return jsonify({'success': True, 'token': create_token(app, user), 'username': user.username})

    @app.route('/admin/api/auth/me/preferences', methods=['PATCH'])
    @require_jwt_auth(app)
    def admin_auth_set_preferences():
        """Upsert one or more of the caller's own preferences (e.g. {"theme": "dark"}).

        Self-service only — a user can set their own preferences, nothing lets
        one admin set another's. Unknown keys/values are rejected rather than
        silently dropped, since this is a small explicit allowlist, not a
        general-purpose settings blob.
        """
        auth_header = request.headers.get('Authorization', '')
        token = auth_header[7:] if auth_header.startswith('Bearer ') else None
        user = user_from_token(app, db, token)
        if not user:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        data = request.get_json(silent=True) or {}
        updates = data.get('preferences', {})
        if not isinstance(updates, dict) or not updates:
            return jsonify({'success': False, 'error': 'No preferences provided'}), 400

        for key, value in updates.items():
            if key not in ALLOWED_PREFERENCE_KEYS:
                return jsonify({'success': False, 'error': f'Unknown preference: {key}'}), 400
            if key == 'theme' and value not in ALLOWED_THEME_VALUES:
                return jsonify({'success': False, 'error': f'Invalid theme: {value}'}), 400

        preferences = user.get_preferences()
        preferences.update(updates)
        user.preferences = json.dumps(preferences)
        db.session.commit()

        return jsonify({'success': True, 'preferences': preferences})

    # --- SSO (OpenID Connect) -------------------------------------------------
    # See application/oidc.py for the flow. These routes stay under
    # /admin/api/auth/ like the password login, so a reverse proxy protecting
    # that prefix covers them too.
    from application.models import AuthProvider
    from application import oidc

    OIDC_COOKIE = 'dh_oidc'
    OIDC_COOKIE_PATH = '/admin/api/auth/oidc'

    def _oidc_redirect_uri(provider):
        # PUBLIC_URL when configured: the redirect URI then no longer depends
        # on the request's Host header. Otherwise host_url, which honours
        # X-Forwarded-Proto/Host when TRUSTED_PROXY_COUNT is set (ProxyFix in
        # the app factory). The Settings page shows admins this same URI to
        # register at the provider.
        base = app.config.get('PUBLIC_URL') or request.host_url.rstrip('/')
        return base + f'/admin/api/auth/oidc/{provider.slug}/callback'

    def _back_to_admin(**fragment):
        # Fragment, not query: browsers never send it to any server, so the
        # handoff code doesn't end up in proxy access logs.
        response = redirect('/admin/#' + urllib.parse.urlencode(fragment))
        response.delete_cookie(OIDC_COOKIE, path=OIDC_COOKIE_PATH)
        return response

    @app.route('/admin/api/auth/providers', methods=['GET'])
    def admin_auth_providers():
        """Enabled SSO providers for the login page's buttons. Public: names only."""
        providers = db.session.execute(
            db.select(AuthProvider).where(AuthProvider.enabled.is_(True)).order_by(AuthProvider.name)
        ).scalars().all()
        return jsonify({'providers': [{'slug': p.slug, 'name': p.name} for p in providers]})

    @app.route('/admin/api/auth/oidc/<slug>/start', methods=['GET'])
    def admin_auth_oidc_start(slug):
        """Send the browser to *slug*'s provider to log in."""
        provider = db.session.execute(
            db.select(AuthProvider).where(AuthProvider.slug == slug, AuthProvider.enabled.is_(True))
        ).scalar_one_or_none()
        if not provider:
            return _back_to_admin(oidc_error='This login provider is not available.')
        try:
            url, browser_binding = oidc.begin_login(provider, _oidc_redirect_uri(provider))
        except oidc.OidcError as e:
            logger.warning("SSO login via '%s' could not start: %s", provider.name, e)
            return _back_to_admin(oidc_error=f'{provider.name} is currently unavailable.')
        response = redirect(url)
        # SameSite=Lax still sends it on the provider's top-level redirect back.
        response.set_cookie(
            OIDC_COOKIE, browser_binding, max_age=oidc.PENDING_TTL_SECONDS, path=OIDC_COOKIE_PATH,
            httponly=True, secure=request.is_secure, samesite='Lax',
        )
        return response

    @app.route('/admin/api/auth/oidc/<slug>/callback', methods=['GET'])
    def admin_auth_oidc_callback(slug):
        """The provider's redirect back: finish the login, hand the SPA a one-time code."""
        try:
            pending = oidc.take_pending(request.args.get('state', ''), request.cookies.get(OIDC_COOKIE))
            provider = db.session.get(AuthProvider, pending.provider_id)
            if not provider or provider.slug != slug or not provider.enabled:
                raise oidc.OidcError('This login provider is no longer available.')
            if request.args.get('error'):
                logger.info("SSO login via '%s' ended at the provider: %s %s", provider.name,
                            request.args.get('error'), request.args.get('error_description', ''))
                raise oidc.OidcError(f'The login at {provider.name} was cancelled or denied.')
            code = request.args.get('code')
            if not code:
                raise oidc.OidcError(f'{provider.name} did not return a login code.')

            claims = oidc.exchange_code(provider, pending, code)
            user = oidc.resolve_user(db, provider, claims)
            if not user.is_active:
                raise oidc.OidcError('This account has been deactivated')
            _record_login(user)
            db.session.commit()
        except oidc.OidcError as e:
            db.session.rollback()
            return _back_to_admin(oidc_error=str(e))
        except Exception:
            db.session.rollback()
            logger.exception("SSO login via '%s' failed", slug)
            return _back_to_admin(oidc_error='The login failed unexpectedly. Please try again.')

        return _back_to_admin(oidc_code=oidc.create_handoff(user.id))

    @app.route('/admin/api/auth/oidc/exchange', methods=['POST'])
    def admin_auth_oidc_exchange():
        """Swap a handoff code from the callback for a session token. data: {code}."""
        data = request.get_json(silent=True) or {}
        user_id = oidc.redeem_handoff(str(data.get('code', '')))
        user = db.session.get(AdminUser, user_id) if user_id else None
        if not user or not user.is_active:
            return jsonify({'success': False, 'error': 'This login has expired. Please log in again.'}), 401
        return jsonify({
            'success': True,
            'token': create_token(app, user, auth_method='oidc'),
            'username': user.username,
            'preferences': user.get_preferences(),
            'must_change_password': False,
        })
