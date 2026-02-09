"""
Flashcards service - Business logic for deck and flashcard management.
Includes AI-powered card generation and SRS review processing.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import DeckNotFoundError, FlashcardNotFoundError, ExternalAPIError
from app.flashcards.models import Deck, Flashcard
from app.flashcards.repository import DeckRepository, FlashcardRepository
from app.flashcards.schemas import (
    BulkCreateResponse,
    DeckCreate,
    DeckDetail,
    DeckList,
    DeckRead,
    DeckUpdate,
    DueCardsResponse,
    FlashcardBulkCreate,
    FlashcardCreate,
    FlashcardDue,
    FlashcardRead,
    FlashcardUpdate,
    GeneratedCard,
    GenerateRequest,
    GenerateResponse,
    ReviewRequest,
    ReviewResponse,
    TimelinePeriod,
    TimelineResponse,
)
from app.flashcards.srs import calculate_next_review, get_interval_display, INTERVALS_MINUTES, PERIOD_LABELS

logger = logging.getLogger(__name__)
settings = get_settings()

# AI Generation prompt template
GENERATION_PROMPT = """You are an expert flashcard creator for spaced repetition learning.
Topic: {topic}
Content: {content}

Generate flashcards in JSON format:
{{"cards": [{{"front": "Question?", "back": "Answer"}}]}}

Rules:
- Generate an APPROPRIATE number of cards based on content richness (1-20 cards)
- Short content (few sentences) = fewer cards (1-3)
- Medium content = moderate cards (4-7)
- Rich, detailed content = more cards (8-20)
- Only create cards for meaningful, distinct concepts - don't pad with filler
- Test UNDERSTANDING, not memorization
- Use Feynman technique (explain simply)
- Vary question types: definitions, comparisons, applications, examples
- Questions should be clear and specific
- Answers should be concise but complete
- Do not include the topic name in every question

