"""
Service layer for subscription management and usage quota enforcement.
"""

import json
import logging
import time
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

import httpx
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ReceiptVerificationError, UsageLimitExceededError
from app.subscriptions.models import PlanType, StorePlatform, SubscriptionStatus
from app.subscriptions.repository import SubscriptionRepository, get_subscription_repository
from app.subscriptions.schemas import (
    SubscriptionRead,
    UsageRead,
    VerifyReceiptRequest,
    VerifyReceiptResponse,
)

logger = logging.getLogger(__name__)

settings = get_settings()

# ═══════════════════════════════════════════════════════════════════════════
# PLAN LIMITS
# ═══════════════════════════════════════════════════════════════════════════

PLAN_LIMITS: Dict[PlanType, Dict[str, int]] = {
    PlanType.FREE: {"sessions": 1, "generations": 1},
    PlanType.STUDENT: {"sessions": 10, "generations": 10},
    PlanType.UNLIMITED: {"sessions": 50, "generations": 50},
}

PRODUCT_TO_PLAN: Dict[str, PlanType] = {
    settings.subscription_student_apple_id: PlanType.STUDENT,
    settings.subscription_unlimited_apple_id: PlanType.UNLIMITED,
    settings.subscription_student_google_id: PlanType.STUDENT,
    settings.subscription_unlimited_google_id: PlanType.UNLIMITED,
}


# ═══════════════════════════════════════════════════════════════════════════
# SERVICE
# ═══════════════════════════════════════════════════════════════════════════


class SubscriptionService:
    def __init__(self, repo: SubscriptionRepository):
        self.repo = repo

    async def get_subscription(self, user_id: str) -> SubscriptionRead:
        """Get subscription details, creating a FREE subscription if none exists."""
        sub = await self.repo.get_subscription(user_id)
        if sub is None:
            sub = await self.repo.upsert_subscription(user_id, PlanType.FREE)
        return SubscriptionRead.model_validate(sub)

    async def get_plan_type(self, user_id: str) -> PlanType:
        """Get the user's effective plan type."""
        sub = await self.repo.get_subscription(user_id)
        if sub is None or not sub.is_active:
            return PlanType.FREE
        return sub.plan_type

    async def verify_receipt(
        self, request: VerifyReceiptRequest, user_id: str
    ) -> VerifyReceiptResponse:
        """Verify an app store receipt and activate the subscription."""
        plan_type = PRODUCT_TO_PLAN.get(request.product_id)
        if plan_type is None:
            raise ReceiptVerificationError(f"Unknown product ID: {request.product_id}")

        try:
            if request.platform == StorePlatform.APPLE:
                receipt_info = await _verify_apple_receipt(request.receipt_data)
            else:
                receipt_info = await _verify_google_receipt(
                    request.receipt_data, request.product_id
                )
        except ReceiptVerificationError:
            raise
        except Exception as e:
            logger.exception(f"Receipt verification failed: {e}")
            raise ReceiptVerificationError("Receipt verification failed")

        sub = await self.repo.upsert_subscription(
            user_id=user_id,
            plan_type=plan_type,
            status=SubscriptionStatus.ACTIVE,
            store_platform=request.platform,
            store_product_id=request.product_id,
            store_transaction_id=receipt_info.get("transaction_id"),
            store_original_transaction_id=receipt_info.get("original_transaction_id"),
            expires_at=receipt_info.get("expires_at"),
            purchased_at=receipt_info.get("purchased_at"),
        )

        return VerifyReceiptResponse(
            success=True,
            subscription=SubscriptionRead.model_validate(sub),
            message=f"Subscription activated: {plan_type.value}",
        )

    async def check_session_quota(self, user_id: str) -> None:
        """Raise UsageLimitExceededError if session quota is exhausted."""
        plan = await self.get_plan_type(user_id)
        limit = PLAN_LIMITS[plan]["sessions"]
        usage = await self.repo.get_or_create_daily_usage(user_id, date.today())
        if usage.sessions_used >= limit:
            raise UsageLimitExceededError(
                f"Daily session limit reached ({limit}/{limit}). Upgrade your plan for more."
            )

    async def check_generation_quota(self, user_id: str) -> None:
        """Raise UsageLimitExceededError if generation quota is exhausted."""
        plan = await self.get_plan_type(user_id)
        limit = PLAN_LIMITS[plan]["generations"]
        usage = await self.repo.get_or_create_daily_usage(user_id, date.today())
        if usage.generations_used >= limit:
            raise UsageLimitExceededError(
                f"Daily generation limit reached ({limit}/{limit}). Upgrade your plan for more."
            )

    async def increment_session_usage(self, user_id: str) -> None:
        """Increment session count after a successful session."""
        await self.repo.increment_sessions(user_id, date.today())

    async def increment_generation_usage(self, user_id: str) -> None:
        """Increment generation count after a successful generation."""
        await self.repo.increment_generations(user_id, date.today())

    async def get_usage(self, user_id: str) -> UsageRead:
        """Get current daily usage with limits and remaining counts."""
        plan = await self.get_plan_type(user_id)
        limits = PLAN_LIMITS[plan]
        usage = await self.repo.get_or_create_daily_usage(user_id, date.today())

        return UsageRead(
            usage_date=usage.usage_date,
            sessions_used=usage.sessions_used,
            sessions_limit=limits["sessions"],
            sessions_remaining=max(0, limits["sessions"] - usage.sessions_used),
            generations_used=usage.generations_used,
            generations_limit=limits["generations"],
            generations_remaining=max(0, limits["generations"] - usage.generations_used),
            plan_type=plan,
        )


