"""User-rights system: groups, subgroups, right definitions, and per-user overrides.

See application/permissions.py for the resolution algorithm (effective group
closure, allow/deny/inherit precedence, superadmin bypass) that consumes
these tables. Kept deliberately data-only here; no business logic.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import db


class RightDefinition(db.Model):
    """A single checkable right, e.g. ``media.upload``.

    The catalog of rows here is kept in sync with the ``RIGHTS`` list in
    application/permissions.py on every startup (see sync_right_definitions),
    so that list is the actual source of truth — this table exists so groups
    and users can hold a stable foreign key to a right, and so the admin UI
    can list/group rights without hardcoding them a second time.
    """
    __tablename__ = 'right_definition'

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)

    def __repr__(self):
        return f"<RightDefinition {self.key}>"


class Group(db.Model):
    """A group of users that can be granted rights (allow-only) and nested via subgroups.

    A subgroup's effective rights include everything granted to its
    ancestors — see effective_group_closure() in application/permissions.py.
    """
    __tablename__ = 'group'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    parent_group_id: Mapped[Optional[int]] = mapped_column(ForeignKey('group.id'), nullable=True, index=True)
    # The single well-known "always allow everything" group. Exactly one such
    # group is expected to exist (seeded on first run); it cannot be deleted
    # and its is_superadmin flag cannot be unset via the admin UI.
    is_superadmin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='0')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    parent: Mapped[Optional["Group"]] = relationship("Group", remote_side=[id], back_populates="children")
    children: Mapped[list["Group"]] = relationship("Group", back_populates="parent")

    def __repr__(self):
        return f"<Group {self.name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'parent_group_id': self.parent_group_id,
            'is_superadmin': self.is_superadmin,
        }


class GroupRight(db.Model):
    """A right granted to a group. Presence of a row means "allow" — groups
    cannot express deny or inherit, only additive allow grants."""
    __tablename__ = 'group_right'

    group_id: Mapped[int] = mapped_column(ForeignKey('group.id', ondelete='CASCADE'), primary_key=True)
    right_id: Mapped[int] = mapped_column(ForeignKey('right_definition.id', ondelete='CASCADE'), primary_key=True)


class UserGroup(db.Model):
    """Membership of an AdminUser in a Group. Many-to-many."""
    __tablename__ = 'user_group'

    user_id: Mapped[int] = mapped_column(ForeignKey('admin_user.id', ondelete='CASCADE'), primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey('group.id', ondelete='CASCADE'), primary_key=True)


class UserRight(db.Model):
    """A per-user override for a single right: 'allow' or 'deny'.

    Sparse by design — a user with no row for a right simply inherits the
    group-resolved value. 'inherit' is therefore represented by the absence
    of a row rather than a stored value; the admin UI presents it as a
    third state by deleting the row when the operator picks "inherit".
    """
    __tablename__ = 'user_right'
    __table_args__ = (
        UniqueConstraint('user_id', 'right_id', name='uq_user_right_user_id_right_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('admin_user.id', ondelete='CASCADE'), nullable=False, index=True)
    right_id: Mapped[int] = mapped_column(ForeignKey('right_definition.id', ondelete='CASCADE'), nullable=False)
    # 'allow' or 'deny'. Validated in application/permissions.py, not at the DB layer.
    value: Mapped[str] = mapped_column(String(10), nullable=False)
