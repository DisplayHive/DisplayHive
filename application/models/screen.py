"""Screen and screengroup database models."""

from datetime import datetime
from uuid import uuid4
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import db, screengroup_screen, content_element_screengroup


class Screen(db.Model):
    """Screen model representing a physical display connected to the system."""
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid4()))
    active: Mapped[bool]
    lastseen: Mapped[datetime]
    name: Mapped[str]
    resolution_width: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    resolution_height: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    debug: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default='1')
    # a Screen can belong to multiple Screengroups
    screengroups: Mapped[list["Screengroup"]] = relationship("Screengroup", secondary=screengroup_screen, back_populates="screens")
    # log entries for this screen — deleted automatically when screen is removed
    logs: Mapped[list["ScreenLog"]] = relationship("ScreenLog", back_populates="screen", cascade="all, delete-orphan", passive_deletes=True)
    # Devices currently assigned to this screen. No cascade here on purpose:
    # deleting a Screen with devices still assigned is blocked in the admin
    # handler rather than silently orphaning/deleting those Device rows.
    devices: Mapped[list["Device"]] = relationship("Device", back_populates="screen")


class ScreenLog(db.Model):
    """A single log entry emitted by a screen client."""
    __tablename__ = "screen_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screen_id: Mapped[int] = mapped_column(Integer, ForeignKey("screen.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    message: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    function: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    screen: Mapped["Screen"] = relationship("Screen", back_populates="logs")


class Screengroup(db.Model):
    """Group of screens that can be assigned the same content."""
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    is_one_screen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='0')
    # many-to-many: a Screengroup can have many Screens
    screens: Mapped[list["Screen"]] = relationship("Screen", secondary=screengroup_screen, back_populates="screengroups")
    # many-to-many: a Screengroup can have many ContentElements
    content_elements: Mapped[list["ContentElement"]] = relationship("ContentElement", secondary="content_element_screengroup", back_populates="screengroups")
