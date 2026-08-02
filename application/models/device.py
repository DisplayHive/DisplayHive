"""Device models for authentication and registration."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import db


class Device(db.Model):
    """Device model for authenticated screen clients."""
    __tablename__ = 'device'

    id: Mapped[int] = mapped_column(primary_key=True)
    devicekey: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    registration_token: Mapped[Optional[str]] = mapped_column(String(36), unique=True, nullable=True, index=True)
    find: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_connected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    screen_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('screen.id'), nullable=True, index=True)
    max_resolution_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)
    max_resolution_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)
    screen: Mapped[Optional["Screen"]] = relationship("Screen", back_populates="devices")

    def __repr__(self):
        return f"<Device {self.devicekey}>"

    def to_dict(self):
        """Convert device to dictionary."""
        return {
            'id': self.id,
            'devicekey': self.devicekey,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_connected_at': self.last_connected_at.isoformat() if self.last_connected_at else None,
            'is_online': bool(self.is_online),
            'is_active': self.is_active,
            'screen_id': self.screen_id,
            'find': bool(self.find),
        }
