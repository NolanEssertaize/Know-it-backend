"""
Pydantic schemas for subscription and usage endpoints.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.subscriptions.models import PlanType, StorePlatform, SubscriptionStatus


class VerifyReceiptRequest(BaseModel):
    """Request to verify an app store receipt."""
    platform: StorePlatform
    receipt_data: str = Field(..., description="Receipt data or purchase token from the store")
    product_id: str = Field(..., description="Store product ID being purchased")


class SubscriptionRead(BaseModel):
    """Subscription details returned to the client."""
    id: str
    plan_type: PlanType
    status: SubscriptionStatus
    store_platform: Optional[StorePlatform] = None
    store_product_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class VerifyReceiptResponse(BaseModel):
    """Response after receipt verification."""
    success: bool
    subscription: Optional[SubscriptionRead] = None
    message: str


class UsageRead(BaseModel):
    """Daily usage stats with limits."""
    usage_date: date
    sessions_used: int
    sessions_limit: int
    sessions_remaining: int
    generations_used: int
    generations_limit: int
    generations_remaining: int
    plan_type: PlanType


class SubscriptionError(BaseModel):
    """Error response for subscription endpoints."""
    error: str
    code: str
