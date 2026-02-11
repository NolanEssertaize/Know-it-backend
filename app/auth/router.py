"""
Authentication router - API endpoints for user authentication.
Supports local (email/password) and Google OAuth authentication.
"""

import json
import logging
import re
from urllib.parse import urlencode, quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.rate_limit import limiter
from app.config import get_settings

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


# ═══════════════════════════════════════════════════════════════════════════
# GOOGLE OAUTH
# ═══════════════════════════════════════════════════════════════════════════


@router.post(
    "/google",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate with Google (web flow)",
    description="Exchange a Google authorization code for user authentication.",
    responses={
        200: {"model": AuthResponse, "description": "Authentication successful"},
        401: {"model": AuthError, "description": "OAuth authentication failed"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit("10/minute")
async def google_auth(
        request: Request,
        auth_data: GoogleAuthRequest,
        db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Authenticate via Google OAuth web flow.

    Accepts an authorization code and redirect_uri, exchanges them
    for user info, then creates or links the user account.
    """
    logger.info("[AuthRouter] Google OAuth web flow request")

    try:
        from app.auth.oauth import GoogleOAuth

        google_oauth = GoogleOAuth()
        oauth_info = await google_oauth.authenticate(
            code=auth_data.code,
            redirect_uri=auth_data.redirect_uri,
        )

        auth_service = get_auth_service(db)
        return await auth_service.authenticate_oauth(oauth_info)

    except OAuthError as e:
        logger.warning(f"[AuthRouter] Google OAuth failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": str(e), "code": "OAUTH_ERROR"},
        )


@router.post(
    "/google/token",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate with Google ID token (mobile flow)",
    description="Verify a Google ID token from mobile Sign-In (Expo) for user authentication.",
    responses={
        200: {"model": AuthResponse, "description": "Authentication successful"},
        401: {"model": AuthError, "description": "OAuth authentication failed"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit("10/minute")
async def google_token_auth(
        request: Request,
        token_data: GoogleTokenRequest,
        db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Authenticate via Google ID token (mobile/Expo flow).

    Accepts a Google ID token from the mobile app, verifies it,
    then creates or links the user account.
    """
    logger.info("[AuthRouter] Google OAuth token flow request")

    try:
        from app.auth.oauth import GoogleOAuth

        google_oauth = GoogleOAuth()
        oauth_info = await google_oauth.authenticate(
            id_token_str=token_data.id_token,
        )

        auth_service = get_auth_service(db)
        return await auth_service.authenticate_oauth(oauth_info)

    except OAuthError as e:
        logger.warning(f"[AuthRouter] Google token auth failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": str(e), "code": "OAUTH_ERROR"},
        )


# ═══════════════════════════════════════════════════════════════════════════
# GOOGLE OAUTH - MOBILE SERVER-SIDE FLOW
# ═══════════════════════════════════════════════════════════════════════════

# Allowed redirect URI schemes for mobile apps
_ALLOWED_SCHEMES = re.compile(r"^(exp|knowit|https)://")


def _validate_redirect_uri(redirect_uri: str) -> bool:
    """Validate that redirect_uri uses a safe scheme."""
    return bool(_ALLOWED_SCHEMES.match(redirect_uri))


@router.get(
    "/google/mobile",
    summary="Start Google OAuth for mobile",
    description="Redirects to Google consent screen. Mobile app opens this in an in-app browser.",
    responses={
        302: {"description": "Redirect to Google OAuth consent screen"},
        400: {"description": "Invalid redirect_uri"},
    },
)
@limiter.limit("10/minute")
async def google_mobile_start(
        request: Request,
        redirect_uri: str = Query(
            ...,
            description="Deep link URL to redirect back to after auth (e.g. exp://192.168.1.236:8081/--/auth)",
        ),
):
    """
    Start the Google OAuth server-side flow for mobile apps.

    The mobile app opens this URL in an in-app browser. The backend
    redirects to Google's consent screen, handles the callback,
    then redirects back to the app's deep link with tokens.
    """
    if not _validate_redirect_uri(redirect_uri):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Invalid redirect_uri scheme. Allowed: exp://, knowit://, https://"},
        )

    settings = get_settings()

    if not settings.google_client_id:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Google OAuth not configured"},
        )

    # Build the callback URL using configured base URL or request's base URL
    base_url = settings.google_oauth_callback_base_url or str(request.base_url).rstrip("/")
    callback_url = base_url + "/api/v1/auth/google/mobile/callback"

    # Build Google OAuth authorization URL
    google_auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": redirect_uri,
    })

    logger.info(f"[AuthRouter] Google mobile OAuth started, callback: {callback_url}")

    return RedirectResponse(url=google_auth_url, status_code=302)


@router.get(
    "/google/mobile/callback",
    summary="Google OAuth callback for mobile",
    description="Handles Google's OAuth callback, exchanges code for tokens, and redirects to the mobile app.",
    responses={
        302: {"description": "Redirect to mobile app with tokens"},
    },
)
async def google_mobile_callback(
        request: Request,
        code: str = Query(None, description="Authorization code from Google"),
        state: str = Query(None, description="Mobile app redirect_uri"),
        error: str = Query(None, description="Error from Google"),
        db: AsyncSession = Depends(get_db),
):
    """
    Handle Google OAuth callback for mobile flow.

    Exchanges the authorization code for user info, creates/finds the user,
    generates JWT tokens, and redirects to the mobile app's deep link.
    """
    # If Google returned an error
    if error:
        logger.warning(f"[AuthRouter] Google OAuth error: {error}")
        if state and _validate_redirect_uri(state):
            return RedirectResponse(
                url=f"{state}?error={quote(error)}",
                status_code=302,
            )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": f"Google OAuth error: {error}"},
        )

    # Validate required params
    if not code or not state:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Missing code or state parameter"},
        )

    redirect_uri = state

    if not _validate_redirect_uri(redirect_uri):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Invalid redirect_uri in state"},
        )

    try:
        from app.auth.oauth import GoogleOAuth

        google_oauth = GoogleOAuth()

        # Build the same callback URL used in the initial redirect
        settings = get_settings()
        base_url = settings.google_oauth_callback_base_url or str(request.base_url).rstrip("/")
        callback_url = base_url + "/api/v1/auth/google/mobile/callback"

        # Exchange code for user info
        oauth_info = await google_oauth.authenticate(
            code=code,
            redirect_uri=callback_url,
        )

        # Create or find user
        auth_service = get_auth_service(db)
        auth_response = await auth_service.authenticate_oauth(oauth_info)

        # Serialize user data
        user_data = auth_response.user.model_dump(mode="json")

        # Redirect to mobile app with tokens
        params = urlencode({
            "access_token": auth_response.tokens.access_token,
            "refresh_token": auth_response.tokens.refresh_token,
            "user": json.dumps(user_data),
        })

        logger.info(f"[AuthRouter] Google mobile OAuth success for: {auth_response.user.email}")

        return RedirectResponse(
            url=f"{redirect_uri}?{params}",
            status_code=302,
        )

    except OAuthError as e:
        logger.warning(f"[AuthRouter] Google mobile OAuth failed: {e}")
        return RedirectResponse(
            url=f"{redirect_uri}?error={quote(str(e))}",
            status_code=302,
        )
    except Exception as e:
        logger.exception(f"[AuthRouter] Google mobile OAuth unexpected error: {e}")
        return RedirectResponse(
            url=f"{redirect_uri}?error={quote('Authentication failed')}",
            status_code=302,
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