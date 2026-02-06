"""
Pydantic schemas for flashcards module.
DTOs for API input/output validation.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.flashcards.srs import ReviewRating


# ═══════════════════════════════════════════════════════════════════════════
# DECK SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class DeckCreate(BaseModel):
    """DTO for creating a new deck."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Deck name",
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Optional deck description",
    )
    topic_id: Optional[str] = Field(
        None,
        description="Optional linked topic ID",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Java Fundamentals",
                "description": "Core Java concepts and syntax",
                "topic_id": None,
            }
        }
    }


class DeckUpdate(BaseModel):
    """DTO for updating a deck."""

    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="New deck name",
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="New deck description",
    )
    topic_id: Optional[str] = Field(
        None,
        description="New linked topic ID (use empty string to unlink)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Java Fundamentals (Updated)",
                "description": "Updated description",
            }
        }
    }


class DeckRead(BaseModel):
    """DTO for reading a deck (without cards)."""

    id: str = Field(..., description="Deck ID")
    name: str = Field(..., description="Deck name")
    description: Optional[str] = Field(None, description="Deck description")
    topic_id: Optional[str] = Field(None, description="Linked topic ID")
    card_count: int = Field(0, description="Total number of cards")
    due_count: int = Field(0, description="Number of cards due for review")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


class DeckDetail(BaseModel):
    """DTO for reading a deck with all cards."""

    id: str = Field(..., description="Deck ID")
    name: str = Field(..., description="Deck name")
    description: Optional[str] = Field(None, description="Deck description")
    topic_id: Optional[str] = Field(None, description="Linked topic ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    flashcards: List["FlashcardRead"] = Field(
        default_factory=list,
        description="All flashcards in this deck",
    )

    model_config = {"from_attributes": True}


class DeckList(BaseModel):
    """DTO for listing decks."""

    decks: List[DeckRead] = Field(..., description="List of decks")
    total: int = Field(..., description="Total number of decks")


# ═══════════════════════════════════════════════════════════════════════════
# FLASHCARD SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class FlashcardCreate(BaseModel):
    """DTO for creating a single flashcard."""

    front_content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Question/front side content",
    )
    back_content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Answer/back side content",
    )
    deck_id: str = Field(
        ...,
        description="Parent deck ID",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "front_content": "What is polymorphism in Java?",
                "back_content": "Polymorphism allows objects of different classes to be treated as objects of a common superclass.",
                "deck_id": "deck-uuid-here",
            }
        }
    }


class FlashcardBulkCreate(BaseModel):
    """DTO for bulk creating flashcards."""

    deck_id: str = Field(
        ...,
        description="Parent deck ID",
    )
    cards: List["CardContent"] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of cards to create",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "deck_id": "deck-uuid-here",
                "cards": [
                    {"front": "What is encapsulation?", "back": "Bundling data with methods that operate on that data."},
                    {"front": "What is inheritance?", "back": "A mechanism where a class inherits properties from another class."},
                ],
            }
        }
    }


class CardContent(BaseModel):
    """Simple card content for bulk operations."""

    front: str = Field(..., min_length=1, max_length=5000)
    back: str = Field(..., min_length=1, max_length=5000)


class FlashcardUpdate(BaseModel):
    """DTO for updating a flashcard (content only, no SRS reset)."""

    front_content: Optional[str] = Field(
        None,
        min_length=1,
        max_length=5000,
        description="New question/front side content",
    )
    back_content: Optional[str] = Field(
        None,
        min_length=1,
        max_length=5000,
        description="New answer/back side content",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "front_content": "Updated question?",
                "back_content": "Updated answer.",
            }
        }
    }


class FlashcardRead(BaseModel):
    """DTO for reading a flashcard."""

    id: str = Field(..., description="Flashcard ID")
    front_content: str = Field(..., description="Question/front side")
    back_content: str = Field(..., description="Answer/back side")
    deck_id: str = Field(..., description="Parent deck ID")
    step: int = Field(..., description="Current SRS step (0-7)")
    next_review_at: datetime = Field(..., description="Next scheduled review time")
    interval_minutes: int = Field(..., description="Current interval in minutes")
    review_count: int = Field(..., description="Total number of reviews")
    last_reviewed_at: Optional[datetime] = Field(None, description="Last review timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


class FlashcardDue(BaseModel):
    """DTO for a flashcard that is due for review."""

    id: str = Field(..., description="Flashcard ID")
    front_content: str = Field(..., description="Question/front side")
    back_content: str = Field(..., description="Answer/back side")
    deck_id: str = Field(..., description="Parent deck ID")
    deck_name: str = Field(..., description="Parent deck name")
    step: int = Field(..., description="Current SRS step")
    review_count: int = Field(..., description="Total reviews so far")

    model_config = {"from_attributes": True}


class DueCardsResponse(BaseModel):
    """Response for due cards query."""

    cards: List[FlashcardDue] = Field(..., description="Cards due for review")
    total_due: int = Field(..., description="Total number of due cards")


class BulkCreateResponse(BaseModel):
    """Response for bulk card creation."""

    created: int = Field(..., description="Number of cards created")
    flashcards: List[FlashcardRead] = Field(..., description="Created flashcards")


# ═══════════════════════════════════════════════════════════════════════════
# REVIEW SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class ReviewRequest(BaseModel):
    """DTO for submitting a flashcard review."""

    rating: ReviewRating = Field(
        ...,
        description="Review rating: hard, good, or easy",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "rating": "good",
            }
        }
    }


class ReviewResponse(BaseModel):
    """Response after submitting a review."""

    flashcard_id: str = Field(..., description="Reviewed flashcard ID")
    new_step: int = Field(..., description="New SRS step after review")
    next_review_at: datetime = Field(..., description="Next scheduled review time")
    interval_display: str = Field(..., description="Human-readable interval")
    review_count: int = Field(..., description="Updated review count")


# ═══════════════════════════════════════════════════════════════════════════
# AI GENERATION SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class GenerateRequest(BaseModel):
    """DTO for AI flashcard generation request."""

    topic: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Topic to generate cards about",
    )
    content: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="Source content to generate cards from",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "topic": "Object-Oriented Programming",
                "content": "OOP is a programming paradigm based on objects...",
            }
        }
    }


class GeneratedCard(BaseModel):
    """A single AI-generated card (for preview)."""

    front: str = Field(..., description="Generated question")
    back: str = Field(..., description="Generated answer")


class GenerateResponse(BaseModel):
    """Response with AI-generated cards for preview."""

    cards: List[GeneratedCard] = Field(..., description="Generated cards for review")
    topic: str = Field(..., description="Topic the cards were generated for")


# ═══════════════════════════════════════════════════════════════════════════
# ERROR SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# TIMELINE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class TimelinePeriod(BaseModel):
    """A time period with its flashcards."""

    period: str = Field(..., description="Period label (today, tomorrow, this_week, later)")
    count: int = Field(..., description="Number of cards in this period")
    cards: List[FlashcardDue] = Field(default_factory=list, description="Flashcards due in this period")


class TimelineResponse(BaseModel):
    """Response for timeline query showing upcoming reviews."""

    periods: List[TimelinePeriod] = Field(..., description="Review periods with cards")
    total_due: int = Field(..., description="Total cards due now")
    total_upcoming: int = Field(..., description="Total upcoming cards")


class FlashcardError(BaseModel):
    """Error response for flashcard operations."""

    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "Flashcard not found",
                "code": "FLASHCARD_NOT_FOUND",
            }
        }
    }


# Update forward references
DeckDetail.model_rebuild()
FlashcardBulkCreate.model_rebuild()
