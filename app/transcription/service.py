"""
Transcription service - Business logic for audio transcription.
Integrates with OpenAI Whisper API.
"""

import logging
from pathlib import Path
from typing import BinaryIO

from openai import AsyncOpenAI

from app.config import get_settings
from app.core.exceptions import TranscriptionError, ExternalAPIError
from app.transcription.schemas import TranscriptionResponse

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for handling audio transcription via Whisper API."""

    def __init__(self, openai_client: AsyncOpenAI | None = None):
        self.settings = get_settings()
        self._client = openai_client

    @property
    def client(self) -> AsyncOpenAI:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        return self._client

    async def transcribe_audio(
        self,
        file: BinaryIO,
        filename: str,
        language: str | None = None,
    ) -> TranscriptionResponse:
        """
        Transcribe an audio file to text using OpenAI Whisper.

        Args:
            file: Binary file object of the audio
            filename: Original filename (used for extension detection)
            language: Optional language code (e.g., 'fr', 'en')

        Returns:
            TranscriptionResponse with transcribed text

        Raises:
            TranscriptionError: If transcription fails
            ExternalAPIError: If OpenAI API call fails
        """
        logger.info(f"[TranscriptionService] Starting transcription for: {filename}")

        try:
            # Prepare the file for OpenAI API
            # OpenAI expects a tuple of (filename, file_content, content_type)
            file_extension = Path(filename).suffix.lower()
            content_type = self._get_content_type(file_extension)

            logger.debug(f"[TranscriptionService] File type: {content_type}")

            # Call Whisper API
            transcription_params = {
                "model": self.settings.whisper_model,
                "file": (filename, file, content_type),
                "response_format": "verbose_json",
            }

            if language:
                transcription_params["language"] = language

            response = await self.client.audio.transcriptions.create(
                **transcription_params
            )

            logger.info(
                f"[TranscriptionService] Transcription successful, "
                f"length: {len(response.text)} chars"
            )

            return TranscriptionResponse(
                text=response.text,
                duration_seconds=getattr(response, "duration", None),
                language=getattr(response, "language", language),
            )

        except Exception as e:
            logger.error(f"[TranscriptionService] Transcription failed: {str(e)}")

            if "api" in str(e).lower() or "openai" in str(e).lower():
                raise ExternalAPIError(f"OpenAI API error: {str(e)}")

            raise TranscriptionError(f"Failed to transcribe audio: {str(e)}")

    def _get_content_type(self, extension: str) -> str:
        """Map file extension to MIME type."""
        content_types = {
            ".m4a": "audio/m4a",
            ".mp3": "audio/mpeg",
            ".mp4": "audio/mp4",
            ".wav": "audio/wav",
            ".webm": "audio/webm",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac",
        }
        return content_types.get(extension, "audio/mpeg")

    async def close(self) -> None:
        """Close the OpenAI client connection."""
        if self._client is not None:
            await self._client.close()


# Singleton instance for dependency injection
_transcription_service: TranscriptionService | None = None


async def get_transcription_service() -> TranscriptionService:
    """Dependency provider for TranscriptionService."""
    global _transcription_service
    if _transcription_service is None:
        _transcription_service = TranscriptionService()
    return _transcription_service
