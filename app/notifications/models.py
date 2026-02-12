"""
SQLAlchemy models for the notifications module.
Stores push tokens, notification preferences, and send logs.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DevicePlatform(str, Enum):
    """Mobile device platform."""
    IOS = "ios"
    ANDROID = "android"


class NotificationType(str, Enum):
    """Types of push notifications the system can send."""
    EVENING_PRACTICE = "evening_practice"
    MORNING_FLASHCARDS = "morning_flashcards"


class NotificationStatus(str, Enum):
    """Delivery status of a sent notification."""
    SENT = "sent"
    FAILED = "failed"


class UserPushToken(Base):
    """
    Stores Expo push tokens for each user device.
    A user may have multiple devices (phone + tablet).
    """

    __tablename__ = "user_push_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    platform: Mapped[DevicePlatform] = mapped_column(
        SQLEnum(DevicePlatform), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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
        return f"<UserPushToken(user_id={self.user_id}, platform={self.platform})>"


class UserNotificationSettings(Base):
    """
    Per-user notification preferences.
    One row per user — created on first settings update or token registration.
    """

    __tablename__ = "user_notification_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    evening_reminder_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    morning_flashcard_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
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

    def __repr__(self) -> str:
        return (
            f"<UserNotificationSettings(user_id={self.user_id}, "
            f"tz={self.timezone}, evening={self.evening_reminder_enabled}, "
            f"morning={self.morning_flashcard_enabled})>"
        )


class NotificationLog(Base):
    """
    Tracks every notification sent to prevent duplicate sends
    and enable debugging / analytics.
    """

    __tablename__ = "notification_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        SQLEnum(NotificationType), nullable=False
    )
    status: Mapped[NotificationStatus] = mapped_column(
        SQLEnum(NotificationStatus), nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_notification_logs_user_type_sent", "user_id", "notification_type", "sent_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationLog(user_id={self.user_id}, "
            f"type={self.notification_type}, status={self.status})>"
        )
