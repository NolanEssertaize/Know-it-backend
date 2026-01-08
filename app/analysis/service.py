"""
Analysis service - Business logic for text analysis.
Integrates with OpenAI GPT-4 API for semantic analysis.
"""

import json
import logging
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import AnalysisError, ExternalAPIError
from app.analysis.models import Session
from app.analysis.repository import SessionRepository
from app.analysis.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisResult,
    SessionCreate,
    SessionRead,
)

logger = logging.getLogger(__name__)

# System prompt for GPT-4 analysis (matches frontend documentation)
ANALYSIS_SYSTEM_PROMPT = """Tu es un expert technique rigoureux et pédagogue.
Analyse la réponse de l'utilisateur sur le sujet : "{topic_title}".

Retourne UNIQUEMENT un objet JSON strict avec exactement ces 3 champs :
1. "valid": array de strings - points techniquement corrects mentionnés par l'utilisateur.
2. "corrections": array de strings - erreurs factuelles ou imprécisions à corriger.
3. "missing": array de strings - concepts clés du sujet que l'utilisateur a oubliés.

Règles importantes:
- Sois précis et constructif dans tes retours
- Chaque point doit être une phrase complète et claire
- Si l'utilisateur a tout bon, "corrections" et "missing" peuvent être vides
- Si l'utilisateur n'a rien dit de pertinent, "valid" peut être vide
- Ne rajoute AUCUN texte avant ou après le JSON

Exemple de format de sortie:
{{"valid": ["Point 1", "Point 2"], "corrections": ["Correction 1"], "missing": ["Concept manquant 1"]}}
"""


class AnalysisService:
    """Service for handling text analysis via GPT-4 API."""

    def __init__(
        self,
        db: AsyncSession | None = None,
        openai_client: AsyncOpenAI | None = None,
    ):
        self.settings = get_settings()
        self._client = openai_client
        self._db = db

    @property
    def client(self) -> AsyncOpenAI:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        return self._client

    async def analyze_text(
        self,
        request: AnalysisRequest,
    ) -> AnalysisResponse:
        """
        Analyze transcribed text using GPT-4.

        Args:
            request: Analysis request with text and topic

        Returns:
            AnalysisResponse with structured feedback

        Raises:
            AnalysisError: If analysis fails
            ExternalAPIError: If OpenAI API call fails
        """
        logger.info(
            f"[AnalysisService] Analyzing text for topic: {request.topic_title}"
        )
        logger.debug(f"[AnalysisService] Text length: {len(request.text)} chars")

        try:
            # Build the system prompt with topic context
            system_prompt = ANALYSIS_SYSTEM_PROMPT.format(
                topic_title=request.topic_title
            )

            # Call GPT-4 API
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": request.text},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,  # Lower temperature for more consistent output
                max_tokens=2000,
            )

            # Parse the response
            content = response.choices[0].message.content
            if not content:
                raise AnalysisError("Empty response from GPT-4")

            logger.debug(f"[AnalysisService] Raw GPT response: {content}")

            # Parse JSON response
            try:
                analysis_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"[AnalysisService] JSON parse error: {e}")
                raise AnalysisError(f"Invalid JSON response from GPT-4: {str(e)}")

            # Validate and create AnalysisResult
            analysis = AnalysisResult(
                valid=analysis_data.get("valid", []),
                corrections=analysis_data.get("corrections", []),
                missing=analysis_data.get("missing", []),
            )

            logger.info(
                f"[AnalysisService] Analysis complete - "
                f"valid: {len(analysis.valid)}, "
                f"corrections: {len(analysis.corrections)}, "
                f"missing: {len(analysis.missing)}"
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

        except AnalysisError:
            raise
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

    async def get_session(self, session_id: str) -> SessionRead:
        """
        Get a session by ID.

        Args:
            session_id: Session UUID

        Returns:
            Session data
        """
        if self._db is None:
            raise AnalysisError("Database session not available")

        repository = SessionRepository(self._db)
        session = await repository.get_by_id(session_id)

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
