"""
Topics repository - Data Access Layer for topics.
Handles all database operations for Topic entities.
"""

import logging
from typing import Sequence
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.topics.models import Topic
from app.topics.schemas import TopicCreate, TopicUpdate
from app.core.exceptions import TopicNotFoundError

logger = logging.getLogger(__name__)


class TopicRepository:
    """Repository for Topic CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, topic_data: TopicCreate) -> Topic:
        """
        Create a new topic.

        Args:
            topic_data: Topic creation DTO

        Returns:
            Created Topic entity
        """
        topic = Topic(
            id=str(uuid4()),
            title=topic_data.title,
        )

        self.db.add(topic)
        await self.db.flush()
        await self.db.refresh(topic)

        logger.info(f"[TopicRepository] Created topic: {topic.id} - {topic.title}")
        return topic

    async def get_by_id(self, topic_id: str, with_sessions: bool = False) -> Topic:
        """
        Get a topic by its ID.

        Args:
            topic_id: Topic UUID
            with_sessions: Whether to eagerly load sessions

        Returns:
            Topic entity

        Raises:
            TopicNotFoundError: If topic not found
        """
        stmt = select(Topic).where(Topic.id == topic_id)

        if with_sessions:
            stmt = stmt.options(selectinload(Topic.sessions))

        result = await self.db.execute(stmt)
        topic = result.scalar_one_or_none()

        if topic is None:
            raise TopicNotFoundError(f"Topic not found: {topic_id}")

        return topic

    async def get_all(self, skip: int = 0, limit: int = 100) -> Sequence[Topic]:
        """
        Get all topics with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of Topic entities
        """
        stmt = (
            select(Topic)
            .order_by(Topic.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def count(self) -> int:
        """
        Count total number of topics.

        Returns:
            Total count
        """
        stmt = select(func.count()).select_from(Topic)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def update(self, topic_id: str, topic_data: TopicUpdate) -> Topic:
        """
        Update a topic.

        Args:
            topic_id: Topic UUID
            topic_data: Topic update DTO

        Returns:
            Updated Topic entity

        Raises:
            TopicNotFoundError: If topic not found
        """
        topic = await self.get_by_id(topic_id)

        if topic_data.title is not None:
            topic.title = topic_data.title

        await self.db.flush()
        await self.db.refresh(topic)

        logger.info(f"[TopicRepository] Updated topic: {topic.id}")
        return topic

    async def delete(self, topic_id: str) -> bool:
        """
        Delete a topic and all its sessions.

        Args:
            topic_id: Topic UUID

        Returns:
            True if deleted

        Raises:
            TopicNotFoundError: If topic not found
        """
        topic = await self.get_by_id(topic_id)
        await self.db.delete(topic)
        await self.db.flush()

        logger.info(f"[TopicRepository] Deleted topic: {topic_id}")
        return True

    async def exists(self, topic_id: str) -> bool:
        """
        Check if a topic exists.

        Args:
            topic_id: Topic UUID

        Returns:
            True if exists, False otherwise
        """
        stmt = select(func.count()).select_from(Topic).where(Topic.id == topic_id)
        result = await self.db.execute(stmt)
        return result.scalar_one() > 0
