"""
SQLAlchemy models for topics module.
Defines the Topic table structure.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.analysis.models import Session
    from app.auth.models import User


class Topic(Base):
    """
    Topic model representing a learning subject.
    Contains a title and has many sessions.
    Belongs to a user.
    """

    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Foreign key to User (nullable for backward compatibility)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,  # Nullable to support existing topics without users
        index=True,
    )

    # Relationship to user
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="topics",
    )

    # Relationship to sessions
    sessions: Mapped[List["Session"]] = relationship(
        "Session",
        back_populates="topic",
        cascade="all, delete-orphan",
        order_by="Session.date.desc()",
    )

    def __repr__(self) -> str:
        return f"<Topic(id={self.id}, title={self.title}, user_id={self.user_id})>"

    @property
    def session_count(self) -> int:
        """Get the number of sessions for this topic."""
        return len(self.sessions) if self.sessions else 0