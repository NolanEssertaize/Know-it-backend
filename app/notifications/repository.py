"""
Notifications repository — Data Access Layer for push tokens,
notification settings, and notification logs.
"""

import logging
from datetime import date, datetime, timezone
from typing import Optional, Sequence
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.models import (
    NotificationLog,
    NotificationStatus,
    NotificationType,
    UserNotificationSettings,
    UserPushToken,
)
from app.notifications.schemas import NotificationSettingsUpdate, PushTokenRegister

logger = logging.getLogger(__name__)


class PushTokenRepository:
    """Repository for user push token operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert(self, user_id: str, data: PushTokenRegister) -> UserPushToken:
        """
        Register a push token. If the token already exists (same device),
        update ownership and reactivate it.
        """
        # Check if token already exists
        stmt = select(UserPushToken).where(UserPushToken.token == data.token)
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.user_id = user_id
            existing.platform = data.platform
            existing.is_active = True
            existing.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
            logger.info(f"[PushTokenRepo] Updated token for user: {user_id}")
            return existing

        token = UserPushToken(
            id=str(uuid4()),
            user_id=user_id,
            token=data.token,
            platform=data.platform,
        )
        self.db.add(token)
        await self.db.flush()
        logger.info(f"[PushTokenRepo] Registered new token for user: {user_id}")
        return token

    async def deactivate_token(self, token: str) -> None:
        """Mark a token as inactive (e.g. after Expo returns DeviceNotRegistered)."""
        stmt = (
            update(UserPushToken)
            .where(UserPushToken.token == token)
            .values(is_active=False, updated_at=datetime.now(timezone.utc))
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def delete_by_token(self, user_id: str, token: str) -> None:
        """Remove a specific push token for a user (logout / unregister)."""
        stmt = (
            delete(UserPushToken)
            .where(UserPushToken.user_id == user_id)
            .where(UserPushToken.token == token)
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def get_active_tokens_for_user(self, user_id: str) -> Sequence[UserPushToken]:
        """Get all active push tokens for a user."""
        stmt = (
            select(UserPushToken)
            .where(UserPushToken.user_id == user_id)
            .where(UserPushToken.is_active == True)  # noqa: E712
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_all_active_tokens_by_user(self) -> Sequence[UserPushToken]:
        """Get all active tokens grouped for batch sending."""
        stmt = (
            select(UserPushToken)
            .where(UserPushToken.is_active == True)  # noqa: E712
            .order_by(UserPushToken.user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()


class NotificationSettingsRepository:
    """Repository for user notification preferences."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(self, user_id: str) -> Optional[UserNotificationSettings]:
        """Get notification settings for a user."""
        stmt = select(UserNotificationSettings).where(
            UserNotificationSettings.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: str) -> UserNotificationSettings:
        """Get existing settings or create defaults."""
        settings = await self.get_by_user_id(user_id)
        if settings:
            return settings

        settings = UserNotificationSettings(
            id=str(uuid4()),
            user_id=user_id,
        )
        self.db.add(settings)
        await self.db.flush()
        logger.info(f"[NotifSettingsRepo] Created default settings for user: {user_id}")
        return settings

    async def update(
        self, user_id: str, data: NotificationSettingsUpdate
    ) -> UserNotificationSettings:
        """Update notification settings for a user. Creates defaults if none exist."""
        settings = await self.get_or_create(user_id)

        if data.timezone is not None:
            settings.timezone = data.timezone
        if data.evening_reminder_enabled is not None:
            settings.evening_reminder_enabled = data.evening_reminder_enabled
        if data.morning_flashcard_enabled is not None:
            settings.morning_flashcard_enabled = data.morning_flashcard_enabled

        settings.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        logger.info(f"[NotifSettingsRepo] Updated settings for user: {user_id}")
        return settings

    async def get_users_with_enabled(
        self, notification_type: NotificationType
    ) -> Sequence[UserNotificationSettings]:
        """Get all settings where a specific notification type is enabled."""
        if notification_type == NotificationType.EVENING_PRACTICE:
            condition = UserNotificationSettings.evening_reminder_enabled == True  # noqa: E712
        else:
            condition = UserNotificationSettings.morning_flashcard_enabled == True  # noqa: E712

        stmt = select(UserNotificationSettings).where(condition)
        result = await self.db.execute(stmt)
        return result.scalars().all()


class NotificationLogRepository:
    """Repository for notification send logs (dedup + analytics)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        user_id: str,
        notification_type: NotificationType,
        status: NotificationStatus,
        error_message: Optional[str] = None,
    ) -> NotificationLog:
        """Record a notification send attempt."""
        entry = NotificationLog(
            id=str(uuid4()),
            user_id=user_id,
            notification_type=notification_type,
            status=status,
            error_message=error_message,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def was_sent_today(
        self, user_id: str, notification_type: NotificationType
    ) -> bool:
        """Check if a notification of this type was already sent to the user today (UTC)."""
        today_start = datetime.combine(date.today(), datetime.min.time()).replace(
            tzinfo=timezone.utc
        )
        stmt = (
            select(func.count())
            .select_from(NotificationLog)
            .where(NotificationLog.user_id == user_id)
            .where(NotificationLog.notification_type == notification_type)
            .where(NotificationLog.status == NotificationStatus.SENT)
            .where(NotificationLog.sent_at >= today_start)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one() > 0
