"""Content-related database models."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Table, Column, Integer, Float, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import db, content_element_screengroup

# Many-to-many association table for Layout and ContentContainer
layout_container = Table(
    'layout_container',
    db.Model.metadata,
    Column('layout_id', Integer, ForeignKey('layout.id'), primary_key=True),
    Column('contentcontainer_id', Integer, ForeignKey('contentcontainer.id'), primary_key=True),
)


class ContentElement(db.Model):
    """Content element model for displaying on screens.

    A ContentElement has no direct container reference: its Contenttype
    defines one field (TagConfig) per container it targets, so a single
    ContentElement's field values fan out to every container its
    Contenttype's fields are mapped to.
    """
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
    # Relationship to Contenttype
    contenttype: Mapped["Contenttype"] = relationship("Contenttype", back_populates="content_elements")
    # many-to-many: a ContentElement can be assigned to many Screengroups
    screengroups: Mapped[list["Screengroup"]] = relationship("Screengroup", secondary="content_element_screengroup", back_populates="content_elements")


class Design(db.Model):
    """Design model: global screen skin (HTML/CSS). Exactly one is active instance-wide."""
    __tablename__ = 'design'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    html: Mapped[str] = mapped_column(Text)
    css: Mapped[str] = mapped_column(Text, nullable=True)
    isDefault: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)


class Layout(db.Model):
    """A named, reusable group of positioned ContentContainers.

    Purely an admin-side organizational concept: it groups containers and
    scopes which containers a Contenttype's handlers may target. It has no
    runtime "screen uses this Layout" meaning.
    """
    __tablename__ = 'layout'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    # Many-to-many relationship to ContentContainer
    contentcontainers: Mapped[list["ContentContainer"]] = relationship("ContentContainer", secondary=layout_container, back_populates="layouts")
    # Contenttypes scoped to this Layout
    contenttypes: Mapped[list["Contenttype"]] = relationship("Contenttype", back_populates="layout")


class ContentContainer(db.Model):
    """A standalone content container: a screen-relative position (vh/vw) and size,
    rendered as an absolutely-positioned overlay. Reusable across multiple Layouts."""
    __tablename__ = 'contentcontainer'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))  # Display/reference name (e.g., 'maincontent', 'sidebar')
    order: Mapped[int] = mapped_column(Integer, default=0)  # Display order in admin lists
    title: Mapped[str] = mapped_column(String(255), nullable=True)  # Container title/description
    # Position/size on screen, in viewport-relative units.
    top: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # vh
    left: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # vw
    width: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)  # vw
    height: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)  # vh
    # Fallback content shown when no active scene's field currently targets
    # this container. Reuses the same field_handler transform as TagConfig
    # (textklein, image, pretalx_table, etc); null field_handler means no
    # default is configured and the container just stays blank as before.
    default_field_handler: Mapped[str] = mapped_column(String(50), nullable=True)
    default_content: Mapped[str] = mapped_column(Text, nullable=True)
    # Many-to-many relationship to Layout
    layouts: Mapped[list["Layout"]] = relationship("Layout", secondary=layout_container, back_populates="contentcontainers")


class Contenttype(db.Model):
    """Content type model defining how content is structured.

    Bound to exactly one Layout. Each ContentContainer the Contenttype uses
    is itself one field (TagConfig) with an assigned field_handler — there is
    no separate render template: a field's transformed value directly becomes
    its target container's rendered content.
    """
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    layout_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('layout.id'), nullable=True)
    layout: Mapped["Layout"] = relationship("Layout", back_populates="contenttypes")
    # Relationship to ContentElement
    content_elements: Mapped[list["ContentElement"]] = relationship("ContentElement", back_populates="contenttype")
    # Relationship to TagConfig (fields; one per container this contenttype uses)
    tagconfigs: Mapped[list["TagConfig"]] = relationship("TagConfig", back_populates="contenttype", cascade="all, delete-orphan")


class TagConfig(db.Model):
    """A field belonging to a Contenttype, targeting one of its containers.

    Reuses the existing field_handler types (textklein, image, pretalx_table,
    etc). The field's transformed value becomes the rendered content of
    contentcontainer_id, which must be one of the containers in the
    Contenttype's Layout.
    """
    __tablename__ = 'tagconfig'
    id: Mapped[int] = mapped_column(primary_key=True)
    contenttype_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('contenttype.id'), nullable=True)
    contentcontainer_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('contentcontainer.id'), nullable=True)
    field_name: Mapped[str] = mapped_column(String(255))  # e.g., 'title', 'text', 'image_url'
    field_handler: Mapped[str] = mapped_column(String(50))   # e.g., 'text', 'textarea', 'number', 'url'
    field_label: Mapped[str] = mapped_column(String(255), nullable=True)  # Display label
    required: Mapped[bool] = mapped_column(db.Boolean, default=False)
    default_value: Mapped[str] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)  # Display order
    # Relationship to Contenttype
    contenttype: Mapped["Contenttype"] = relationship("Contenttype", back_populates="tagconfigs")
    contentcontainer: Mapped["ContentContainer"] = relationship("ContentContainer")


class MagicTagValueList(db.Model):
    """A named list of key/value entries a 'list'-type MagicTag can draw from."""
    __tablename__ = 'magic_tag_value_list'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    entries: Mapped[list["MagicTagValueListEntry"]] = relationship(
        "MagicTagValueListEntry", back_populates="value_list", cascade="all, delete-orphan"
    )


class MagicTagValueListEntry(db.Model):
    """A single key/value entry belonging to a MagicTagValueList."""
    __tablename__ = 'magic_tag_value_list_entry'
    id: Mapped[int] = mapped_column(primary_key=True)
    value_list_id: Mapped[int] = mapped_column(Integer, ForeignKey('magic_tag_value_list.id'), nullable=False)
    key: Mapped[str] = mapped_column(String(255))
    value: Mapped[str] = mapped_column(Text)
    value_list: Mapped["MagicTagValueList"] = relationship("MagicTagValueList", back_populates="entries")


class MagicTag(db.Model):
    """Global magic tag injected into templates and other content.

    A 'text' tag renders `value` literally. A 'list' tag renders the value
    of the entry in `value_list` whose key matches `value`.
    """
    __tablename__ = 'magic_tag'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    value: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, nullable=True, default='')
    type: Mapped[str] = mapped_column(String(20), nullable=False, default='text', server_default='text')
    value_list_id: Mapped[int] = mapped_column(Integer, ForeignKey('magic_tag_value_list.id'), nullable=True, default=None)
    value_list: Mapped["MagicTagValueList"] = relationship("MagicTagValueList", foreign_keys=[value_list_id])


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

