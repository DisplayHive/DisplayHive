"""Content-related database models."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Table, Column, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import db, content_element_screengroup

# Many-to-many association table for Contenttype and ContentContainer
contenttype_container = Table(
    'contenttype_container',
    db.Model.metadata,
    Column('contenttype_id', Integer, ForeignKey('contenttype.id'), primary_key=True),
    Column('contentcontainer_id', Integer, ForeignKey('contentcontainer.id'), primary_key=True)
)


class ContentElement(db.Model):
    """Content element model for displaying on screens."""
    __tablename__ = 'content_element'
    id: Mapped[int] = mapped_column(primary_key=True)
    active: Mapped[bool]
    title: Mapped[str] = mapped_column(String(255))
    html: Mapped[str]
    duration: Mapped[int]
    # store serialized POST input
    serialized_input: Mapped[str] = mapped_column(Text)
    # Scheduling: optional start/end datetime for time-limited display
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Foreign key to Contenttype
    contenttype_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('contenttype.id'), nullable=True)
    # Content container from default template this content belongs to
    contentcontainer: Mapped[str] = mapped_column(String(255), nullable=True, default='maincontent')
    # Relationship to Contenttype
    contenttype: Mapped["Contenttype"] = relationship("Contenttype", back_populates="content_elements")
    # many-to-many: a ContentElement can be assigned to many Screengroups
    screengroups: Mapped[list["Screengroup"]] = relationship("Screengroup", secondary="content_element_screengroup", back_populates="content_elements")


class Template(db.Model):
    """Template model for screen layout templates."""
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    html: Mapped[str] = mapped_column(Text)
    css: Mapped[str] = mapped_column(Text, nullable=True)
    isDefault: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    # Relationship to ContentContainer (Jinja tags)
    contentcontainers: Mapped[list["ContentContainer"]] = relationship("ContentContainer", back_populates="template", cascade="all, delete-orphan")
    # Screens that have this template set as their override
    screens: Mapped[list["Screen"]] = relationship("Screen", back_populates="template", foreign_keys="Screen.template_id")


class ContentContainer(db.Model):
    """Content container (Jinja tag) extracted from template."""
    __tablename__ = 'contentcontainer'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))  # The Jinja tag name (e.g., 'maincontent', 'sidebar')
    template_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('template.id'))
    order: Mapped[int] = mapped_column(Integer, default=0)  # Display order in template
    title: Mapped[str] = mapped_column(String(255), nullable=True)  # Container title/description
    # Relationship to Template
    template: Mapped["Template"] = relationship("Template", back_populates="contentcontainers")
    # Many-to-many relationship to Contenttype
    contenttypes: Mapped[list["Contenttype"]] = relationship("Contenttype", secondary=contenttype_container, back_populates="contentcontainers")


class Contenttype(db.Model):
    """Content type model defining how content is structured."""
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    html: Mapped[str]
    css: Mapped[str] = mapped_column(Text, nullable=True)
    # Relationship to ContentElement
    content_elements: Mapped[list["ContentElement"]] = relationship("ContentElement", back_populates="contenttype")
    # Many-to-many relationship to ContentContainer
    contentcontainers: Mapped[list["ContentContainer"]] = relationship("ContentContainer", secondary=contenttype_container, back_populates="contenttypes")
    # Relationship to TagConfig
    tagconfigs: Mapped[list["TagConfig"]] = relationship("TagConfig", back_populates="contenttype", cascade="all, delete-orphan")


class TagConfig(db.Model):
    """Configuration field for a content type."""
    __tablename__ = 'tagconfig'
    id: Mapped[int] = mapped_column(primary_key=True)
    contenttype_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('contenttype.id'))
    field_name: Mapped[str] = mapped_column(String(255))  # e.g., 'title', 'text', 'image_url'
    field_handler: Mapped[str] = mapped_column(String(50))   # e.g., 'text', 'textarea', 'number', 'url'
    field_label: Mapped[str] = mapped_column(String(255), nullable=True)  # Display label
    required: Mapped[bool] = mapped_column(db.Boolean, default=False)
    default_value: Mapped[str] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)  # Display order
    # Relationship to Contenttype
    contenttype: Mapped["Contenttype"] = relationship("Contenttype", back_populates="tagconfigs")


class MagicTag(db.Model):
    """Global magic tag (key/value pair) injected into templates and other content."""
    __tablename__ = 'magic_tag'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    value: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, nullable=True, default='')


class SystemSetting(db.Model):
    """Key/value store for system-wide configuration."""
    __tablename__ = 'system_setting'
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=True)


class AlertSubscription(db.Model):
    """Subscription linking a TelegramUser to a specific alert type."""
    __tablename__ = 'alert_subscription'
    __table_args__ = (
        UniqueConstraint('user_id', 'alert_type', name='uq_alert_subscription_user_type'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('telegram_users.id', ondelete='CASCADE'), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)


class TelegramUser(db.Model):
    """Saved Telegram users for alert notifications."""
    __tablename__ = 'telegram_users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


class Media(db.Model):
    """Media model for managing images and videos."""
    __tablename__ = 'media'
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))  # Original filename
    title: Mapped[str] = mapped_column(String(255), nullable=True)  # User-defined title
    tags: Mapped[str] = mapped_column(Text, nullable=True)  # Comma-separated tags
    folder_path: Mapped[str] = mapped_column(String(512), default='')  # Path within media folder (e.g., 'category/subcategory')
    mime_type: Mapped[str] = mapped_column(String(100), nullable=True)  # MIME type (image/jpeg, video/mp4, etc.)
    file_size: Mapped[int] = mapped_column(Integer, nullable=True)  # File size in bytes
    created_at: Mapped[datetime] = mapped_column(DateTime)


class PretalxApiUrl(db.Model):
    """Pretalx API endpoint with polling configuration."""
    __tablename__ = 'pretalx_api_url'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(Text)
    polling_enabled: Mapped[bool] = mapped_column(db.Boolean, default=False)
    polling_interval: Mapped[int] = mapped_column(Integer, default=300)  # seconds
    last_success: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_failure: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_valid: Mapped[Optional[bool]] = mapped_column(db.Boolean, nullable=True)
    cache: Mapped[Optional["PretalxApiCache"]] = relationship(
        "PretalxApiCache", back_populates="api_url", cascade="all, delete-orphan", uselist=False
    )


class PretalxApiCache(db.Model):
    """Cached JSON response for a Pretalx API URL."""
    __tablename__ = 'pretalx_api_cache'
    id: Mapped[int] = mapped_column(primary_key=True)
    api_url_id: Mapped[int] = mapped_column(Integer, ForeignKey('pretalx_api_url.id'))
    cached_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)
    api_url: Mapped["PretalxApiUrl"] = relationship("PretalxApiUrl", back_populates="cache")


class PretalxSettings(db.Model):
    """Single-row table for Pretalx-wide settings."""
    __tablename__ = 'pretalx_settings'
    id: Mapped[int] = mapped_column(primary_key=True)
    time_format: Mapped[str] = mapped_column(String(50), nullable=False, default='HH:mm')
    end_of_day: Mapped[str] = mapped_column(String(5), nullable=False, default='23:59')
    no_session_text: Mapped[str] = mapped_column(String(500), nullable=False, default='No session running')
    coming_up_text: Mapped[str] = mapped_column(String(500), nullable=False, default='Coming up next')
    invalid_data_text: Mapped[str] = mapped_column(String(500), nullable=False, default='Invalid API data')
    sim_datetime: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

