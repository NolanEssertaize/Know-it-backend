"""
Transcription router - API endpoints for audio transcription.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse

from app.core.exceptions import TranscriptionError, ExternalAPIError
from app.dependencies import CurrentActiveUser
from app.transcription.schemas import TranscriptionResponse, TranscriptionError as TranscriptionErrorSchema
from app.transcription.service import TranscriptionService, get_transcription_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transcription", tags=["Transcription"])


@router.post(
    "",
    response_model=TranscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Transcribe audio file",
    description="Upload an audio file and get the transcribed text using OpenAI Whisper.",
    responses={
        200: {"model": TranscriptionResponse, "description": "Successful transcription"},
        400: {"model": TranscriptionErrorSchema, "description": "Invalid audio file"},
        401: {"description": "Not authenticated"},
        403: {"description": "User account is deactivated"},
        500: {"model": TranscriptionErrorSchema, "description": "Transcription failed"},
        503: {"model": TranscriptionErrorSchema, "description": "External API unavailable"},
    },
)
async def transcribe_audio(
        file: Annotated[UploadFile, File(description="Audio file to transcribe (.m4a, .mp3, .wav, etc.)")],
        current_user: CurrentActiveUser,
        language: Annotated[str | None, Form(description="Optional language code (e.g., 'fr', 'en')")] = None,
        service: TranscriptionService = Depends(get_transcription_service),
) -> TranscriptionResponse:
    """
    Transcribe an uploaded audio file to text.

    Supported formats: m4a, mp3, mp4, wav, webm, ogg, flac
    Max file size: 25MB (OpenAI limit)

    Requires authentication.

    Args:
        file: Audio file to transcribe
        current_user: Authenticated user (injected by dependency)
        language: Optional language hint for better accuracy

    Returns:
        TranscriptionResponse with transcribed text
    """
    logger.info(f"[TranscriptionRouter] Received file: {file.filename}, size: {file.size}, user: {current_user.id}")

    # Validate file
    if not file.filename:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "No filename provided", "code": "MISSING_FILENAME"},
        )

    allowed_extensions = {".m4a", ".mp3", ".mp4", ".wav", ".webm", ".ogg", ".flac"}
    file_ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""

    if file_ext not in allowed_extensions:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": f"Unsupported file format: {file_ext}. Allowed: {', '.join(allowed_extensions)}",
                "code": "INVALID_FORMAT",
            },
        )

    try:
        # Read file content
        file_content = await file.read()

        # Create a file-like object for the service
        from io import BytesIO
        file_buffer = BytesIO(file_content)

        # Call transcription service
        result = await service.transcribe_audio(
            file=file_buffer,
            filename=file.filename,
            language=language,
        )

        logger.info(f"[TranscriptionRouter] Transcription successful for: {file.filename}")
        return result

    except TranscriptionError as e:
        logger.error(f"[TranscriptionRouter] Transcription error: {e.message}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": e.message, "code": "TRANSCRIPTION_FAILED"},
        )

    except ExternalAPIError as e:
        logger.error(f"[TranscriptionRouter] External API error: {e.message}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": e.message, "code": "EXTERNAL_API_ERROR"},
        )

    except Exception as e:
        logger.exception(f"[TranscriptionRouter] Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An unexpected error occurred", "code": "INTERNAL_ERROR"},
        )

    finally:
        await file.close()