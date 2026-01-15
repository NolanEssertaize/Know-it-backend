"""
Topics service - Business logic for topic management.
All operations are scoped to the authenticated user.
"""

import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.schemas import AnalysisResult, SessionRead
from app.topics.models import Topic
from app.topics.repository import TopicRepository
from app.topics.schemas import (
    TopicCreate,
    TopicDetail,
    TopicList,
    TopicRead,
    TopicUpdate,
)

logger = logging.getLogger(__name__)


class TopicService:
    """Service for topic business logic with user scoping."""

    def __init__(self, db: AsyncSession):
        self.repository = TopicRepository(db)

    async def create_topic(self, topic_data: TopicCreate, user_id: str) -> TopicRead:
        """
        Create a new topic for a user.

        Args:
            topic_data: Topic creation DTO
            user_id: Owner user ID

        Returns:
            Created topic data
        """
        logger.info(f"[TopicService] Creating topic: {topic_data.title} for user: {user_id}")

        topic = await self.repository.create(topic_data, user_id=user_id)
        return self._to_read_dto(topic)

    async def get_topic(self, topic_id: str, user_id: str) -> TopicDetail:
        """
        Get a topic with all its sessions.

        Args:
            topic_id: Topic UUID
            user_id: User ID for ownership verification

        Returns:
            Topic with sessions

        Raises:
            TopicNotFoundError: If topic not found
            PermissionError: If topic doesn't belong to user
        """
        logger.info(f"[TopicService] Getting topic: {topic_id} for user: {user_id}")

        topic = await self.repository.get_by_id(
            topic_id,
            user_id=user_id,
            with_sessions=True,
            verify_ownership=True,
        )
        return self._to_detail_dto(topic)

    async def list_topics(
            self,
            user_id: str,
            skip: int = 0,
            limit: int = 100,
    ) -> TopicList:
        """
        List all topics for a user with pagination.

        Args:
            user_id: User ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of topics with total count
        """
        logger.info(f"[TopicService] Listing topics for user: {user_id} (skip={skip}, limit={limit})")

        topics = await self.repository.get_all(user_id=user_id, skip=skip, limit=limit)
        total = await self.repository.count(user_id=user_id)

        return TopicList(
            topics=[self._to_read_dto(t) for t in topics],
            total=total,
        )

    async def update_topic(
            self,
            topic_id: str,
            topic_data: TopicUpdate,
            user_id: str,
    ) -> TopicRead:
        """
        Update a topic.

        Args:
            topic_id: Topic UUID
            topic_data: Topic update DTO
            user_id: User ID for ownership verification

        Returns:
            Updated topic data

        Raises:
            TopicNotFoundError: If topic not found
            PermissionError: If topic doesn't belong to user
        """
        logger.info(f"[TopicService] Updating topic: {topic_id} for user: {user_id}")

        topic = await self.repository.update(topic_id, topic_data, user_id=user_id)
        return self._to_read_dto(topic)

    async def delete_topic(self, topic_id: str, user_id: str) -> bool:
        """
        Delete a topic and all its sessions.

        Args:
            topic_id: Topic UUID
            user_id: User ID for ownership verification

        Returns:
            True if deleted

        Raises:
            TopicNotFoundError: If topic not found
            PermissionError: If topic doesn't belong to user
        """
        logger.info(f"[TopicService] Deleting topic: {topic_id} for user: {user_id}")

        return await self.repository.delete(topic_id, user_id=user_id)

    async def topic_exists(self, topic_id: str, user_id: Optional[str] = None) -> bool:
        """
        Check if a topic exists (optionally for a specific user).

        Args:
            topic_id: Topic UUID
            user_id: Optional user ID to filter by

        Returns:
            True if exists
        """
        return await self.repository.exists(topic_id, user_id=user_id)

    async def verify_ownership(self, topic_id: str, user_id: str) -> bool:
        """
        Verify that a topic belongs to a user.

        Args:
            topic_id: Topic UUID
            user_id: User ID

        Returns:
            True if topic belongs to user
        """
        return await self.repository.verify_ownership(topic_id, user_id)

    def _to_read_dto(self, topic: Topic) -> TopicRead:
        """Convert Topic model to TopicRead DTO."""
        return TopicRead(
            id=topic.id,
            title=topic.title,
            created_at=topic.created_at,
            session_count=topic.session_count,
        )

    def _to_detail_dto(self, topic: Topic) -> TopicDetail:
        """Convert Topic model to TopicDetail DTO."""
        sessions = [
            SessionRead(
                id=s.id,
                date=s.date,
                audio_uri=s.audio_uri,
                transcription=s.transcription,
                analysis=AnalysisResult(**s.analysis_data),
                topic_id=s.topic_id,
            )
            for s in (topic.sessions or [])
        ]

        return TopicDetail(
            id=topic.id,
            title=topic.title,
            created_at=topic.created_at,
            sessions=sessions,
        )


def get_topic_service(db: AsyncSession) -> TopicService:
    """Factory function for TopicService."""
    return TopicService(db)