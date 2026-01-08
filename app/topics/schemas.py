"""
Pydantic schemas for topics module.
DTOs for API input/output validation.
"""

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

from app.analysis.schemas import SessionRead


class TopicCreate(BaseModel):
    """DTO for creating a new topic."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Topic title",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Polymorphisme en Java",
            }
        }
    }


class TopicUpdate(BaseModel):
    """DTO for updating a topic."""

    title: str | None = Field(
        None,
        min_length=1,
        max_length=200,
        description="New topic title",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Polymorphisme en Java (avancé)",
            }
        }
    }


class TopicRead(BaseModel):
    """DTO for reading a topic (without sessions)."""

    id: str = Field(..., description="Topic ID")
    title: str = Field(..., description="Topic title")
    created_at: datetime = Field(..., description="Creation timestamp")
    session_count: int = Field(0, description="Number of sessions")

    model_config = {"from_attributes": True}


class TopicDetail(BaseModel):
    """DTO for reading a topic with all sessions."""

    id: str = Field(..., description="Topic ID")
    title: str = Field(..., description="Topic title")
    created_at: datetime = Field(..., description="Creation timestamp")
    sessions: List[SessionRead] = Field(
        default_factory=list,
        description="All sessions for this topic",
    )

    model_config = {"from_attributes": True}


class TopicList(BaseModel):
    """DTO for listing topics."""

    topics: List[TopicRead] = Field(..., description="List of topics")
    total: int = Field(..., description="Total number of topics")


class TopicError(BaseModel):
    """Error response for topic operations."""

    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "Topic not found",
                "code": "TOPIC_NOT_FOUND",
            }
        }
    }