Respond ONLY with the JSON, no additional text."""


class FlashcardService:
    """Service for flashcard business logic with AI generation."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.deck_repo = DeckRepository(db)
        self.flashcard_repo = FlashcardRepository(db)
        self._client: Optional[AsyncOpenAI] = None

    @property
    def openai_client(self) -> AsyncOpenAI:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    # ═══════════════════════════════════════════════════════════════════════
    # DECK OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════

    async def create_deck(self, deck_data: DeckCreate, user_id: str) -> DeckRead:
        """Create a new deck for a user."""
        logger.info(f"[FlashcardService] Creating deck: {deck_data.name} for user: {user_id}")

        deck = await self.deck_repo.create(deck_data, user_id=user_id)
        return self._deck_to_read_dto(deck, card_count=0, due_count=0)

    async def get_deck(self, deck_id: str, user_id: str) -> DeckDetail:
        """Get a deck with all its flashcards."""
        logger.info(f"[FlashcardService] Getting deck: {deck_id} for user: {user_id}")

        deck = await self.deck_repo.get_by_id(
            deck_id,
            user_id=user_id,
            with_flashcards=True,
            verify_ownership=True,
        )
        return self._deck_to_detail_dto(deck)

    async def list_decks(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> DeckList:
        """List all decks for a user with card and due counts."""
        logger.info(f"[FlashcardService] Listing decks for user: {user_id}")

        decks = await self.deck_repo.get_all(user_id=user_id, skip=skip, limit=limit)
        total = await self.deck_repo.count(user_id=user_id)

        card_counts = await self.deck_repo.get_card_counts(user_id=user_id)
        due_counts = await self.deck_repo.get_due_counts(user_id=user_id)

        return DeckList(
            decks=[
                self._deck_to_read_dto(
                    d,
                    card_count=card_counts.get(d.id, 0),
                    due_count=due_counts.get(d.id, 0),
                )
                for d in decks
            ],
            total=total,
        )

    async def update_deck(
        self,
        deck_id: str,
        deck_data: DeckUpdate,
        user_id: str,
    ) -> DeckRead:
        """Update a deck."""
        logger.info(f"[FlashcardService] Updating deck: {deck_id} for user: {user_id}")

        deck = await self.deck_repo.update(deck_id, deck_data, user_id=user_id)

        card_counts = await self.deck_repo.get_card_counts(user_id=user_id)
        due_counts = await self.deck_repo.get_due_counts(user_id=user_id)

        return self._deck_to_read_dto(
            deck,
            card_count=card_counts.get(deck.id, 0),
            due_count=due_counts.get(deck.id, 0),
        )

    async def delete_deck(self, deck_id: str, user_id: str) -> bool:
        """Delete a deck and all its flashcards."""
        logger.info(f"[FlashcardService] Deleting deck: {deck_id} for user: {user_id}")
        return await self.deck_repo.delete(deck_id, user_id=user_id)

    # ═══════════════════════════════════════════════════════════════════════
    # FLASHCARD OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════

    async def create_flashcard(
        self,
        flashcard_data: FlashcardCreate,
        user_id: str,
    ) -> FlashcardRead:
        """Create a single flashcard."""
        logger.info(f"[FlashcardService] Creating flashcard in deck: {flashcard_data.deck_id}")

        # Verify deck ownership
        await self.deck_repo.get_by_id(
            flashcard_data.deck_id,
            user_id=user_id,
            verify_ownership=True,
        )

        flashcard = await self.flashcard_repo.create(flashcard_data, user_id=user_id)
        return self._flashcard_to_read_dto(flashcard)

    async def bulk_create_flashcards(
        self,
        bulk_data: FlashcardBulkCreate,
        user_id: str,
    ) -> BulkCreateResponse:
        """Bulk create flashcards from approved AI-generated cards."""
        logger.info(f"[FlashcardService] Bulk creating {len(bulk_data.cards)} flashcards in deck: {bulk_data.deck_id}")

        # Verify deck ownership
        await self.deck_repo.get_by_id(
            bulk_data.deck_id,
            user_id=user_id,
            verify_ownership=True,
        )

        cards = [{"front": c.front, "back": c.back, "delay": c.delay} for c in bulk_data.cards]
        flashcards = await self.flashcard_repo.bulk_create(
            deck_id=bulk_data.deck_id,
            cards=cards,
            user_id=user_id,
        )

        return BulkCreateResponse(
            created=len(flashcards),
            flashcards=[self._flashcard_to_read_dto(f) for f in flashcards],
        )

    async def get_due_cards(
        self,
        user_id: str,
        limit: int = 20,
        deck_id: Optional[str] = None,
    ) -> DueCardsResponse:
        """Get flashcards that are due for review."""
        logger.info(f"[FlashcardService] Getting due cards for user: {user_id}")

        if deck_id:
            # Verify deck ownership
            await self.deck_repo.get_by_id(deck_id, user_id=user_id, verify_ownership=True)

        flashcards = await self.flashcard_repo.get_due_cards(
            user_id=user_id,
            limit=limit,
            deck_id=deck_id,
        )
        total_due = await self.flashcard_repo.count_due_cards(
            user_id=user_id,
            deck_id=deck_id,
        )

        return DueCardsResponse(
            cards=[self._flashcard_to_due_dto(f) for f in flashcards],
            total_due=total_due,
        )

    async def get_timeline(self, user_id: str) -> TimelineResponse:
        """
        Get flashcard review timeline grouped by SRS periods.

        Periods match the SRS intervals:
        - 1_day, 1_week, 1_month, 3_months, 6_months, 12_months, 18_months, 24_months, 36_months

        Cards are grouped by their current step (which determines their interval).
        """
        logger.info(f"[FlashcardService] Getting timeline for user: {user_id}")

        now = datetime.now(timezone.utc)

        # Get all flashcards for the user
        flashcards = await self.flashcard_repo.get_all_cards(user_id=user_id)

        # Group cards by their step (period)
        period_cards: dict[str, list[FlashcardDue]] = {label: [] for label in PERIOD_LABELS}
        due_cards: list[FlashcardDue] = []

        for f in flashcards:
            dto = self._flashcard_to_due_dto(f)
            # Cards due now go to a special "due" category
            if f.next_review_at <= now:
                due_cards.append(dto)
            else:
                # Group by step
                period_label = PERIOD_LABELS[f.step] if f.step < len(PERIOD_LABELS) else PERIOD_LABELS[-1]
                period_cards[period_label].append(dto)

        # Build periods list (only include non-empty periods)
        periods = []

        # Add due cards first
        if due_cards:
            periods.append(TimelinePeriod(period="due", count=len(due_cards), cards=due_cards))

        # Add each SRS period
        for label in PERIOD_LABELS:
            cards = period_cards[label]
            if cards:
                periods.append(TimelinePeriod(period=label, count=len(cards), cards=cards))

        total_upcoming = sum(len(cards) for cards in period_cards.values())

        return TimelineResponse(
            periods=periods,
            total_due=len(due_cards),
            total_upcoming=total_upcoming,
        )

    async def get_deck_timeline(self, deck_id: str, user_id: str) -> TimelineResponse:
        """
        Get flashcard review timeline for a specific deck, grouped by SRS periods.
        Same logic as the global timeline but filtered to one deck.
        """
        logger.info(f"[FlashcardService] Getting deck timeline: {deck_id} for user: {user_id}")

        # Verify deck exists and belongs to user
        await self.deck_repo.get_by_id(deck_id, user_id=user_id, verify_ownership=True)

        now = datetime.now(timezone.utc)

        flashcards = await self.flashcard_repo.get_all_cards(user_id=user_id, deck_id=deck_id)

        period_cards: dict[str, list[FlashcardDue]] = {label: [] for label in PERIOD_LABELS}
        due_cards: list[FlashcardDue] = []

        for f in flashcards:
            dto = self._flashcard_to_due_dto(f)
            if f.next_review_at <= now:
                due_cards.append(dto)
            else:
                period_label = PERIOD_LABELS[f.step] if f.step < len(PERIOD_LABELS) else PERIOD_LABELS[-1]
                period_cards[period_label].append(dto)

        periods = []
        if due_cards:
            periods.append(TimelinePeriod(period="due", count=len(due_cards), cards=due_cards))

        for label in PERIOD_LABELS:
            cards = period_cards[label]
            if cards:
                periods.append(TimelinePeriod(period=label, count=len(cards), cards=cards))

        total_upcoming = sum(len(cards) for cards in period_cards.values())

        return TimelineResponse(
            periods=periods,
            total_due=len(due_cards),
            total_upcoming=total_upcoming,
        )

    async def review_flashcard(
        self,
        flashcard_id: str,
        review_data: ReviewRequest,
        user_id: str,
    ) -> ReviewResponse:
        """Process a flashcard review and update SRS state."""
        logger.info(f"[FlashcardService] Reviewing flashcard: {flashcard_id}, rating: {review_data.rating}")

        # Get current flashcard state
        flashcard = await self.flashcard_repo.get_by_id(
            flashcard_id,
            user_id=user_id,
            verify_ownership=True,
        )

        # Calculate new SRS state
        srs_update = calculate_next_review(
            current_step=flashcard.step,
            review_count=flashcard.review_count,
            rating=review_data.rating,
        )

        # Update flashcard
        updated = await self.flashcard_repo.update_srs(
            flashcard_id=flashcard_id,
            srs_update=srs_update,
            user_id=user_id,
        )

        return ReviewResponse(
            flashcard_id=updated.id,
            new_step=updated.step,
            next_review_at=updated.next_review_at,
            interval_display=get_interval_display(updated.interval_minutes),
            review_count=updated.review_count,
        )

    async def update_flashcard(
        self,
        flashcard_id: str,
        flashcard_data: FlashcardUpdate,
        user_id: str,
    ) -> FlashcardRead:
        """Update flashcard content (no SRS reset)."""
        logger.info(f"[FlashcardService] Updating flashcard: {flashcard_id}")

        flashcard = await self.flashcard_repo.update(
            flashcard_id,
            flashcard_data,
            user_id=user_id,
        )
        return self._flashcard_to_read_dto(flashcard)

    async def delete_flashcard(self, flashcard_id: str, user_id: str) -> bool:
        """Delete a flashcard."""
        logger.info(f"[FlashcardService] Deleting flashcard: {flashcard_id}")
        return await self.flashcard_repo.delete(flashcard_id, user_id=user_id)

    # ═══════════════════════════════════════════════════════════════════════
    # AI GENERATION
    # ═══════════════════════════════════════════════════════════════════════

    async def generate_flashcards(
        self,
        request: GenerateRequest,
        user_id: str,
    ) -> GenerateResponse:
        """
        Generate flashcards using AI.

        The AI determines the appropriate number of cards based on content richness.
        Returns preview cards that are NOT automatically saved.
        User must approve and save via bulk_create.
        """
        logger.info(f"[FlashcardService] Generating flashcards for topic: {request.topic}")

        try:
            prompt = GENERATION_PROMPT.format(
                topic=request.topic,
                content=request.content,
            )

            response = await self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "You are an expert flashcard creator."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=2000,
            )

            content = response.choices[0].message.content
            if not content:
                raise ExternalAPIError("Empty response from AI")

            data = json.loads(content)
            cards = data.get("cards", [])

            generated = [
                GeneratedCard(front=c.get("front", ""), back=c.get("back", ""))
                for c in cards
                if c.get("front") and c.get("back")
            ]

            logger.info(f"[FlashcardService] Generated {len(generated)} flashcards")

            return GenerateResponse(
                cards=generated,
                topic=request.topic,
            )

        except json.JSONDecodeError as e:
            logger.error(f"[FlashcardService] Failed to parse AI response: {e}")
            raise ExternalAPIError("Failed to parse AI-generated cards")
        except Exception as e:
            logger.error(f"[FlashcardService] AI generation failed: {e}")
            if "api" in str(e).lower() or "openai" in str(e).lower():
                raise ExternalAPIError(f"AI service error: {str(e)}")
            raise

    # ═══════════════════════════════════════════════════════════════════════
    # DTO TRANSFORMATIONS
    # ═══════════════════════════════════════════════════════════════════════

    def _deck_to_read_dto(
        self,
        deck: Deck,
        card_count: int = 0,
        due_count: int = 0,
    ) -> DeckRead:
        """Convert Deck model to DeckRead DTO."""
        return DeckRead(
            id=deck.id,
            name=deck.name,
            description=deck.description,
            topic_id=deck.topic_id,
            card_count=card_count,
            due_count=due_count,
            created_at=deck.created_at,
            updated_at=deck.updated_at,
        )

    def _deck_to_detail_dto(self, deck: Deck) -> DeckDetail:
        """Convert Deck model to DeckDetail DTO with flashcards."""
        flashcards = [
            self._flashcard_to_read_dto(f)
            for f in (deck.flashcards or [])
        ]

        return DeckDetail(
            id=deck.id,
            name=deck.name,
            description=deck.description,
            topic_id=deck.topic_id,
            created_at=deck.created_at,
            updated_at=deck.updated_at,
            flashcards=flashcards,
        )

    def _flashcard_to_read_dto(self, flashcard: Flashcard) -> FlashcardRead:
        """Convert Flashcard model to FlashcardRead DTO."""
        return FlashcardRead(
            id=flashcard.id,
            front_content=flashcard.front_content,
            back_content=flashcard.back_content,
            deck_id=flashcard.deck_id,
            step=flashcard.step,
            next_review_at=flashcard.next_review_at,
            interval_minutes=flashcard.interval_minutes,
            review_count=flashcard.review_count,
            last_reviewed_at=flashcard.last_reviewed_at,
            created_at=flashcard.created_at,
            updated_at=flashcard.updated_at,
        )

    def _flashcard_to_due_dto(self, flashcard: Flashcard) -> FlashcardDue:
        """Convert Flashcard model to FlashcardDue DTO."""
        return FlashcardDue(
            id=flashcard.id,
            front_content=flashcard.front_content,
            back_content=flashcard.back_content,
            deck_id=flashcard.deck_id,
            deck_name=flashcard.deck.name if flashcard.deck else "Unknown",
            step=flashcard.step,
            review_count=flashcard.review_count,
            next_review_at=flashcard.next_review_at,
        )


def get_flashcard_service(db: AsyncSession) -> FlashcardService:
    """Factory function for FlashcardService."""
    return FlashcardService(db)
