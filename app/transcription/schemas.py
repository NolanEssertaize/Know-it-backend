"""
Pydantic schemas for transcription module.
DTOs for API input/output validation.
"""

from pydantic import BaseModel, Field


class TranscriptionResponse(BaseModel):
    """Response DTO for transcription endpoint."""

    text: str = Field(..., description="Transcribed text from audio")
    duration_seconds: float | None = Field(
        None, description="Audio duration in seconds"
    )
    language: str | None = Field(None, description="Detected language code")

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "Le polymorphisme en Java permet à des objets de différentes classes d'être traités comme des objets d'une classe parente commune.",
                "duration_seconds": 12.5,
                "language": "fr",
            }
        }
    }


class TranscriptionError(BaseModel):
    """Error response for transcription failures."""

    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "Failed to transcribe audio file",
                "code": "TRANSCRIPTION_FAILED",
            }
        }
    }
