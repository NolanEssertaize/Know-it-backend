"""
Authentication router - API endpoints for user authentication.
Supports local (email/password) and Google OAuth authentication.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.rate_limit import limiter

from app.dependencies import CurrentUser, CurrentActiveUser
from app.auth.schemas import (
    AuthError,
    AuthResponse,
    GoogleAuthRequest,
    GoogleTokenRequest,
    MessageResponse,
    PasswordChange,
    Token,
    TokenRefresh,
    UserCreate,
    UserLogin,
    UserRead,
    UserUpdate,
)
from app.auth.service import AuthService, get_auth_service
from app.core.exceptions import (
    AuthenticationError,
    InvalidTokenError,
    OAuthError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ═══════════════════════════════════════════════════════════════════════════
# LOCAL AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════════════


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password.",
    responses={
        201: {"model": AuthResponse, "description": "User registered successfully"},
        400: {"model": AuthError, "description": "Invalid input"},
        409: {"model": AuthError, "description": "Email already registered"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit("10/minute")
async def register(
        request: Request,
        user_data: UserCreate,
        db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Register a new user with email and password.

    Password requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    """
    logger.info(f"[AuthRouter] Registration request: {user_data.email}")

    try:
        auth_service = get_auth_service(db)
        return await auth_service.register(user_data)

    except UserAlreadyExistsError as e:
        logger.warning(f"[AuthRouter] Registration failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": str(e), "code": "USER_EXISTS"},
        )


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Login with email and password",
    description="Authenticate user with email and password credentials.",
    responses={
        200: {"model": AuthResponse, "description": "Login successful"},
        401: {"model": AuthError, "description": "Invalid credentials"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit("10/minute")
async def login(
        request: Request,
        credentials: UserLogin,
        db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Login with email and password.

    Returns access and refresh tokens on successful authentication.
    """
    logger.info(f"[AuthRouter] Login request: {credentials.email}")

    try:
        auth_service = get_auth_service(db)
        return await auth_service.login(credentials)

    except AuthenticationError as e:
        logger.warning(f"[AuthRouter] Login failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": str(e), "code": "AUTH_FAILED"},
        )


@router.post(
    "/refresh",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Get new access and refresh tokens using a valid refresh token.",
    responses={
        200: {"model": Token, "description": "Tokens refreshed"},
        401: {"model": AuthError, "description": "Invalid refresh token"},
    },
)
async def refresh_token(
        token_data: TokenRefresh,
        db: AsyncSession = Depends(get_db),
) -> Token:
    """
    Refresh access token using refresh token.

    Returns new access and refresh tokens.
    """
    logger.info("[AuthRouter] Token refresh request")

    try:
        auth_service = get_auth_service(db)
        return await auth_service.refresh_tokens(token_data.refresh_token)

    except (InvalidTokenError, UserNotFoundError) as e:
        logger.warning(f"[AuthRouter] Token refresh failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": str(e), "code": "INVALID_TOKEN"},
        )



# ═══════════════════════════════════════════════════════════════════════════
# USER PROFILE
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="Get the currently authenticated user's profile.",
    responses={
        200: {"model": UserRead, "description": "Current user profile"},
        401: {"model": AuthError, "description": "Not authenticated"},
    },
)
async def get_me(current_user: CurrentUser) -> UserRead:
    """
    Get current authenticated user's profile.
    """
    return UserRead.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Update current user",
    description="Update the currently authenticated user's profile.",
    responses={
        200: {"model": UserRead, "description": "Updated user profile"},
        401: {"model": AuthError, "description": "Not authenticated"},
    },
)
async def update_me(
        update_data: UserUpdate,
        current_user: CurrentActiveUser,
        db: AsyncSession = Depends(get_db),
) -> UserRead:
    """
    Update current user's profile.
    """
    from app.auth.repository import UserRepository

    repository = UserRepository(db)
    user = await repository.update_profile(
        current_user.id,
        full_name=update_data.full_name,
        picture_url=update_data.picture_url,
    )

    return UserRead.model_validate(user)


@router.post(
    "/change-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Change password",
    description="Change the current user's password.",
    responses={
        200: {"model": MessageResponse, "description": "Password changed"},
        400: {"model": AuthError, "description": "Invalid current password"},
        401: {"model": AuthError, "description": "Not authenticated"},
    },
)
async def change_password(
        password_data: PasswordChange,
        current_user: CurrentActiveUser,
        db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Change current user's password.

    Requires current password for verification.
    """
    logger.info(f"[AuthRouter] Password change request: {current_user.id}")

    try:
        auth_service = get_auth_service(db)
        await auth_service.change_password(
            current_user.id,
            password_data.current_password,
            password_data.new_password,
        )

        return MessageResponse(message="Password changed successfully")

    except AuthenticationError as e:
        logger.warning(f"[AuthRouter] Password change failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(e), "code": "PASSWORD_CHANGE_FAILED"},
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout",
    description="Logout current user (client should discard tokens).",
    responses={
        200: {"model": MessageResponse, "description": "Logged out"},
    },
)
async def logout(current_user: CurrentUser) -> MessageResponse:
    """
    Logout current user.

    Note: Since we use JWT, the actual token invalidation
    should happen client-side by discarding the tokens.
    For production, consider implementing a token blacklist.
    """
    logger.info(f"[AuthRouter] Logout: {current_user.id}")
    return MessageResponse(message="Successfully logged out")