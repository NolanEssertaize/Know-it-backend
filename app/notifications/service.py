"""
Push notification service — sends notifications via Expo Push API
and manages notification preferences.
"""

import logging
from typing import List, Optional, Sequence

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.models import (
    NotificationStatus,
    NotificationType,
    UserPushToken,
)
from app.notifications.repository import (
    NotificationLogRepository,
    NotificationSettingsRepository,
    PushTokenRepository,
)
from app.notifications.schemas import (
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
    PushTokenRegister,
    PushTokenResponse,
)

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


class PushService:
    """Sends push notifications via the Expo Push API."""

    async def send(
        self,
        tokens: Sequence[str],
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> list[tuple[str, bool]]:
        """
        Send a push notification to one or more Expo push tokens.

        Returns a list of (token, success) tuples.
        """
        if not tokens:
            return []

        messages = [
            {
                "to": token,
                "sound": "default",
                "title": title,
                "body": body,
                **({"data": data} if data else {}),
            }
            for token in tokens
        ]

        results: list[tuple[str, bool]] = []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Expo accepts up to 100 messages per request
                for batch_start in range(0, len(messages), 100):
                    batch = messages[batch_start : batch_start + 100]
                    response = await client.post(
                        EXPO_PUSH_URL,
                        json=batch,
                        headers={
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                        },
                    )

                    if response.status_code != 200:
                        logger.error(
                            f"[PushService] Expo API error: {response.status_code} - {response.text}"
                        )
                        results.extend(
                            (msg["to"], False) for msg in batch
                        )
                        continue

                    response_data = response.json().get("data", [])
                    for msg, ticket in zip(batch, response_data):
                        token_str = msg["to"]
                        if ticket.get("status") == "ok":
                            results.append((token_str, True))
                        else:
                            error_detail = ticket.get("details", {})
                            error_code = error_detail.get("error", "unknown")
                            logger.warning(
                                f"[PushService] Failed to send to {token_str}: {error_code}"
                            )
                            results.append((token_str, False))

        except httpx.TimeoutException:
            logger.error("[PushService] Expo API request timed out")
            results.extend((msg["to"], False) for msg in messages if (msg["to"], True) not in results and (msg["to"], False) not in results)
        except httpx.HTTPError as e:
            logger.error(f"[PushService] HTTP error: {e}")
            results.extend((msg["to"], False) for msg in messages if (msg["to"], True) not in results and (msg["to"], False) not in results)

        return results


class NotificationService:
    """
    High-level notification operations: token management,
    settings, and sending with dedup + logging.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.token_repo = PushTokenRepository(db)
        self.settings_repo = NotificationSettingsRepository(db)
        self.log_repo = NotificationLogRepository(db)
        self.push_service = PushService()

    # ── Token management ──────────────────────────────────────────────

    async def register_token(
        self, user_id: str, data: PushTokenRegister
    ) -> PushTokenResponse:
        """Register or update a device push token."""
        token = await self.token_repo.upsert(user_id, data)
        # Ensure notification settings exist
        await self.settings_repo.get_or_create(user_id)
        return PushTokenResponse.model_validate(token)

    async def unregister_token(self, user_id: str, token: str) -> None:
        """Remove a push token (on logout)."""
        await self.token_repo.delete_by_token(user_id, token)

    # ── Settings management ───────────────────────────────────────────

    async def get_settings(self, user_id: str) -> NotificationSettingsResponse:
        """Get current notification settings (creates defaults if needed)."""
        settings = await self.settings_repo.get_or_create(user_id)
        return NotificationSettingsResponse.model_validate(settings)

    async def update_settings(
        self, user_id: str, data: NotificationSettingsUpdate
    ) -> NotificationSettingsResponse:
        """Update notification preferences."""
        settings = await self.settings_repo.update(user_id, data)
        return NotificationSettingsResponse.model_validate(settings)

    # ── Send with dedup + logging ─────────────────────────────────────

    async def send_to_user(
        self,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> bool:
        """
        Send a notification to all active devices of a user.
        Checks dedup (already sent today?) and logs the result.
        Returns True if at least one device received it.
        """
        # Dedup check
        if await self.log_repo.was_sent_today(user_id, notification_type):
            logger.debug(
                f"[NotificationService] Skipping {notification_type.value} for {user_id} — already sent today"
            )
            return False

        tokens = await self.token_repo.get_active_tokens_for_user(user_id)
        if not tokens:
            return False

        token_strings = [t.token for t in tokens]
        results = await self.push_service.send(token_strings, title, body, data)

        any_success = False
        for token_str, success in results:
            if success:
                any_success = True
            else:
                # Deactivate tokens that Expo rejected
                await self.token_repo.deactivate_token(token_str)

        # Log the result
        await self.log_repo.log(
            user_id=user_id,
            notification_type=notification_type,
            status=NotificationStatus.SENT if any_success else NotificationStatus.FAILED,
            error_message=None if any_success else "All tokens failed",
        )

        return any_success


def get_notification_service(db: AsyncSession) -> NotificationService:
    """Factory function for NotificationService."""
    return NotificationService(db)
