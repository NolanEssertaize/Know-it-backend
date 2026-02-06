"""
SQLAlchemy models for flashcards module.
Defines Deck and Flashcard tables with SRS fields.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.auth.models import User
    from app.topics.models import Topic


class Deck(Base):
    """
    Deck model representing a collection of flashcards.
    Optionally linked to a topic.
    """

    __tablename__ = "decks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Foreign keys
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="decks",
    )
    topic: Mapped[Optional["Topic"]] = relationship(
        "Topic",
        back_populates="decks",
    )
    flashcards: Mapped[List["Flashcard"]] = relationship(
        "Flashcard",
        back_populates="deck",
        cascade="all, delete-orphan",
        order_by="Flashcard.created_at.asc()",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Deck(id={self.id}, name={self.name}, user_id={self.user_id})>"


class Flashcard(Base):
    """
    Flashcard model with SRS (Spaced Repetition System) fields.
    Uses the "Longevity" algorithm with rigid intervals.
    """

    __tablename__ = "flashcards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    front_content: Mapped[str] = mapped_column(Text, nullable=False)
    back_content: Mapped[str] = mapped_column(Text, nullable=False)

    # Foreign keys
    deck_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("decks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # SRS Fields
    step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_review_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    interval_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    deck: Mapped["Deck"] = relationship(
        "Deck",
        back_populates="flashcards",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="flashcards",
    )

    # Composite index for efficient "due cards" query
    __table_args__ = (
        Index("ix_flashcards_user_next_review", "user_id", "next_review_at"),
    )

    def __repr__(self) -> str:
        return f"<Flashcard(id={self.id}, deck_id={self.deck_id}, step={self.step})>"
