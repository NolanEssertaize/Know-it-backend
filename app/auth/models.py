"""
SQLAlchemy models for authentication module.
Defines the User table structure with OAuth support.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.topics.models import Topic
    from app.flashcards.models import Deck, Flashcard
    from app.subscriptions.models import UserSubscription


class AuthProvider(str, Enum):
    """Authentication provider enum."""
    LOCAL = "local"
    GOOGLE = "google"


class User(Base):
    """
    User model for authentication.
    Supports both local (email/password) and OAuth (Google) authentication.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    hashed_password: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True  # Nullable for OAuth users
    )

    # Profile info
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    picture_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)

    # OAuth fields
    auth_provider: Mapped[AuthProvider] = mapped_column(
        SQLEnum(AuthProvider),
        default=AuthProvider.LOCAL,
        nullable=False,
    )
    google_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True
    )

    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship to topics
    topics: Mapped[List["Topic"]] = relationship(
        "Topic",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Topic.created_at.desc()",
    )

    # Relationship to decks
    decks: Mapped[List["Deck"]] = relationship(
        "Deck",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Deck.created_at.desc()",
    )

    # Relationship to flashcards
    flashcards: Mapped[List["Flashcard"]] = relationship(
        "Flashcard",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Relationship to subscription (one-to-one)
    subscription: Mapped[Optional["UserSubscription"]] = relationship(
        "UserSubscription",
        back_populates="user",
        uselist=False,
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, provider={self.auth_provider})>"

    @property
    def is_oauth_user(self) -> bool:
        """Check if user authenticated via OAuth."""
        return self.auth_provider != AuthProvider.LOCAL


class PasswordResetCode(Base):
    """Stores 6-digit password reset codes with expiry and attempt tracking."""

    __tablename__ = "password_reset_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<PasswordResetCode(id={self.id}, email={self.email}, used={self.is_used})>"