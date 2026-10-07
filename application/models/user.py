"""Admin user model for the login-protected admin backend."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, Integer, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import db

logger = logging.getLogger(__name__)


class AdminUser(db.Model):
    """An administrator account authenticated via username + password (JWT session)."""
    __tablename__ = 'admin_user'

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Bumped whenever the account's credentials change (e.g. password reset) to
    # invalidate every JWT issued before the change. Embedded in the token as
    # `tv` and compared on each request.
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    # Whether this account may log in with username + password at all. Off for
    # accounts created by an SSO (OIDC) login, which have no password; on for
    # local accounts. permissions.password_superadmin_exists() keeps at least
    # one active Superadmin with it on, as the break-glass path when every
    # identity provider is unreachable.
    password_login_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default='1')
    # Set by an admin (Users page) to force this account to pick a new password
    # before it can do anything else. While set, user_from_token() only accepts
    # this account's tokens on the self-service password-change routes; cleared
    # by POST /admin/api/auth/me/password.
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='0')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # JSON-encoded dict of self-service UI preferences (e.g. {"theme": "dark"}),
    # opaque here — same convention as Design.default_colors etc. Never exposed
    # via the admin Users page, only through the owning user's own /auth/me.
    preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # SSO identities linked to this account (ORM cascade, since SQLite doesn't
    # enforce ON DELETE CASCADE here — see AdminUserIdentity).
    identities = relationship(
        'AdminUserIdentity', back_populates='user', cascade='all, delete-orphan', lazy='selectin',
    )

    def __repr__(self):
        return f"<AdminUser {self.username}>"

    def get_preferences(self) -> dict:
        """Decode `preferences`, tolerating missing/corrupt data."""
        if not self.preferences:
            return {}
        try:
            decoded = json.loads(self.preferences)
            return decoded if isinstance(decoded, dict) else {}
        except (TypeError, ValueError):
            logger.warning("AdminUser %s has corrupt preferences JSON", self.id)
            return {}

    def to_dict(self):
        """Convert to a dict for admin clients. Never includes password_hash."""
        return {
            'id': self.id,
            'username': self.username,
            'is_active': self.is_active,
            'must_change_password': bool(self.must_change_password),
            'password_login_allowed': bool(self.password_login_allowed),
            'has_password': bool(self.password_hash),
            'identities': [i.to_dict() for i in self.identities],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
        }


class AdminUserLogin(db.Model):
    """One successful login by an AdminUser, kept for the Users page's login-history popup."""
    __tablename__ = 'admin_user_login'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('admin_user.id', ondelete='CASCADE'), nullable=False, index=True)
    logged_in_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    def to_dict(self):
        return {
            'logged_in_at': self.logged_in_at.isoformat() if self.logged_in_at else None,
            'ip_address': self.ip_address,
        }


class AuthProvider(db.Model):
    """An OpenID Connect identity provider admins can log in with (Settings page).

    Endpoints are not stored: they are discovered from
    ``<issuer>/.well-known/openid-configuration`` at login time (see
    application/oidc.py), so a provider only needs its issuer and client
    credentials.
    """
    __tablename__ = 'auth_provider'

    id: Mapped[int] = mapped_column(primary_key=True)
    # URL-safe identifier used in the callback path
    # (/admin/api/auth/oidc/<slug>/callback), which has to be registered at the
    # provider — so it can't change after creation.
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)  # login button label
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    client_id: Mapped[str] = mapped_column(String(512), nullable=False)
    # Write-only from the admin UI: never sent back to any client.
    client_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scopes: Mapped[str] = mapped_column(String(512), nullable=False, default='openid profile email', server_default='openid profile email')
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default='1')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        """Admin view. Never includes client_secret, only whether one is set."""
        return {
            'id': self.id,
            'slug': self.slug,
            'name': self.name,
            'issuer': self.issuer,
            'client_id': self.client_id,
            'has_client_secret': bool(self.client_secret),
            'scopes': self.scopes,
            'enabled': self.enabled,
        }


class AdminUserIdentity(db.Model):
    """Links an AdminUser to one SSO identity.

    Keyed by (issuer, subject), as OpenID Connect defines a user's identity —
    not by AuthProvider row, so editing, re-creating or duplicating a
    provider entry for the same issuer keeps every link. Never matched by
    email or username.
    """
    __tablename__ = 'admin_user_identity'
    __table_args__ = (UniqueConstraint('issuer', 'subject', name='uq_admin_user_identity_issuer_subject'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('admin_user.id', ondelete='CASCADE'), nullable=False, index=True)
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    # Last provider entry this identity logged in through — for display only.
    provider_id: Mapped[Optional[int]] = mapped_column(ForeignKey('auth_provider.id', ondelete='SET NULL'), nullable=True)
    # Human-readable label from the ID token (email / preferred_username), for
    # admins telling identities apart. Never used for matching.
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user = relationship('AdminUser', back_populates='identities')
    provider = relationship('AuthProvider', lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'issuer': self.issuer,
            'subject': self.subject,
            'provider_name': self.provider.name if self.provider else None,
            'display_name': self.display_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
        }
