"""
Analysis repository - Data Access Layer for sessions.
Handles all database operations for Session entities.
"""

import logging
from typing import List, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.models import Session
from app.analysis.schemas import AnalysisResult, SessionCreate
from app.core.exceptions import SessionNotFoundError

logger = logging.getLogger(__name__)


class SessionRepository:
    """Repository for Session CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, session_data: SessionCreate) -> Session:
        """
        Create a new session in the database.

        Args:
            session_data: Session creation DTO

        Returns:
            Created Session entity
        """
        from uuid import uuid4

        session = Session(
            id=str(uuid4()),
            topic_id=session_data.topic_id,
            audio_uri=session_data.audio_uri,
            transcription=session_data.transcription,
            analysis_data=session_data.analysis.model_dump(),
        )

        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)

        logger.info(f"[SessionRepository] Created session: {session.id}")
        return session

    async def get_by_id(self, session_id: str) -> Session:
        """
        Get a session by its ID.

        Args:
            session_id: Session UUID

        Returns:
            Session entity

        Raises:
            SessionNotFoundError: If session not found
        """
        stmt = select(Session).where(Session.id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if session is None:
            raise SessionNotFoundError(f"Session not found: {session_id}")

        return session

    async def get_by_topic_id(self, topic_id: str) -> Sequence[Session]:
        """
        Get all sessions for a topic.

        Args:
            topic_id: Parent topic UUID

        Returns:
            List of Session entities
        """
        stmt = (
            select(Session)
            .where(Session.topic_id == topic_id)
            .order_by(Session.date.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def delete(self, session_id: str) -> bool:
        """
        Delete a session by its ID.

        Args:
            session_id: Session UUID

        Returns:
            True if deleted, False if not found
        """
        session = await self.get_by_id(session_id)
        await self.db.delete(session)
        await self.db.flush()

        logger.info(f"[SessionRepository] Deleted session: {session_id}")
        return True

    async def count_by_topic(self, topic_id: str) -> int:
        """
        Count sessions for a topic.

        Args:
            topic_id: Parent topic UUID

        Returns:
            Number of sessions
        """
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(Session)
            .where(Session.topic_id == topic_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()
