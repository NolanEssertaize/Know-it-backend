"""
SQLAlchemy models for topics module.
Defines the Topic table structure.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.analysis.models import Session


class Topic(Base):
    """
    Topic model representing a learning subject.
    Contains a title and has many sessions.
    """

    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship to sessions
    sessions: Mapped[List["Session"]] = relationship(
        "Session",
        back_populates="topic",
        cascade="all, delete-orphan",
        order_by="Session.date.desc()",
    )

    def __repr__(self) -> str:
        return f"<Topic(id={self.id}, title={self.title})>"

    @property
    def session_count(self) -> int:
        """Get the number of sessions for this topic."""
        return len(self.sessions) if self.sessions else 0
