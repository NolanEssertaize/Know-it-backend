"""
SQLAlchemy models for subscription and usage tracking.
"""

from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlanType(str, Enum):
    """Subscription plan tiers."""
    FREE = "free"
    STUDENT = "student"
    UNLIMITED = "unlimited"


class StorePlatform(str, Enum):
    """App store platform."""
    APPLE = "apple"
    GOOGLE = "google"


class SubscriptionStatus(str, Enum):
    """Subscription lifecycle status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    GRACE_PERIOD = "grace_period"


class UserSubscription(Base):
    """
    Tracks a user's subscription plan and store purchase details.
    One-to-one relationship with User.
    """

    __tablename__ = "user_subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    plan_type: Mapped[PlanType] = mapped_column(
        SQLEnum(PlanType),
        default=PlanType.FREE,
        nullable=False,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SQLEnum(SubscriptionStatus),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
    )
    store_platform: Mapped[str | None] = mapped_column(
        SQLEnum(StorePlatform),
        nullable=True,
    )
    store_product_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    store_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    store_original_transaction_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    purchased_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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

    # Relationship back to User
    user = relationship("User", back_populates="subscription")

    @property
    def is_active(self) -> bool:
        """Check if the subscription is currently active."""
        if self.plan_type == PlanType.FREE:
            return True
        if self.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.GRACE_PERIOD):
            return False
        if self.expires_at and self.expires_at < datetime.now(timezone.utc):
            return False
        return True

    def __repr__(self) -> str:
        return f"<UserSubscription(user_id={self.user_id}, plan={self.plan_type}, status={self.status})>"


class DailyUsage(Base):
    """
    Tracks daily usage counts per user for quota enforcement.
    One row per user per day.
    """

    __tablename__ = "daily_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "usage_date", name="uq_user_usage_date"),
        Index("ix_user_usage_date", "user_id", "usage_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    sessions_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generations_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
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

    def __repr__(self) -> str:
        return f"<DailyUsage(user_id={self.user_id}, date={self.usage_date}, sessions={self.sessions_used}, gens={self.generations_used})>"