# ═══════════════════════════════════════════════════════════════════════════
# STORE VERIFICATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════


async def _verify_apple_receipt(receipt_data: str) -> Dict[str, Any]:
    """
    Verify receipt with Apple App Store Server API v2.
    Uses JWT (ES256) authentication and decodes JWS signed transactions.
    """
    if not all([settings.apple_key_id, settings.apple_issuer_id, settings.apple_private_key]):
        raise ReceiptVerificationError("Apple App Store credentials not configured")

    # Build JWT for App Store Server API authentication
    now = int(time.time())
    payload = {
        "iss": settings.apple_issuer_id,
        "iat": now,
        "exp": now + 300,
        "aud": "appstoreconnect-v1",
        "bid": settings.apple_bundle_id,
    }
    headers = {
        "alg": "ES256",
        "kid": settings.apple_key_id,
        "typ": "JWT",
    }
    token = jwt.encode(payload, settings.apple_private_key, algorithm="ES256", headers=headers)

    # Look up transaction
    url = f"https://api.storekit.itunes.apple.com/inApps/v1/transactions/{receipt_data}"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )

    if response.status_code != 200:
        logger.error(f"Apple API error: {response.status_code} - {response.text}")
        raise ReceiptVerificationError("Apple receipt verification failed")

    data = response.json()
    # Decode the JWS signed transaction (header.payload.signature)
    signed_transaction = data.get("signedTransactionInfo", "")
    try:
        # Decode without verification for now — in production, verify Apple's x5c chain
        transaction = jwt.decode(
            signed_transaction,
            options={"verify_signature": False},
            algorithms=["ES256"],
        )
    except Exception as e:
        logger.error(f"Failed to decode Apple JWS transaction: {e}")
        raise ReceiptVerificationError("Failed to decode Apple transaction")

    expires_ms = transaction.get("expiresDate")
    purchased_ms = transaction.get("purchaseDate")

    return {
        "transaction_id": transaction.get("transactionId"),
        "original_transaction_id": transaction.get("originalTransactionId"),
        "expires_at": (
            datetime.fromtimestamp(expires_ms / 1000, tz=timezone.utc) if expires_ms else None
        ),
        "purchased_at": (
            datetime.fromtimestamp(purchased_ms / 1000, tz=timezone.utc)
            if purchased_ms
            else None
        ),
    }


async def _verify_google_receipt(
    purchase_token: str, product_id: str
) -> Dict[str, Any]:
    """
    Verify receipt with Google Play Developer API v3.
    Uses service account authentication.
    """
    if not settings.google_service_account_json or not settings.google_play_package_name:
        raise ReceiptVerificationError("Google Play credentials not configured")

    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request

        creds_info = json.loads(settings.google_service_account_json)
        credentials = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/androidpublisher"],
        )
        credentials.refresh(Request())
        access_token = credentials.token
    except Exception as e:
        logger.error(f"Google auth failed: {e}")
        raise ReceiptVerificationError("Google Play authentication failed")

    url = (
        f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
        f"{settings.google_play_package_name}/purchases/subscriptions/"
        f"{product_id}/tokens/{purchase_token}"
    )

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15.0,
        )

    if response.status_code != 200:
        logger.error(f"Google API error: {response.status_code} - {response.text}")
        raise ReceiptVerificationError("Google Play receipt verification failed")

    data = response.json()
    expires_ms = int(data.get("expiryTimeMillis", 0))
    start_ms = int(data.get("startTimeMillis", 0))

    return {
        "transaction_id": data.get("orderId"),
        "original_transaction_id": data.get("orderId"),
        "expires_at": (
            datetime.fromtimestamp(expires_ms / 1000, tz=timezone.utc) if expires_ms else None
        ),
        "purchased_at": (
            datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc) if start_ms else None
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════
# FACTORY
# ═══════════════════════════════════════════════════════════════════════════


def get_subscription_service(db: AsyncSession) -> SubscriptionService:
    repo = get_subscription_repository(db)
    return SubscriptionService(repo)
