"""
Subscription router - API endpoints for subscription management and usage tracking.
"""

import logging

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ReceiptVerificationError
from app.database import get_db
from app.dependencies import CurrentActiveUser
from app.rate_limit import limiter
from app.subscriptions.schemas import (
    SubscriptionError,
    SubscriptionRead,
    UsageRead,
    VerifyReceiptRequest,
    VerifyReceiptResponse,
)
from app.subscriptions.service import SubscriptionService, get_subscription_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get(
    "",
    response_model=SubscriptionRead,
    status_code=status.HTTP_200_OK,
    summary="Get current subscription",
    description="Get the authenticated user's subscription status. Creates a FREE subscription if none exists.",
    responses={
        200: {"model": SubscriptionRead, "description": "Subscription details"},
        401: {"description": "Not authenticated"},
    },
)
async def get_subscription(
    current_user: CurrentActiveUser,
    db: AsyncSession = Depends(get_db),
) -> SubscriptionRead:
    """Get current subscription status."""
    service = get_subscription_service(db)
    return await service.get_subscription(current_user.id)


@router.post(
    "/verify",
    response_model=VerifyReceiptResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify receipt and activate subscription",
    description="Verify an app store receipt (Apple or Google) and activate the corresponding subscription plan.",
    responses={
        200: {"model": VerifyReceiptResponse, "description": "Verification result"},
        400: {"model": SubscriptionError, "description": "Invalid receipt"},
        401: {"description": "Not authenticated"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit("5/minute")
async def verify_receipt(
    request: Request,
    verify_request: VerifyReceiptRequest,
    current_user: CurrentActiveUser,
    db: AsyncSession = Depends(get_db),
) -> VerifyReceiptResponse:
    """Verify an app store receipt and activate the subscription."""
    logger.info(
        f"[SubscriptionRouter] Verifying receipt for user: {current_user.id}, "
        f"platform: {verify_request.platform}, product: {verify_request.product_id}"
    )

    try:
        service = get_subscription_service(db)
        return await service.verify_receipt(verify_request, current_user.id)
    except ReceiptVerificationError as e:
        logger.warning(f"[SubscriptionRouter] Receipt verification failed: {e.message}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": e.message, "code": "RECEIPT_VERIFICATION_FAILED"},
        )


@router.get(
    "/usage",
    response_model=UsageRead,
    status_code=status.HTTP_200_OK,
    summary="Get daily usage",
    description="Get the authenticated user's daily usage counts and remaining quota.",
    responses={
        200: {"model": UsageRead, "description": "Usage details"},
        401: {"description": "Not authenticated"},
    },
)
async def get_usage(
    current_user: CurrentActiveUser,
    db: AsyncSession = Depends(get_db),
) -> UsageRead:
    """Get daily usage and remaining quota."""
    service = get_subscription_service(db)
    return await service.get_usage(current_user.id)
