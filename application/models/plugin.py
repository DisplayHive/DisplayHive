from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import db


class Plugin(db.Model):
    """The state of one plugin on this instance: which are switched on, and where they came from.

    The code itself is in ``plugins/`` (bundled with the application) or ``DATA_DIR/plugins``
    (installed); this row only records the decision. See application/plugins/loader.py.
    """
    __tablename__ = 'plugin'

    id: Mapped[str] = mapped_column(String(100), primary_key=True)          # e.g. displayhive.countdown
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default='bundled')   # bundled | installed
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')   # last plugin migration that ran
    installed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
