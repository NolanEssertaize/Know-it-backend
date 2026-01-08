"""
Topics service - Business logic for topic management.
"""

import logging
from typing import List

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
    """Service for topic business logic."""

    def __init__(self, db: AsyncSession):
        self.repository = TopicRepository(db)

    async def create_topic(self, topic_data: TopicCreate) -> TopicRead:
        """
        Create a new topic.

        Args:
            topic_data: Topic creation DTO

        Returns:
            Created topic data
        """
        logger.info(f"[TopicService] Creating topic: {topic_data.title}")

        topic = await self.repository.create(topic_data)
        return self._to_read_dto(topic)

    async def get_topic(self, topic_id: str) -> TopicDetail:
        """
        Get a topic with all its sessions.

        Args:
            topic_id: Topic UUID

        Returns:
            Topic with sessions
        """
        logger.info(f"[TopicService] Getting topic: {topic_id}")

        topic = await self.repository.get_by_id(topic_id, with_sessions=True)
        return self._to_detail_dto(topic)

    async def list_topics(self, skip: int = 0, limit: int = 100) -> TopicList:
        """
        List all topics with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of topics with total count
        """
        logger.info(f"[TopicService] Listing topics (skip={skip}, limit={limit})")

        topics = await self.repository.get_all(skip=skip, limit=limit)
        total = await self.repository.count()

        return TopicList(
            topics=[self._to_read_dto(t) for t in topics],
            total=total,
        )

    async def update_topic(self, topic_id: str, topic_data: TopicUpdate) -> TopicRead:
        """
        Update a topic.

        Args:
            topic_id: Topic UUID
            topic_data: Topic update DTO

        Returns:
            Updated topic data
        """
        logger.info(f"[TopicService] Updating topic: {topic_id}")

        topic = await self.repository.update(topic_id, topic_data)
        return self._to_read_dto(topic)

    async def delete_topic(self, topic_id: str) -> bool:
        """
        Delete a topic and all its sessions.

        Args:
            topic_id: Topic UUID

        Returns:
            True if deleted
        """
        logger.info(f"[TopicService] Deleting topic: {topic_id}")

        return await self.repository.delete(topic_id)

    async def topic_exists(self, topic_id: str) -> bool:
        """
        Check if a topic exists.

        Args:
            topic_id: Topic UUID

        Returns:
            True if exists
        """
        return await self.repository.exists(topic_id)

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
