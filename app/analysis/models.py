"""
SQLAlchemy models for analysis module.
Defines the Session table structure.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.topics.models import Topic


class Session(Base):
    """
    Session model representing a learning session.
    Stores audio URI, transcription, and analysis results.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    audio_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Store analysis as JSONB for flexibility
    # Structure: {"valid": [...], "corrections": [...], "missing": [...]}
    analysis_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Foreign key to Topic
    topic_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationship
    topic: Mapped["Topic"] = relationship(
        "Topic",
        back_populates="sessions",
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, topic_id={self.topic_id}, date={self.date})>"

    @property
    def analysis_valid(self) -> List[str]:
        """Get valid points from analysis."""
        return self.analysis_data.get("valid", [])

    @property
    def analysis_corrections(self) -> List[str]:
        """Get corrections from analysis."""
        return self.analysis_data.get("corrections", [])

    @property
    def analysis_missing(self) -> List[str]:
        """Get missing concepts from analysis."""
        return self.analysis_data.get("missing", [])
