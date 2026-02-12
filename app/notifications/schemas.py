"""
Pydantic schemas for the notifications module.
DTOs for push token registration and notification preferences.
"""

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.notifications.models import DevicePlatform


# ═══════════════════════════════════════════════════════════════════════════
# PUSH TOKEN SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class PushTokenRegister(BaseModel):
    """Register or update an Expo push token for the current device."""
    token: str = Field(..., min_length=1, max_length=255)
    platform: DevicePlatform

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        """Expo tokens start with ExponentPushToken[ or are UUIDs."""
        v = v.strip()
        if not v:
            raise ValueError("Push token cannot be empty")
        return v


class PushTokenResponse(BaseModel):
    """Response after registering a push token."""
    token: str
    platform: DevicePlatform
    is_active: bool

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATION SETTINGS SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class NotificationSettingsUpdate(BaseModel):
    """Update notification preferences. All fields optional — only provided fields are updated."""
    timezone: Optional[str] = Field(None, max_length=64)
    evening_reminder_enabled: Optional[bool] = None
    morning_flashcard_enabled: Optional[bool] = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
        """Validate that the timezone string is a valid IANA timezone."""
        if v is None:
            return v
        import zoneinfo
        try:
            zoneinfo.ZoneInfo(v)
        except (KeyError, zoneinfo.ZoneInfoNotFoundError):
            raise ValueError(f"Invalid timezone: {v}")
        return v


class NotificationSettingsResponse(BaseModel):
    """Current notification settings for the user."""
    timezone: str
    evening_reminder_enabled: bool
    morning_flashcard_enabled: bool

    model_config = {"from_attributes": True}
