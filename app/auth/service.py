"""
Authentication service - Business logic for user authentication.
Handles password hashing, JWT tokens, and OAuth flows.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AuthProvider, User
from app.auth.repository import PasswordResetRepository, UserRepository
from app.auth.schemas import (
    AuthResponse,
    OAuthUserInfo,
    ResetTokenResponse,
    Token,
    TokenPayload,
    UserCreate,
    UserLogin,
    UserRead,
)
from app.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    UserAlreadyExistsError,
    UserNotFoundError,
    InvalidTokenError,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = UserRepository(db)
        self.reset_repository = PasswordResetRepository(db)

    # ═══════════════════════════════════════════════════════════════════════
    # PASSWORD OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    # ═══════════════════════════════════════════════════════════════════════
    # JWT TOKEN OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════

    def create_access_token(self, user_id: str) -> Tuple[str, datetime]:
        """
        Create an access token.

        Args:
            user_id: User UUID

        Returns:
            Tuple of (token, expiration datetime)
        """
        expires = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_expire_minutes
        )
        payload = {
            "sub": user_id,
            "exp": expires,
            "type": "access",
        }
        token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        return token, expires

    def create_refresh_token(self, user_id: str) -> Tuple[str, datetime]:
        """
        Create a refresh token.

        Args:
            user_id: User UUID

        Returns:
            Tuple of (token, expiration datetime)
        """
        expires = datetime.now(timezone.utc) + timedelta(
            days=settings.jwt_refresh_expire_days
        )
        payload = {
            "sub": user_id,
            "exp": expires,
            "type": "refresh",
        }
        token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        return token, expires

    def create_tokens(self, user_id: str) -> Token:
        """
        Create both access and refresh tokens.

        Args:
            user_id: User UUID

        Returns:
            Token schema with both tokens
        """
        access_token, access_exp = self.create_access_token(user_id)
        refresh_token, _ = self.create_refresh_token(user_id)

        expires_in = int((access_exp - datetime.now(timezone.utc)).total_seconds())

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
        )

    def verify_token(self, token: str, token_type: str = "access") -> TokenPayload:
        """
        Verify and decode a JWT token.

        Args:
            token: JWT token string
            token_type: Expected token type ("access" or "refresh")

        Returns:
            TokenPayload with decoded data

        Raises:
            InvalidTokenError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )

            if payload.get("type") != token_type:
                raise InvalidTokenError(f"Invalid token type. Expected {token_type}")

            return TokenPayload(
                sub=payload["sub"],
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                type=payload["type"],
            )
        except JWTError as e:
            logger.warning(f"[AuthService] Token verification failed: {e}")
            raise InvalidTokenError("Invalid or expired token")

    # ═══════════════════════════════════════════════════════════════════════
    # USER REGISTRATION & LOGIN
    # ═══════════════════════════════════════════════════════════════════════

    async def register(self, user_data: UserCreate) -> AuthResponse:
        """
        Register a new user.

        Args:
            user_data: User registration data

        Returns:
            AuthResponse with user and tokens

        Raises:
            UserAlreadyExistsError: If email already registered
        """
        logger.info(f"[AuthService] Registering user: {user_data.email}")

        # Check if email exists
        if await self.repository.email_exists(user_data.email):
            raise UserAlreadyExistsError(f"Email already registered: {user_data.email}")

        # Hash password and create user
        hashed_password = self.hash_password(user_data.password)
        user = await self.repository.create(user_data, hashed_password)

        # Create tokens
        tokens = self.create_tokens(user.id)

        # Update last login
        await self.repository.update_last_login(user.id)

        logger.info(f"[AuthService] User registered successfully: {user.id}")

        return AuthResponse(
            user=UserRead.model_validate(user),
            tokens=tokens,
        )

    async def login(self, credentials: UserLogin) -> AuthResponse:
        """
        Authenticate a user with email and password.

        Args:
            credentials: Login credentials

        Returns:
            AuthResponse with user and tokens

        Raises:
            AuthenticationError: If credentials are invalid
        """
        logger.info(f"[AuthService] Login attempt: {credentials.email}")

        # Get user
        user = await self.repository.get_by_email(credentials.email)

        if not user:
            raise AuthenticationError("Invalid email or password")

        # Check if user is OAuth-only
        if user.auth_provider != AuthProvider.LOCAL and not user.hashed_password:
            raise AuthenticationError(
                f"This account uses {user.auth_provider.value} sign-in. "
                "Please use that method to log in."
            )

        # Verify password
        if not user.hashed_password or not self.verify_password(
                credentials.password, user.hashed_password
        ):
            raise AuthenticationError("Invalid email or password")

        # Check if account is active
        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        # Create tokens
        tokens = self.create_tokens(user.id)

        # Update last login
        await self.repository.update_last_login(user.id)

        logger.info(f"[AuthService] User logged in: {user.id}")

        return AuthResponse(
            user=UserRead.model_validate(user),
            tokens=tokens,
        )

    async def refresh_tokens(self, refresh_token: str) -> Token:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            New Token with fresh access and refresh tokens

        Raises:
            InvalidTokenError: If refresh token is invalid
            UserNotFoundError: If user no longer exists
        """
        # Verify refresh token
        payload = self.verify_token(refresh_token, token_type="refresh")

        # Get user
        user = await self.repository.get_by_id(payload.sub)
        if not user or not user.is_active:
            raise UserNotFoundError("User not found or inactive")

        # Create new tokens
        return self.create_tokens(user.id)

    # ═══════════════════════════════════════════════════════════════════════
    # OAUTH AUTHENTICATION
    # ═══════════════════════════════════════════════════════════════════════

    async def authenticate_oauth(self, oauth_info: OAuthUserInfo) -> AuthResponse:
        """
        Authenticate or register user via OAuth.

        Args:
            oauth_info: User info from OAuth provider

        Returns:
            AuthResponse with user and tokens
        """
        logger.info(f"[AuthService] OAuth authentication: {oauth_info.email}")

        # Check if user exists by Google ID
        user = await self.repository.get_by_google_id(oauth_info.google_id)

        if not user:
            # Check if email exists (link accounts)
            user = await self.repository.get_by_email(oauth_info.email)

            if user:
                # Link Google account to existing user
                user = await self.repository.link_google_account(
                    user.id,
                    oauth_info.google_id,
                    oauth_info.picture_url,
                )
                logger.info(f"[AuthService] Linked Google account to user: {user.id}")
            else:
                # Create new OAuth user
                user = await self.repository.create_oauth_user(oauth_info)
                logger.info(f"[AuthService] Created OAuth user: {user.id}")

        # Check if account is active
        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        # Create tokens
        tokens = self.create_tokens(user.id)

        # Update last login
        await self.repository.update_last_login(user.id)

        return AuthResponse(
            user=UserRead.model_validate(user),
            tokens=tokens,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # USER MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    async def get_current_user(self, user_id: str) -> User:
        """
        Get current authenticated user.

        Args:
            user_id: User UUID from token

        Returns:
            User entity

        Raises:
            UserNotFoundError: If user not found
        """
        user = await self.repository.get_by_id(user_id)
        if not user or not user.is_active:
            raise UserNotFoundError("User not found or inactive")
        return user

    async def change_password(
            self,
            user_id: str,
            current_password: str,
            new_password: str,
    ) -> None:
        """
        Change user's password.

        Args:
            user_id: User UUID
            current_password: Current password
            new_password: New password

        Raises:
            AuthenticationError: If current password is wrong
        """
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        if not user.hashed_password:
            raise AuthenticationError(
                "Cannot change password for OAuth-only account"
            )

        if not self.verify_password(current_password, user.hashed_password):
            raise AuthenticationError("Current password is incorrect")

        hashed_password = self.hash_password(new_password)
        await self.repository.update_password(user_id, hashed_password)

        logger.info(f"[AuthService] Password changed for user: {user_id}")


    # ═══════════════════════════════════════════════════════════════════════
    # PASSWORD RESET
    # ═══════════════════════════════════════════════════════════════════════

    async def initiate_password_reset(self, email: str) -> None:
        """
        Start the password reset flow: generate a 6-digit code and send it.

        Always returns silently to prevent email enumeration.
        """
        logger.info("[AuthService] Password reset requested")

        user = await self.repository.get_by_email(email)

        # Silently bail for non-existent or OAuth-only users
        if not user or user.auth_provider != AuthProvider.LOCAL:
            return
        if not user.is_active:
            return

        # Invalidate any previous codes
        await self.reset_repository.invalidate_all_for_user(user.id)

        # Generate cryptographic 6-digit code
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        await self.reset_repository.create_reset_code(
            user_id=user.id,
            email=user.email,
            code=code,
            expires_at=expires_at,
        )

        # Send email (fire-and-forget; failure is logged but not raised)
        from app.email_service import EmailService

        email_service = EmailService()
        sent = await email_service.send_password_reset_code(
            to_email=user.email,
            code=code,
            user_name=user.full_name,
        )
        if not sent:
            logger.error(f"[AuthService] Failed to send reset email for user: {user.id}")

    async def verify_reset_code(self, email: str, code: str) -> ResetTokenResponse:
        """
        Verify a 6-digit reset code and return a short-lived JWT.

        Raises:
            AuthenticationError: If the code is invalid, expired, or max attempts reached.
        """
        reset_code = await self.reset_repository.get_active_code_by_email(email)

        if not reset_code:
            raise AuthenticationError("Invalid or expired reset code")

        # Check max attempts
        if reset_code.attempts >= reset_code.max_attempts:
            raise AuthenticationError("Too many attempts. Please request a new code.")

        # Increment attempts before checking (prevents timing attacks)
        await self.reset_repository.increment_attempts(reset_code.id)

        if reset_code.code != code:
            remaining = reset_code.max_attempts - reset_code.attempts - 1
            raise AuthenticationError(
                f"Invalid code. {remaining} attempt(s) remaining."
            )

        # Mark code as used
        await self.reset_repository.mark_as_used(reset_code.id)

        # Create a short-lived password_reset JWT (10 minutes)
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        payload = {
            "sub": reset_code.user_id,
            "exp": expires,
            "type": "password_reset",
        }
        token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

        expires_in = int((expires - datetime.now(timezone.utc)).total_seconds())

        logger.info(f"[AuthService] Reset code verified for user: {reset_code.user_id}")

        return ResetTokenResponse(reset_token=token, expires_in=expires_in)

    async def reset_password_with_token(
        self, token: str, new_password: str
    ) -> None:
        """
        Set a new password using a password_reset JWT.

        Raises:
            InvalidTokenError: If the token is invalid or not a password_reset token.
        """
        payload = self.verify_token(token, token_type="password_reset")

        user = await self.repository.get_by_id(payload.sub)
        if not user or not user.is_active:
            raise UserNotFoundError("User not found or inactive")

        hashed_password = self.hash_password(new_password)
        await self.repository.update_password(user.id, hashed_password)

        # Invalidate all remaining reset codes for this user
        await self.reset_repository.invalidate_all_for_user(user.id)

        logger.info(f"[AuthService] Password reset completed for user: {user.id}")


def get_auth_service(db: AsyncSession) -> AuthService:
    """Factory function for AuthService."""
    return AuthService(db)