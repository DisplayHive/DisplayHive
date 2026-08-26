"""Admin user model for the login-protected admin backend."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .base import db


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
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self):
        return f"<AdminUser {self.username}>"

    def to_dict(self):
        """Convert to a dict for admin clients. Never includes password_hash."""
        return {
            'id': self.id,
            'username': self.username,
            'is_active': self.is_active,
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
