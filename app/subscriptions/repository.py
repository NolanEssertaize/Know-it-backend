"""
Repository layer for subscription and usage data access.
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid7 import uuid7

from app.subscriptions.models import (
    DailyUsage,
    PlanType,
    StorePlatform,
    SubscriptionStatus,
    UserSubscription,
)


class SubscriptionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_subscription(self, user_id: str) -> Optional[UserSubscription]:
        """Get a user's subscription or None."""
        result = await self.db.execute(
            select(UserSubscription).where(UserSubscription.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert_subscription(
        self,
        user_id: str,
        plan_type: PlanType,
        status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
        store_platform: Optional[StorePlatform] = None,
        store_product_id: Optional[str] = None,
        store_transaction_id: Optional[str] = None,
        store_original_transaction_id: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        purchased_at: Optional[datetime] = None,
    ) -> UserSubscription:
        """Create or update a user's subscription."""
        sub = await self.get_subscription(user_id)
        now = datetime.now(timezone.utc)

        if sub is None:
            sub = UserSubscription(
                id=str(uuid7()),
                user_id=user_id,
                plan_type=plan_type,
                status=status,
                store_platform=store_platform,
                store_product_id=store_product_id,
                store_transaction_id=store_transaction_id,
                store_original_transaction_id=store_original_transaction_id,
                expires_at=expires_at,
                purchased_at=purchased_at,
                created_at=now,
                updated_at=now,
            )
            self.db.add(sub)
        else:
            sub.plan_type = plan_type
            sub.status = status
            sub.store_platform = store_platform
            sub.store_product_id = store_product_id
            sub.store_transaction_id = store_transaction_id
            sub.store_original_transaction_id = store_original_transaction_id
            sub.expires_at = expires_at
            sub.purchased_at = purchased_at
            sub.updated_at = now

        await self.db.flush()
        return sub

    async def get_or_create_daily_usage(
        self, user_id: str, usage_date: date
    ) -> DailyUsage:
        """Get today's usage row or create one with zeros."""
        result = await self.db.execute(
            select(DailyUsage).where(
                DailyUsage.user_id == user_id,
                DailyUsage.usage_date == usage_date,
            )
        )
        usage = result.scalar_one_or_none()

        if usage is None:
            now = datetime.now(timezone.utc)
            usage = DailyUsage(
                id=str(uuid7()),
                user_id=user_id,
                usage_date=usage_date,
                sessions_used=0,
                generations_used=0,
                created_at=now,
                updated_at=now,
            )
            self.db.add(usage)
            await self.db.flush()

        return usage

    async def increment_sessions(self, user_id: str, usage_date: date) -> DailyUsage:
        """Increment sessions_used by 1."""
        usage = await self.get_or_create_daily_usage(user_id, usage_date)
        usage.sessions_used += 1
        usage.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return usage

    async def increment_generations(self, user_id: str, usage_date: date) -> DailyUsage:
        """Increment generations_used by 1."""
        usage = await self.get_or_create_daily_usage(user_id, usage_date)
        usage.generations_used += 1
        usage.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return usage


def get_subscription_repository(db: AsyncSession) -> SubscriptionRepository:
    return SubscriptionRepository(db)
