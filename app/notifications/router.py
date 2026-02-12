"""
Notifications router — API endpoints for push token registration
and notification preference management.
"""

import logging

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentActiveUser
from app.notifications.schemas import (
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
    PushTokenRegister,
    PushTokenResponse,
)
from app.notifications.service import get_notification_service
from app.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ═══════════════════════════════════════════════════════════════════════════
# PUSH TOKEN MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════


@router.put(
    "/push-token",
    response_model=PushTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Register or update a push token",
    description="Register the current device's Expo push token. Call this on every app launch.",
    responses={
        200: {"model": PushTokenResponse, "description": "Token registered"},
        401: {"description": "Not authenticated"},
    },
)
@limiter.limit("30/minute")
async def register_push_token(
        request: Request,
        body: PushTokenRegister,
        current_user: CurrentActiveUser,
        db: AsyncSession = Depends(get_db),
) -> PushTokenResponse:
    """Register or update a push token for the authenticated user's device."""
    logger.info(f"[NotifRouter] Push token registration for user: {current_user.id}")

    service = get_notification_service(db)
    return await service.register_token(current_user.id, body)


@router.delete(
    "/push-token",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unregister a push token",
    description="Remove a push token on logout or when notifications are disabled.",
    responses={
        204: {"description": "Token removed"},
        401: {"description": "Not authenticated"},
    },
)
@limiter.limit("30/minute")
async def unregister_push_token(
        request: Request,
        body: PushTokenRegister,
        current_user: CurrentActiveUser,
        db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a push token for the authenticated user."""
    logger.info(f"[NotifRouter] Push token removal for user: {current_user.id}")

    service = get_notification_service(db)
    await service.unregister_token(current_user.id, body.token)


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATION SETTINGS
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/settings",
    response_model=NotificationSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get notification settings",
    description="Get the current user's notification preferences.",
    responses={
        200: {"model": NotificationSettingsResponse, "description": "Current settings"},
        401: {"description": "Not authenticated"},
    },
)
async def get_notification_settings(
        current_user: CurrentActiveUser,
        db: AsyncSession = Depends(get_db),
) -> NotificationSettingsResponse:
    """Get notification settings for the authenticated user."""
    service = get_notification_service(db)
    return await service.get_settings(current_user.id)


@router.put(
    "/settings",
    response_model=NotificationSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Update notification settings",
    description="Update notification preferences (timezone, enable/disable notification types).",
    responses={
        200: {"model": NotificationSettingsResponse, "description": "Updated settings"},
        401: {"description": "Not authenticated"},
        422: {"description": "Invalid timezone"},
    },
)
@limiter.limit("20/minute")
async def update_notification_settings(
        request: Request,
        body: NotificationSettingsUpdate,
        current_user: CurrentActiveUser,
        db: AsyncSession = Depends(get_db),
) -> NotificationSettingsResponse:
    """Update notification settings for the authenticated user."""
    logger.info(f"[NotifRouter] Settings update for user: {current_user.id}")

    service = get_notification_service(db)
    return await service.update_settings(current_user.id, body)
