"""
Flashcards repository - Data Access Layer for decks and flashcards.
Handles all database operations for Deck and Flashcard entities.
All operations filter by user_id for security.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.flashcards.models import Deck, Flashcard
from app.flashcards.schemas import DeckCreate, DeckUpdate, FlashcardCreate, FlashcardUpdate
from app.flashcards.srs import SRSUpdate, get_initial_srs_state
from app.core.exceptions import DeckNotFoundError, FlashcardNotFoundError

logger = logging.getLogger(__name__)


class DeckRepository:
    """Repository for Deck CRUD operations with user filtering."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, deck_data: DeckCreate, user_id: str) -> Deck:
        """
        Create a new deck for a user.

        Args:
            deck_data: Deck creation DTO
            user_id: Owner user ID

        Returns:
            Created Deck entity
        """
        deck = Deck(
            id=str(uuid4()),
            name=deck_data.name,
            description=deck_data.description,
            user_id=user_id,
            topic_id=deck_data.topic_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(deck)
        await self.db.flush()

        logger.info(f"[DeckRepository] Created deck: {deck.id} - {deck.name} for user: {user_id}")
        return deck

    async def get_by_id(
        self,
        deck_id: str,
        user_id: Optional[str] = None,
        with_flashcards: bool = False,
        verify_ownership: bool = True,
    ) -> Deck:
        """
        Get a deck by its ID.

        Args:
            deck_id: Deck UUID
            user_id: User ID for ownership verification
            with_flashcards: Whether to eagerly load flashcards
            verify_ownership: Whether to verify user ownership

        Returns:
            Deck entity

        Raises:
            DeckNotFoundError: If deck not found
            PermissionError: If deck doesn't belong to user
        """
        stmt = select(Deck).where(Deck.id == deck_id)

        if with_flashcards:
            stmt = stmt.options(selectinload(Deck.flashcards))

        result = await self.db.execute(stmt)
        deck = result.scalar_one_or_none()

        if deck is None:
            raise DeckNotFoundError(f"Deck not found: {deck_id}")

        if verify_ownership and user_id is not None and deck.user_id != user_id:
            raise PermissionError(f"Deck {deck_id} does not belong to user {user_id}")

        return deck

    async def get_all(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Deck]:
        """
        Get all decks for a user with pagination.

        Args:
            user_id: User ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of Deck entities belonging to the user
        """
        stmt = (
            select(Deck)
            .where(Deck.user_id == user_id)
            .order_by(Deck.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def count(self, user_id: str) -> int:
        """Count total number of decks for a user."""
        stmt = select(func.count()).select_from(Deck).where(Deck.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def get_card_counts(self, user_id: str) -> Dict[str, int]:
        """
        Get card counts for all decks of a user.

        Returns:
            Dict mapping deck_id to card_count
        """
        stmt = (
            select(Deck.id, func.count(Flashcard.id).label("card_count"))
            .outerjoin(Flashcard, Flashcard.deck_id == Deck.id)
            .where(Deck.user_id == user_id)
            .group_by(Deck.id)
        )

        result = await self.db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def get_due_counts(self, user_id: str) -> Dict[str, int]:
        """
        Get due card counts for all decks of a user.

        Returns:
            Dict mapping deck_id to due_count
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(Deck.id, func.count(Flashcard.id).label("due_count"))
            .outerjoin(
                Flashcard,
                (Flashcard.deck_id == Deck.id) & (Flashcard.next_review_at <= now)
            )
            .where(Deck.user_id == user_id)
            .group_by(Deck.id)
        )

        result = await self.db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def update(
        self,
        deck_id: str,
        deck_data: DeckUpdate,
        user_id: str,
    ) -> Deck:
        """
        Update a deck.

        Args:
            deck_id: Deck UUID
            deck_data: Update data
            user_id: User ID for ownership verification

        Returns:
            Updated Deck entity
        """
        deck = await self.get_by_id(deck_id, user_id=user_id, verify_ownership=True)

        if deck_data.name is not None:
            deck.name = deck_data.name
        if deck_data.description is not None:
            deck.description = deck_data.description if deck_data.description else None
        if deck_data.topic_id is not None:
            # Empty string means unlink, otherwise set the topic_id
            deck.topic_id = deck_data.topic_id if deck_data.topic_id else None

        deck.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(f"[DeckRepository] Updated deck: {deck.id}")
        return deck

    async def delete(self, deck_id: str, user_id: str) -> bool:
        """
        Delete a deck by its ID.

        Args:
            deck_id: Deck UUID
            user_id: User ID for ownership verification

        Returns:
            True if deleted
        """
        deck = await self.get_by_id(deck_id, user_id=user_id, verify_ownership=True)
        await self.db.delete(deck)
        await self.db.flush()

        logger.info(f"[DeckRepository] Deleted deck: {deck_id}")
        return True

    async def verify_ownership(self, deck_id: str, user_id: str) -> bool:
        """Verify that a deck belongs to a user."""
        stmt = (
            select(func.count())
            .select_from(Deck)
            .where(Deck.id == deck_id)
            .where(Deck.user_id == user_id)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one() > 0


class FlashcardRepository:
    """Repository for Flashcard CRUD operations with user filtering."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, flashcard_data: FlashcardCreate, user_id: str) -> Flashcard:
        """
        Create a new flashcard.

        Args:
            flashcard_data: Flashcard creation DTO
            user_id: Owner user ID

        Returns:
            Created Flashcard entity
        """
        step, next_review_at, interval_minutes = get_initial_srs_state()

        flashcard = Flashcard(
            id=str(uuid4()),
            front_content=flashcard_data.front_content,
            back_content=flashcard_data.back_content,
            deck_id=flashcard_data.deck_id,
            user_id=user_id,
            step=step,
            next_review_at=next_review_at,
            interval_minutes=interval_minutes,
            ease_factor=2.5,
            review_count=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(flashcard)
        await self.db.flush()

        logger.info(f"[FlashcardRepository] Created flashcard: {flashcard.id} in deck: {flashcard.deck_id}")
        return flashcard

    async def bulk_create(
        self,
        deck_id: str,
        cards: List[Dict[str, str]],
        user_id: str,
    ) -> List[Flashcard]:
        """
        Bulk create flashcards.

        Args:
            deck_id: Parent deck ID
            cards: List of dicts with 'front' and 'back' keys
            user_id: Owner user ID

        Returns:
            List of created Flashcard entities
        """
        step, next_review_at, interval_minutes = get_initial_srs_state()
        now = datetime.now(timezone.utc)

        flashcards = []
        for card in cards:
            flashcard = Flashcard(
                id=str(uuid4()),
                front_content=card["front"],
                back_content=card["back"],
                deck_id=deck_id,
                user_id=user_id,
                step=step,
                next_review_at=next_review_at,
                interval_minutes=interval_minutes,
                ease_factor=2.5,
                review_count=0,
                created_at=now,
                updated_at=now,
            )
            self.db.add(flashcard)
            flashcards.append(flashcard)

        await self.db.flush()

        logger.info(f"[FlashcardRepository] Bulk created {len(flashcards)} flashcards in deck: {deck_id}")
        return flashcards

    async def get_by_id(
        self,
        flashcard_id: str,
        user_id: Optional[str] = None,
        verify_ownership: bool = True,
    ) -> Flashcard:
        """
        Get a flashcard by its ID.

        Args:
            flashcard_id: Flashcard UUID
            user_id: User ID for ownership verification
            verify_ownership: Whether to verify user ownership

        Returns:
            Flashcard entity

        Raises:
            FlashcardNotFoundError: If flashcard not found
            PermissionError: If flashcard doesn't belong to user
        """
        stmt = select(Flashcard).where(Flashcard.id == flashcard_id)

        result = await self.db.execute(stmt)
        flashcard = result.scalar_one_or_none()

        if flashcard is None:
            raise FlashcardNotFoundError(f"Flashcard not found: {flashcard_id}")

        if verify_ownership and user_id is not None and flashcard.user_id != user_id:
            raise PermissionError(f"Flashcard {flashcard_id} does not belong to user {user_id}")

        return flashcard

    async def get_due_cards(
        self,
        user_id: str,
        limit: int = 20,
        deck_id: Optional[str] = None,
    ) -> Sequence[Flashcard]:
        """
        Get flashcards that are due for review.

        Uses the composite index (user_id, next_review_at) for efficiency.

        Args:
            user_id: User ID to filter by
            limit: Maximum number of cards to return
            deck_id: Optional deck ID to filter by

        Returns:
            List of due Flashcard entities with deck relationship loaded
        """
        now = datetime.now(timezone.utc)

        stmt = (
            select(Flashcard)
            .options(selectinload(Flashcard.deck))
            .where(Flashcard.user_id == user_id)
            .where(Flashcard.next_review_at <= now)
            .order_by(Flashcard.next_review_at.asc())
            .limit(limit)
        )

        if deck_id:
            stmt = stmt.where(Flashcard.deck_id == deck_id)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def count_due_cards(self, user_id: str, deck_id: Optional[str] = None) -> int:
        """Count total due cards for a user."""
        now = datetime.now(timezone.utc)

        stmt = (
            select(func.count())
            .select_from(Flashcard)
            .where(Flashcard.user_id == user_id)
            .where(Flashcard.next_review_at <= now)
        )

        if deck_id:
            stmt = stmt.where(Flashcard.deck_id == deck_id)

        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def update(
        self,
        flashcard_id: str,
        flashcard_data: FlashcardUpdate,
        user_id: str,
    ) -> Flashcard:
        """
        Update flashcard content (no SRS reset).

        Args:
            flashcard_id: Flashcard UUID
            flashcard_data: Update data
            user_id: User ID for ownership verification

        Returns:
            Updated Flashcard entity
        """
        flashcard = await self.get_by_id(flashcard_id, user_id=user_id, verify_ownership=True)

        if flashcard_data.front_content is not None:
            flashcard.front_content = flashcard_data.front_content
        if flashcard_data.back_content is not None:
            flashcard.back_content = flashcard_data.back_content

        flashcard.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(f"[FlashcardRepository] Updated flashcard: {flashcard.id}")
        return flashcard

    async def update_srs(
        self,
        flashcard_id: str,
        srs_update: SRSUpdate,
        user_id: str,
    ) -> Flashcard:
        """
        Update flashcard SRS state after a review.

        Args:
            flashcard_id: Flashcard UUID
            srs_update: SRS calculation result
            user_id: User ID for ownership verification

        Returns:
            Updated Flashcard entity
        """
        flashcard = await self.get_by_id(flashcard_id, user_id=user_id, verify_ownership=True)

        flashcard.step = srs_update.step
        flashcard.next_review_at = srs_update.next_review_at
        flashcard.interval_minutes = srs_update.interval_minutes
        flashcard.review_count = srs_update.review_count
        flashcard.last_reviewed_at = datetime.now(timezone.utc)
        flashcard.updated_at = datetime.now(timezone.utc)

        await self.db.flush()

        logger.info(
            f"[FlashcardRepository] Updated SRS for flashcard: {flashcard.id}, "
            f"step={srs_update.step}, next_review={srs_update.next_review_at}"
        )
        return flashcard

    async def delete(self, flashcard_id: str, user_id: str) -> bool:
        """
        Delete a flashcard by its ID.

        Args:
            flashcard_id: Flashcard UUID
            user_id: User ID for ownership verification

        Returns:
            True if deleted
        """
        flashcard = await self.get_by_id(flashcard_id, user_id=user_id, verify_ownership=True)
        await self.db.delete(flashcard)
        await self.db.flush()

        logger.info(f"[FlashcardRepository] Deleted flashcard: {flashcard_id}")
        return True

    async def verify_ownership(self, flashcard_id: str, user_id: str) -> bool:
        """Verify that a flashcard belongs to a user."""
        stmt = (
            select(func.count())
            .select_from(Flashcard)
            .where(Flashcard.id == flashcard_id)
            .where(Flashcard.user_id == user_id)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one() > 0

    async def get_all_cards(
        self,
        user_id: str,
    ) -> Sequence[Flashcard]:
        """
        Get all flashcards for a user for timeline view.

        Args:
            user_id: User ID to filter by

        Returns:
            List of Flashcard entities with deck relationship loaded, ordered by next_review_at
        """
        stmt = (
            select(Flashcard)
            .options(selectinload(Flashcard.deck))
            .where(Flashcard.user_id == user_id)
            .order_by(Flashcard.next_review_at.asc())
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()
