"""In-app contextual help content.

Content lives here (DB) instead of hardcoded in the frontend, addressable by
a stable `key` (e.g. "page.devices") so it can be looked up per-page or
per-field. `HelpTranslation` is split out per `locale` so adding a language
later is just adding rows — no schema change.
"""

from sqlalchemy import String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import db


class HelpTopic(db.Model):
    """One addressable piece of in-app help (a page, a field, ...)."""
    __tablename__ = 'help_topic'
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # 'page' | 'field' — what kind of UI element this help attaches to.
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    # Feature/module this topic belongs to, e.g. 'devices', 'pretalx'.
    context: Mapped[str] = mapped_column(String(100), nullable=False)
    # Optional "Learn more" link into the mkdocs user guide.
    docs_url: Mapped[str] = mapped_column(String(500), nullable=True)

    translations: Mapped[list["HelpTranslation"]] = relationship(
        "HelpTranslation", back_populates="topic", cascade="all, delete-orphan"
    )


class HelpTranslation(db.Model):
    """The title/body of one HelpTopic in one locale."""
    __tablename__ = 'help_translation'
    __table_args__ = (
        UniqueConstraint('topic_id', 'locale', name='uq_help_translation_topic_locale'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey('help_topic.id'), nullable=False, index=True)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    topic: Mapped["HelpTopic"] = relationship("HelpTopic", back_populates="translations")
