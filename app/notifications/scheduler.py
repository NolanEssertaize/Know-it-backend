"""
Notification scheduler — runs cron jobs that check which users
should receive push notifications based on their local time.

Jobs:
  1. Evening practice reminder  — fires when user's local time is ~20:00
  2. Morning flashcard reminder — fires when user's local time is ~08:00

Both run every 15 minutes to cover all timezone offsets (some are +XX:30 / +XX:45).
"""

import logging
import zoneinfo
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.models import Session
from app.database import AsyncSessionLocal
from app.flashcards.models import Flashcard
from app.notifications.models import NotificationType
from app.notifications.repository import NotificationSettingsRepository
from app.notifications.service import NotificationService
from app.topics.models import Topic

logger = logging.getLogger(__name__)


def _local_hour(utc_now: datetime, tz_name: str) -> int:
    """Get the current hour (0-23) in a given timezone."""
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
        return utc_now.astimezone(tz).hour
    except (KeyError, Exception):
        return utc_now.hour  # fallback to UTC


async def _get_today_topic_titles(db: AsyncSession, user_id: str) -> list[str]:
    """Get titles of topics the user studied today (UTC day)."""
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(
        tzinfo=timezone.utc
    )
    stmt = (
        select(Topic.title)
        .join(Session, Session.topic_id == Topic.id)
        .where(Topic.user_id == user_id)
        .where(Session.date >= today_start)
        .distinct()
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def _count_due_cards(db: AsyncSession, user_id: str) -> int:
    """Count flashcards that are due for review right now."""
    now = datetime.now(timezone.utc)
    stmt = (
        select(func.count())
        .select_from(Flashcard)
        .where(Flashcard.user_id == user_id)
        .where(Flashcard.next_review_at <= now)
    )
    result = await db.execute(stmt)
    return result.scalar_one()


async def run_evening_practice_reminder() -> None:
    """
    Send evening practice reminders to users whose local time is 20:xx.
    Only sent if the user studied at least one topic today.
    """
    logger.info("[Scheduler] Running evening practice reminder job")
    utc_now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        try:
            settings_repo = NotificationSettingsRepository(db)
            all_settings = await settings_repo.get_users_with_enabled(
                NotificationType.EVENING_PRACTICE
            )

            notif_service = NotificationService(db)
            sent_count = 0

            for user_settings in all_settings:
                local_hour = _local_hour(utc_now, user_settings.timezone)
                if local_hour != 20:
                    continue

                topic_titles = await _get_today_topic_titles(db, user_settings.user_id)
                if not topic_titles:
                    continue

                # Build message
                if len(topic_titles) == 1:
                    body = f'You studied "{topic_titles[0]}" today — ready to practice?'
                else:
                    joined = ", ".join(topic_titles[:3])
                    body = f"You studied {joined} today — ready to practice?"

                success = await notif_service.send_to_user(
                    user_id=user_settings.user_id,
                    notification_type=NotificationType.EVENING_PRACTICE,
                    title="Time to practice!",
                    body=body,
                    data={"type": "evening_practice"},
                )
                if success:
                    sent_count += 1

            await db.commit()
            logger.info(
                f"[Scheduler] Evening reminder done — sent to {sent_count} user(s)"
            )

        except Exception:
            await db.rollback()
            logger.exception("[Scheduler] Evening reminder job failed")


async def run_morning_flashcard_reminder() -> None:
    """
    Send morning flashcard reminders to users whose local time is 08:xx
    and who have cards due for review.
    """
    logger.info("[Scheduler] Running morning flashcard reminder job")
    utc_now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        try:
            settings_repo = NotificationSettingsRepository(db)
            all_settings = await settings_repo.get_users_with_enabled(
                NotificationType.MORNING_FLASHCARDS
            )

            notif_service = NotificationService(db)
            sent_count = 0

            for user_settings in all_settings:
                local_hour = _local_hour(utc_now, user_settings.timezone)
                if local_hour != 8:
                    continue

                due_count = await _count_due_cards(db, user_settings.user_id)
                if due_count == 0:
                    continue

                # Build message
                if due_count == 1:
                    body = "You have 1 flashcard ready for review!"
                else:
                    body = f"You have {due_count} flashcards ready for review!"

                success = await notif_service.send_to_user(
                    user_id=user_settings.user_id,
                    notification_type=NotificationType.MORNING_FLASHCARDS,
                    title="Flashcards waiting for you",
                    body=body,
                    data={"type": "morning_flashcards", "due_count": due_count},
                )
                if success:
                    sent_count += 1

            await db.commit()
            logger.info(
                f"[Scheduler] Morning flashcard reminder done — sent to {sent_count} user(s)"
            )

        except Exception:
            await db.rollback()
            logger.exception("[Scheduler] Morning flashcard reminder job failed")
