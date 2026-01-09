"""
Pydantic schemas for authentication module.
DTOs for user registration, login, and token responses.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.auth.models import AuthProvider


# ═══════════════════════════════════════════════════════════════════════════
# USER SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(UserBase):
    """Schema for user login."""
    password: str


class UserRead(UserBase):
    """Schema for reading user data (response)."""
    id: str
    full_name: Optional[str] = None
    picture_url: Optional[str] = None
    auth_provider: AuthProvider
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    full_name: Optional[str] = Field(None, max_length=255)
    picture_url: Optional[str] = Field(None, max_length=500)


class PasswordChange(BaseModel):
    """Schema for password change."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


# ═══════════════════════════════════════════════════════════════════════════
# TOKEN SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class Token(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenRefresh(BaseModel):
    """Schema for token refresh request."""
    refresh_token: str


class TokenPayload(BaseModel):
    """Schema for JWT token payload."""
    sub: str  # user_id
    exp: datetime
    type: str  # "access" or "refresh"


# ═══════════════════════════════════════════════════════════════════════════
# OAUTH SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class GoogleAuthRequest(BaseModel):
    """Schema for Google OAuth callback."""
    code: str  # Authorization code from Google
    redirect_uri: str


class GoogleTokenRequest(BaseModel):
    """Schema for Google ID token authentication (mobile)."""
    id_token: str  # ID token from Google Sign-In


class OAuthUserInfo(BaseModel):
    """Schema for OAuth user info from provider."""
    email: EmailStr
    google_id: str
    full_name: Optional[str] = None
    picture_url: Optional[str] = None
    email_verified: bool = False


# ═══════════════════════════════════════════════════════════════════════════
# RESPONSE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class AuthResponse(BaseModel):
    """Schema for authentication response."""
    user: UserRead
    tokens: Token


class MessageResponse(BaseModel):
    """Schema for simple message responses."""
    message: str


class AuthError(BaseModel):
    """Schema for authentication errors."""
    error: str
    code: str