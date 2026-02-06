"""
Authentication dependencies for FastAPI.
Provides user authentication via JWT tokens.
"""

import logging
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import AuthService, get_auth_service
from app.core.exceptions import InvalidTokenError, UsageLimitExceededError, UserNotFoundError, too_many_requests
from app.database import get_db

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
        credentials: Annotated[
            Optional[HTTPAuthorizationCredentials],
            Depends(security)
        ],
        db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency to get the current authenticated user.

    Extracts JWT from Authorization header and validates it.

    Args:
        credentials: Bearer token from Authorization header
        db: Database session

    Returns:
        Authenticated User entity

    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = get_auth_service(db)

    try:
        # Verify token
        payload = auth_service.verify_token(credentials.credentials, token_type="access")

        # Get user
        user = await auth_service.get_current_user(payload.sub)

        return user

    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_optional(
        credentials: Annotated[
            Optional[HTTPAuthorizationCredentials],
            Depends(security)
        ],
        db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Dependency to optionally get the current authenticated user.

    Returns None if no token provided or token is invalid.
    Useful for endpoints that work with or without authentication.

    Args:
        credentials: Bearer token from Authorization header
        db: Database session

    Returns:
        Authenticated User entity or None
    """
    if not credentials:
        return None

    auth_service = get_auth_service(db)

    try:
        payload = auth_service.verify_token(credentials.credentials, token_type="access")
        user = await auth_service.get_current_user(payload.sub)
        return user
    except (InvalidTokenError, UserNotFoundError):
        return None


async def get_current_active_user(
        current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Dependency to get current user and verify they are active.

    Args:
        current_user: User from get_current_user dependency

    Returns:
        Active User entity

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    return current_user


async def get_current_verified_user(
        current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Dependency to get current user and verify their email is verified.

    Args:
        current_user: User from get_current_active_user dependency

    Returns:
        Verified User entity

    Raises:
        HTTPException: If email is not verified
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email first.",
        )
    return current_user


# Type aliases for cleaner dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]
CurrentVerifiedUser = Annotated[User, Depends(get_current_verified_user)]
OptionalUser = Annotated[Optional[User], Depends(get_current_user_optional)]


async def check_session_quota(
        current_user: Annotated[User, Depends(get_current_active_user)],
        db: AsyncSession = Depends(get_db),
) -> User:
    """Check that the user has not exceeded their daily session quota."""
    from app.subscriptions.service import get_subscription_service

    service = get_subscription_service(db)
    try:
        await service.check_session_quota(current_user.id)
    except UsageLimitExceededError as e:
        raise too_many_requests(detail=e.message)
    return current_user


async def check_generation_quota(
        current_user: Annotated[User, Depends(get_current_active_user)],
        db: AsyncSession = Depends(get_db),
) -> User:
    """Check that the user has not exceeded their daily generation quota."""
    from app.subscriptions.service import get_subscription_service

    service = get_subscription_service(db)
    try:
        await service.check_generation_quota(current_user.id)
    except UsageLimitExceededError as e:
        raise too_many_requests(detail=e.message)
    return current_user


SessionQuotaUser = Annotated[User, Depends(check_session_quota)]
GenerationQuotaUser = Annotated[User, Depends(check_generation_quota)]