"""The Pretalx plugin's tables: the API addresses, their cached answers and the plugin-wide settings.

These tables were created in the core by older versions of DisplayHive (their migrations are in the core's history)
and keep their names; the plugin adopts them (``adopts_tables`` in plugin.json). The classes are built once per
process (see application/plugins/orm.py).
"""

from datetime import datetime
from types import SimpleNamespace
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from application.plugins import orm

KEY = 'displayhive.pretalx'


def _build(db):
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
        api_url_id: Mapped[int] = mapped_column(Integer, ForeignKey('pretalx_api_url.id', ondelete='CASCADE'))
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

    return SimpleNamespace(PretalxApiUrl=PretalxApiUrl, PretalxApiCache=PretalxApiCache, PretalxSettings=PretalxSettings)


def load_models():
    """``PretalxApiUrl``, ``PretalxApiCache`` and ``PretalxSettings`` (the same classes every time)."""
    return orm.once(KEY, _build)
