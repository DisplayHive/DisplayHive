"""Socket handlers for SSO login providers (Settings page → Login providers)."""

import logging
import urllib.parse

logger = logging.getLogger(__name__)


def _validate_issuer(issuer: str) -> str | None:
    """Return an error message if *issuer* isn't an acceptable issuer URL."""
    parsed = urllib.parse.urlparse(issuer)
    if not parsed.netloc or parsed.query or parsed.fragment:
        return 'Issuer must be a URL like https://login.example.com/realms/main'
    # Plain http only for a provider on this machine (local testing): over a
    # network it would expose the authorization code and client secret.
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1')):
        return 'Issuer must use https://'
    return None


def register_admin_authprovider_handlers(socketio, app, db):
    """Register list/save/delete/test handlers for AuthProvider rows."""
    from application.socketio_handlers.actions import admin_action, get_or_fail, Fail, ok
    from application.models import AuthProvider, AdminUserIdentity
    from application import oidc

    def _providers_payload():
        providers = db.session.execute(db.select(AuthProvider).order_by(AuthProvider.name)).scalars().all()
        return ok(
            providers=[p.to_dict() for p in providers],
            # The base of the redirect URI to register at a provider (None: use the browser's origin).
            public_url=app.config.get('PUBLIC_URL'),
        )

    @socketio.on('displayhive:admin:authproviders:cts:get_providers')
    @admin_action('authproviders.manage')
    def handle_get_providers(data=None):
        return _providers_payload()

    @socketio.on('displayhive:admin:authproviders:cts:save_provider')
    @admin_action('authproviders.manage')
    def handle_save_provider(data):
        """Create or update a provider.

        data: {id?, slug (create only), name, issuer, client_id,
        client_secret? (empty = keep current), clear_client_secret?, scopes, enabled}
        """
        data = data or {}
        provider_id = data.get('id')
        name = str(data.get('name', '')).strip()
        issuer = str(data.get('issuer', '')).strip()
        client_id = str(data.get('client_id', '')).strip()
        # 'openid' is what makes the provider return an ID token at all.
        scopes = [s for s in str(data.get('scopes', '')).split() if s]
        if 'openid' not in scopes:
            scopes.insert(0, 'openid')

        if not name:
            raise Fail('Name is required')
        if not client_id:
            raise Fail('Client ID is required')
        issuer_error = _validate_issuer(issuer)
        if issuer_error:
            raise Fail(issuer_error)

        if provider_id:
            provider = get_or_fail(db, AuthProvider, provider_id, 'Provider')
        else:
            # The slug is part of the redirect URI registered at the provider,
            # so it's fixed once created.
            slug = str(data.get('slug', '')).strip().lower()
            if not oidc.SLUG_RE.match(slug):
                raise Fail('Identifier may only contain a-z, 0-9 and "-" (max. 64)')
            if db.session.execute(db.select(AuthProvider.id).where(AuthProvider.slug == slug)).first():
                raise Fail('A provider with this identifier already exists')
            provider = AuthProvider(slug=slug)
            db.session.add(provider)

        provider.name = name
        provider.issuer = issuer
        provider.client_id = client_id
        provider.scopes = ' '.join(scopes)
        provider.enabled = bool(data.get('enabled', True))
        secret = str(data.get('client_secret') or '')
        if secret:
            provider.client_secret = secret
        elif data.get('clear_client_secret'):
            provider.client_secret = None

        db.session.commit()
        result = _providers_payload()
        result['id'] = provider.id
        return result

    @socketio.on('displayhive:admin:authproviders:cts:delete_provider')
    @admin_action('authproviders.manage')
    def handle_delete_provider(data):
        """Delete a provider. Linked identities stay (they're keyed by issuer),
        so re-adding a provider for the same issuer restores those logins."""
        provider = get_or_fail(db, AuthProvider, (data or {}).get('id'), 'Provider')
        # SQLite doesn't enforce the FK's ON DELETE SET NULL here.
        db.session.execute(
            db.update(AdminUserIdentity).where(AdminUserIdentity.provider_id == provider.id).values(provider_id=None)
        )
        db.session.delete(provider)
        db.session.commit()
        return _providers_payload()

    @socketio.on('displayhive:admin:authproviders:cts:test_provider')
    @admin_action('authproviders.manage')
    def handle_test_provider(data):
        """Fetch an issuer's discovery document, to check it before saving. data: {issuer}."""
        issuer = str((data or {}).get('issuer', '')).strip()
        issuer_error = _validate_issuer(issuer)
        if issuer_error:
            raise Fail(issuer_error)
        try:
            doc = oidc.discover(issuer, force=True)
        except oidc.OidcError as e:
            raise Fail(str(e))
        return ok(
            issuer=doc['issuer'],
            authorization_endpoint=doc['authorization_endpoint'],
            pkce='S256' in (doc.get('code_challenge_methods_supported') or []),
        )
