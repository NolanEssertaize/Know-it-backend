"""
Analysis service - Business logic for text analysis and GPT-4 integration.
Includes user ownership verification for topics and sessions.
"""

import json
import logging
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.repository import SessionRepository
from app.analysis.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisResult,
    SessionCreate,
    SessionRead,
)
from app.config import get_settings
from app.core.exceptions import AnalysisError, ExternalAPIError, SessionNotFoundError
from app.topics.repository import TopicRepository

logger = logging.getLogger(__name__)
settings = get_settings()

# Analysis prompt template
ANALYSIS_PROMPT = """Tu es un assistant pédagogique expert. Analyse la réponse de l'étudiant sur le sujet "{topic}".

Évalue sa compréhension et retourne un JSON avec exactement cette structure :
{{
    "valid": ["point correct 1", "point correct 2", ...],
    "corrections": ["erreur à corriger 1", "erreur à corriger 2", ...],
    "missing": ["concept manquant 1", "concept manquant 2", ...]
}}

Règles :
- "valid" : les points factuellement corrects et bien expliqués
- "corrections" : les erreurs ou imprécisions à corriger (avec la correction)
- "missing" : les concepts importants non mentionnés

Réponds UNIQUEMENT avec le JSON, sans texte supplémentaire."""


class AnalysisService:
    """Service for text analysis with GPT-4 and user scoping."""

    def __init__(self, db: Optional[AsyncSession] = None):
        self._client: Optional[AsyncOpenAI] = None
        self._db = db

    @property
    def client(self) -> AsyncOpenAI:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    async def analyze_text(
            self,
            request: AnalysisRequest,
            user_id: Optional[str] = None,
    ) -> AnalysisResponse:
        """
        Analyze transcribed text using GPT-4.

        Args:
            request: Analysis request with text and topic
            user_id: User ID for topic ownership verification

        Returns:
            AnalysisResponse with structured analysis

        Raises:
            AnalysisError: If analysis fails
            ExternalAPIError: If OpenAI API fails
            PermissionError: If topic doesn't belong to user
        """
        logger.info(f"[AnalysisService] Starting analysis for topic: {request.topic_title}")

        # Verify topic ownership if topic_id is provided
        if request.topic_id and user_id and self._db:
            topic_repo = TopicRepository(self._db)
            is_owner = await topic_repo.verify_ownership(request.topic_id, user_id)
            if not is_owner:
                raise PermissionError(f"Topic {request.topic_id} does not belong to user {user_id}")

        try:
            # Prepare the prompt
            system_prompt = ANALYSIS_PROMPT.format(topic=request.topic_title)

            # Call GPT-4
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": request.text},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=2000,
            )

            # Parse response
            content = response.choices[0].message.content
            if not content:
                raise AnalysisError("Empty response from GPT-4")

            analysis_data = json.loads(content)
            analysis = AnalysisResult(
                valid=analysis_data.get("valid", []),
                corrections=analysis_data.get("corrections", []),
                missing=analysis_data.get("missing", []),
            )

            logger.info(
                f"[AnalysisService] Analysis complete: "
                f"valid={len(analysis.valid)}, "
                f"corrections={len(analysis.corrections)}, "
                f"missing={len(analysis.missing)}"
            )

            # Save session if topic_id is provided and db is available
            session_id: str | None = None
            if request.topic_id and self._db:
                session_id = await self._save_session(
                    topic_id=request.topic_id,
                    transcription=request.text,
                    analysis=analysis,
                )

            return AnalysisResponse(
                analysis=analysis,
                session_id=session_id,
            )

        except PermissionError:
            raise
        except AnalysisError:
            raise
        except json.JSONDecodeError as e:
            logger.error(f"[AnalysisService] Failed to parse GPT-4 response: {e}")
            raise AnalysisError("Failed to parse analysis response")
        except Exception as e:
            logger.error(f"[AnalysisService] Analysis failed: {str(e)}")

            if "api" in str(e).lower() or "openai" in str(e).lower():
                raise ExternalAPIError(f"OpenAI API error: {str(e)}")

            raise AnalysisError(f"Failed to analyze text: {str(e)}")

    async def _save_session(
            self,
            topic_id: str,
            transcription: str,
            analysis: AnalysisResult,
            audio_uri: str | None = None,
    ) -> str:
        """
        Save analysis session to database.

        Args:
            topic_id: Parent topic ID
            transcription: Transcribed text
            analysis: Analysis result
            audio_uri: Optional audio file path

        Returns:
            Created session ID
        """
        if self._db is None:
            raise AnalysisError("Database session not available")

        repository = SessionRepository(self._db)

        session_data = SessionCreate(
            topic_id=topic_id,
            transcription=transcription,
            analysis=analysis,
            audio_uri=audio_uri,
        )

        session = await repository.create(session_data)
        logger.info(f"[AnalysisService] Saved session: {session.id}")

        return session.id

    async def get_session(
            self,
            session_id: str,
            user_id: Optional[str] = None,
    ) -> SessionRead:
        """
        Get a session by ID.

        Args:
            session_id: Session UUID
            user_id: User ID for ownership verification

        Returns:
            Session data

        Raises:
            SessionNotFoundError: If session not found
            PermissionError: If session's topic doesn't belong to user
        """
        if self._db is None:
            raise AnalysisError("Database session not available")

        repository = SessionRepository(self._db)
        session = await repository.get_by_id(session_id)

        # Verify ownership through the topic
        if user_id:
            topic_repo = TopicRepository(self._db)
            is_owner = await topic_repo.verify_ownership(session.topic_id, user_id)
            if not is_owner:
                raise PermissionError(f"Session {session_id} does not belong to user {user_id}")

        return SessionRead(
            id=session.id,
            date=session.date,
            audio_uri=session.audio_uri,
            transcription=session.transcription,
            analysis=AnalysisResult(**session.analysis_data),
            topic_id=session.topic_id,
        )

    async def close(self) -> None:
        """Close the OpenAI client connection."""
        if self._client is not None:
            await self._client.close()


def get_analysis_service(db: AsyncSession) -> AnalysisService:
    """Factory function for AnalysisService with database session."""
    return AnalysisService(db=db)