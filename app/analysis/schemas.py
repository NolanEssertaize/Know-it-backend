"""
Pydantic schemas for analysis module.
DTOs for API input/output validation.
"""

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class AnalysisResult(BaseModel):
    """
    Structured analysis result matching frontend AnalysisResult interface.
    Contains valid points, corrections, and missing concepts.
    """

    valid: List[str] = Field(
        default_factory=list,
        description="Points correctly mentioned by the user",
    )
    corrections: List[str] = Field(
        default_factory=list,
        description="Factual errors or inaccuracies to correct",
    )
    missing: List[str] = Field(
        default_factory=list,
        description="Key concepts the user forgot to mention",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "valid": [
                    "Définition correcte du polymorphisme (traitement via classe parente).",
                    "Mention du lien avec l'héritage.",
                ],
                "corrections": [
                    "Précision : Le polymorphisme s'applique aussi via les Interfaces."
                ],
                "missing": [
                    "Polymorphisme statique (Surcharge) vs Dynamique (Redéfinition).",
                    "Exemple concret (e.g., List vs ArrayList).",
                ],
            }
        }
    }


class AnalysisRequest(BaseModel):
    """Request DTO for analysis endpoint."""

    text: str = Field(
        ...,
        min_length=10,
        max_length=50000,
        description="Transcribed text to analyze",
    )
    topic_title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Topic title for context",
    )
    topic_id: str | None = Field(
        None,
        description="Optional topic ID for saving the session",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "Le polymorphisme en Java permet à des objets de différentes classes d'être traités comme des objets d'une classe parente commune.",
                "topic_title": "Polymorphisme en Java",
                "topic_id": "550e8400-e29b-41d4-a716-446655440000",
            }
        }
    }


class AnalysisResponse(BaseModel):
    """Response DTO for analysis endpoint."""

    analysis: AnalysisResult = Field(..., description="Structured analysis result")
    session_id: str | None = Field(
        None,
        description="ID of the saved session (if topic_id was provided)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "analysis": {
                    "valid": ["Point 1", "Point 2"],
                    "corrections": ["Correction 1"],
                    "missing": ["Missing concept 1"],
                },
                "session_id": "660e8400-e29b-41d4-a716-446655440001",
            }
        }
    }


class SessionCreate(BaseModel):
    """DTO for creating a new session."""

    topic_id: str = Field(..., description="Parent topic ID")
    audio_uri: str | None = Field(None, description="Path to audio file")
    transcription: str | None = Field(None, description="Transcribed text")
    analysis: AnalysisResult = Field(..., description="Analysis result")


class SessionRead(BaseModel):
    """DTO for reading a session."""

    id: str = Field(..., description="Session ID")
    date: datetime = Field(..., description="Session creation date")
    audio_uri: str | None = Field(None, description="Path to audio file")
    transcription: str | None = Field(None, description="Transcribed text")
    analysis: AnalysisResult = Field(..., description="Analysis result")
    topic_id: str = Field(..., description="Parent topic ID")

    model_config = {"from_attributes": True}


class AnalysisError(BaseModel):
    """Error response for analysis failures."""

    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "Failed to analyze text",
                "code": "ANALYSIS_FAILED",
            }
        }
    }
