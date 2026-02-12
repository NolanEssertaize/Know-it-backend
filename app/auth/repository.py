"""
Authentication repository - Data Access Layer for users.
Handles all database operations for User entities.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AuthProvider, PasswordResetCode, User
from app.auth.schemas import OAuthUserInfo, UserCreate

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for User CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_data: UserCreate, hashed_password: str) -> User:
        """
        Create a new local user.

        Args:
            user_data: User creation DTO
            hashed_password: Pre-hashed password

        Returns:
            Created User entity
        """
        user = User(
            id=str(uuid4()),
            email=user_data.email.lower(),
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            auth_provider=AuthProvider.LOCAL,
            is_verified=False,
        )

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        logger.info(f"[UserRepository] Created local user: {user.id}")
        return user

    async def create_oauth_user(self, oauth_info: OAuthUserInfo) -> User:
        """
        Create a new OAuth user.

        Args:
            oauth_info: OAuth user info from provider

        Returns:
            Created User entity
        """
        user = User(
            id=str(uuid4()),
            email=oauth_info.email.lower(),
            hashed_password=None,
            full_name=oauth_info.full_name,
            picture_url=oauth_info.picture_url,
            auth_provider=AuthProvider.GOOGLE,
            google_id=oauth_info.google_id,
            is_verified=oauth_info.email_verified,
        )

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        logger.info(f"[UserRepository] Created OAuth user: {user.id}")
        return user

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """
        Get a user by ID.

        Args:
            user_id: User UUID

        Returns:
            User entity or None
        """
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by email.

        Args:
            email: User email address

        Returns:
            User entity or None
        """
        stmt = select(User).where(User.email == email.lower())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_google_id(self, google_id: str) -> Optional[User]:
        """
        Get a user by Google ID.

        Args:
            google_id: Google user ID

        Returns:
            User entity or None
        """
        stmt = select(User).where(User.google_id == google_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_last_login(self, user_id: str) -> None:
        """
        Update user's last login timestamp.

        Args:
            user_id: User UUID
        """
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(last_login=datetime.now(timezone.utc))
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def update_password(self, user_id: str, hashed_password: str) -> None:
        """
        Update user's password.

        Args:
            user_id: User UUID
            hashed_password: New hashed password
        """
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                hashed_password=hashed_password,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.db.execute(stmt)
        await self.db.flush()
        logger.info(f"[UserRepository] Updated password for user: {user_id}")

    async def update_profile(
            self,
            user_id: str,
            full_name: Optional[str] = None,
            picture_url: Optional[str] = None,
    ) -> Optional[User]:
        """
        Update user profile.

        Args:
            user_id: User UUID
            full_name: New full name
            picture_url: New picture URL

        Returns:
            Updated User entity or None
        """
        update_data = {"updated_at": datetime.now(timezone.utc)}

        if full_name is not None:
            update_data["full_name"] = full_name
        if picture_url is not None:
            update_data["picture_url"] = picture_url

        stmt = update(User).where(User.id == user_id).values(**update_data)
        await self.db.execute(stmt)
        await self.db.flush()

        return await self.get_by_id(user_id)

    async def link_google_account(
            self,
            user_id: str,
            google_id: str,
            picture_url: Optional[str] = None,
    ) -> Optional[User]:
        """
        Link Google account to existing user.

        Args:
            user_id: User UUID
            google_id: Google user ID
            picture_url: Google profile picture URL

        Returns:
            Updated User entity or None
        """
        update_data = {
            "google_id": google_id,
            "updated_at": datetime.now(timezone.utc),
        }

        if picture_url:
            update_data["picture_url"] = picture_url

        stmt = update(User).where(User.id == user_id).values(**update_data)
        await self.db.execute(stmt)
        await self.db.flush()

        logger.info(f"[UserRepository] Linked Google account to user: {user_id}")
        return await self.get_by_id(user_id)

    async def verify_email(self, user_id: str) -> None:
        """
        Mark user's email as verified.

        Args:
            user_id: User UUID
        """
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                is_verified=True,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.db.execute(stmt)
        await self.db.flush()
        logger.info(f"[UserRepository] Verified email for user: {user_id}")

    async def deactivate(self, user_id: str) -> None:
        """
        Deactivate a user account.

        Args:
            user_id: User UUID
        """
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                is_active=False,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.db.execute(stmt)
        await self.db.flush()
        logger.info(f"[UserRepository] Deactivated user: {user_id}")

    async def email_exists(self, email: str) -> bool:
        """
        Check if email already exists.

        Args:
            email: Email to check

        Returns:
            True if exists
        """
        user = await self.get_by_email(email)
        return user is not None


class PasswordResetRepository:
    """Repository for password reset code operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_reset_code(
        self,
        user_id: str,
        email: str,
        code: str,
        expires_at: datetime,
    ) -> PasswordResetCode:
        """Create a new password reset code."""
        reset_code = PasswordResetCode(
            id=str(uuid4()),
            user_id=user_id,
            email=email.lower(),
            code=code,
            expires_at=expires_at,
        )
        self.db.add(reset_code)
        await self.db.flush()
        logger.info(f"[PasswordResetRepository] Created reset code for user: {user_id}")
        return reset_code

    async def get_active_code_by_email(self, email: str) -> Optional[PasswordResetCode]:
        """Get the latest active (non-used, non-expired) code for an email."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(PasswordResetCode)
            .where(
                PasswordResetCode.email == email.lower(),
                PasswordResetCode.is_used == False,  # noqa: E712
                PasswordResetCode.expires_at > now,
            )
            .order_by(PasswordResetCode.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def increment_attempts(self, code_id: str) -> None:
        """Increment the attempt counter for a reset code."""
        stmt = (
            update(PasswordResetCode)
            .where(PasswordResetCode.id == code_id)
            .values(attempts=PasswordResetCode.attempts + 1)
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def mark_as_used(self, code_id: str) -> None:
        """Mark a reset code as used."""
        stmt = (
            update(PasswordResetCode)
            .where(PasswordResetCode.id == code_id)
            .values(
                is_used=True,
                used_at=datetime.now(timezone.utc),
            )
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def invalidate_all_for_user(self, user_id: str) -> None:
        """Invalidate all active reset codes for a user."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(PasswordResetCode)
            .where(
                PasswordResetCode.user_id == user_id,
                PasswordResetCode.is_used == False,  # noqa: E712
            )
            .values(is_used=True, used_at=now)
        )
        await self.db.execute(stmt)
        await self.db.flush()
        logger.info(f"[PasswordResetRepository] Invalidated all codes for user: {user_id}")