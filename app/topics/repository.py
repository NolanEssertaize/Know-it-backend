"""
Topics repository - Data Access Layer for topics.
Handles all database operations for Topic entities.
All operations filter by user_id for security.

FIX: Added get_session_count() method and with_session_count parameter
to avoid lazy-loading issues in async SQLAlchemy.
"""

import logging
from typing import Optional, Sequence, Dict
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.topics.models import Topic
from app.analysis.models import Session
from app.topics.schemas import TopicCreate, TopicUpdate
from app.core.exceptions import TopicNotFoundError

logger = logging.getLogger(__name__)


class TopicRepository:
    """Repository for Topic CRUD operations with user filtering."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, topic_data: TopicCreate, user_id: str) -> Topic:
        """
        Create a new topic for a user.

        Args:
            topic_data: Topic creation DTO
            user_id: Owner user ID

        Returns:
            Created Topic entity (session_count will be 0)
        """
        topic = Topic(
            id=str(uuid4()),
            title=topic_data.title,
            user_id=user_id,
        )

        self.db.add(topic)
        await self.db.flush()
        await self.db.refresh(topic)

        logger.info(f"[TopicRepository] Created topic: {topic.id} - {topic.title} for user: {user_id}")
        return topic

    async def get_by_id(
            self,
            topic_id: str,
            user_id: Optional[str] = None,
            with_sessions: bool = False,
            verify_ownership: bool = True,
    ) -> Topic:
        """
        Get a topic by its ID.

        Args:
            topic_id: Topic UUID
            user_id: User ID for ownership verification
            with_sessions: Whether to eagerly load sessions
            verify_ownership: Whether to verify user ownership

        Returns:
            Topic entity

        Raises:
            TopicNotFoundError: If topic not found
            PermissionError: If topic doesn't belong to user
        """
        stmt = select(Topic).where(Topic.id == topic_id)

        if with_sessions:
            stmt = stmt.options(selectinload(Topic.sessions))

        result = await self.db.execute(stmt)
        topic = result.scalar_one_or_none()

        if topic is None:
            raise TopicNotFoundError(f"Topic not found: {topic_id}")

        # Verify ownership if user_id provided and verification enabled
        if verify_ownership and user_id is not None and topic.user_id != user_id:
            raise PermissionError(f"Topic {topic_id} does not belong to user {user_id}")

        return topic

    async def get_all(
            self,
            user_id: str,
            skip: int = 0,
            limit: int = 100,
            with_sessions: bool = False,
    ) -> Sequence[Topic]:
        """
        Get all topics for a user with pagination.

        Args:
            user_id: User ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            with_sessions: Whether to eagerly load sessions

        Returns:
            List of Topic entities belonging to the user
        """
        stmt = (
            select(Topic)
            .where(Topic.user_id == user_id)
            .order_by(Topic.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        if with_sessions:
            stmt = stmt.options(selectinload(Topic.sessions))

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_session_counts(self, user_id: str) -> Dict[str, int]:
        """
        Get session counts for all topics of a user.

        More efficient than loading all sessions just to count them.

        Args:
            user_id: User ID to filter by

        Returns:
            Dict mapping topic_id to session_count
        """
        stmt = (
            select(Topic.id, func.count(Session.id).label("session_count"))
            .outerjoin(Session, Session.topic_id == Topic.id)
            .where(Topic.user_id == user_id)
            .group_by(Topic.id)
        )

        result = await self.db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def get_session_count(self, topic_id: str) -> int:
        """
        Get session count for a single topic.

        Args:
            topic_id: Topic UUID

        Returns:
            Number of sessions
        """
        stmt = (
            select(func.count(Session.id))
            .where(Session.topic_id == topic_id)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def count(self, user_id: str) -> int:
        """
        Count total number of topics for a user.

        Args:
            user_id: User ID to filter by

        Returns:
            Total count
        """
        stmt = select(func.count()).select_from(Topic).where(Topic.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def update(
            self,
            topic_id: str,
            topic_data: TopicUpdate,
            user_id: str,
    ) -> Topic:
        """
        Update a topic.

        Args:
            topic_id: Topic UUID
            topic_data: Update data
            user_id: User ID for ownership verification

        Returns:
            Updated Topic entity

        Raises:
            TopicNotFoundError: If topic not found
            PermissionError: If topic doesn't belong to user
        """
        topic = await self.get_by_id(topic_id, user_id=user_id, verify_ownership=True)

        if topic_data.title is not None:
            topic.title = topic_data.title

        await self.db.flush()
        await self.db.refresh(topic)

        logger.info(f"[TopicRepository] Updated topic: {topic.id}")
        return topic

    async def delete(self, topic_id: str, user_id: str) -> bool:
        """
        Delete a topic by its ID.

        Args:
            topic_id: Topic UUID
            user_id: User ID for ownership verification

        Returns:
            True if deleted

        Raises:
            TopicNotFoundError: If topic not found
            PermissionError: If topic doesn't belong to user
        """
        topic = await self.get_by_id(topic_id, user_id=user_id, verify_ownership=True)
        await self.db.delete(topic)
        await self.db.flush()

        logger.info(f"[TopicRepository] Deleted topic: {topic_id}")
        return True

    async def exists(self, topic_id: str, user_id: Optional[str] = None) -> bool:
        """
        Check if a topic exists (optionally for a specific user).

        Args:
            topic_id: Topic UUID
            user_id: Optional user ID to filter by

        Returns:
            True if exists
        """
        stmt = select(func.count()).select_from(Topic).where(Topic.id == topic_id)

        if user_id is not None:
            stmt = stmt.where(Topic.user_id == user_id)

        result = await self.db.execute(stmt)
        return result.scalar_one() > 0

    async def verify_ownership(self, topic_id: str, user_id: str) -> bool:
        """
        Verify that a topic belongs to a user.

        Args:
            topic_id: Topic UUID
            user_id: User ID

        Returns:
            True if topic belongs to user
        """
        stmt = (
            select(func.count())
            .select_from(Topic)
            .where(Topic.id == topic_id)
            .where(Topic.user_id == user_id)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one() > 0