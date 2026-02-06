"""
Flashcards router - API endpoints for deck and flashcard management.
All routes require authentication and filter by user.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DeckNotFoundError, FlashcardNotFoundError, ExternalAPIError
from app.database import get_db
from app.dependencies import CurrentActiveUser
from app.flashcards.schemas import (
    BulkCreateResponse,
    DeckCreate,
    DeckDetail,
    DeckList,
    DeckRead,
    DeckUpdate,
    DueCardsResponse,
    FlashcardBulkCreate,
    FlashcardError,
    FlashcardRead,
    FlashcardUpdate,
    GenerateRequest,
    GenerateResponse,
    ReviewRequest,
    ReviewResponse,
    TimelineResponse,
)
from app.flashcards.service import FlashcardService, get_flashcard_service

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# DECK ROUTER
# ═══════════════════════════════════════════════════════════════════════════

decks_router = APIRouter(prefix="/decks", tags=["Decks"])


@decks_router.post(
    "",
    response_model=DeckRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new deck",
    description="Create a new flashcard deck for the authenticated user.",
    responses={
        201: {"model": DeckRead, "description": "Deck created"},
        401: {"description": "Not authenticated"},
        403: {"description": "User account is deactivated"},
    },
)
async def create_deck(
    deck_data: DeckCreate,
    current_user: CurrentActiveUser,
    db: AsyncSession = Depends(get_db),
) -> DeckRead:
    """Create a new flashcard deck."""
    logger.info(f"[DecksRouter] Creating deck: {deck_data.name}, user: {current_user.id}")

    try:
        service = get_flashcard_service(db)
        return await service.create_deck(deck_data, user_id=current_user.id)
    except Exception as e:
        logger.exception(f"[DecksRouter] Error creating deck: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e), "code": "CREATE_FAILED"},
        )


@decks_router.get(
    "",
    response_model=DeckList,
    status_code=status.HTTP_200_OK,
    summary="List all decks",
    description="Get a paginated list of all decks belonging to the authenticated user.",
    responses={
        200: {"model": DeckList, "description": "List of decks"},
        401: {"description": "Not authenticated"},
    },
)
async def list_decks(
    current_user: CurrentActiveUser,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    db: AsyncSession = Depends(get_db),
) -> DeckList:
    """List all decks for the authenticated user."""
    logger.info(f"[DecksRouter] Listing decks (skip={skip}, limit={limit}), user: {current_user.id}")

    service = get_flashcard_service(db)
    return await service.list_decks(user_id=current_user.id, skip=skip, limit=limit)


@decks_router.get(
    "/{deck_id}",
    response_model=DeckDetail,
    status_code=status.HTTP_200_OK,
    summary="Get deck by ID",
    description="Get a specific deck with all its flashcards.",
    responses={
        200: {"model": DeckDetail, "description": "Deck with flashcards"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied"},
        404: {"model": FlashcardError, "description": "Deck not found"},
    },
)
async def get_deck(
    deck_id: str,
    current_user: CurrentActiveUser,
    db: AsyncSession = Depends(get_db),
) -> DeckDetail:
    """Get a specific deck with all flashcards."""
    logger.info(f"[DecksRouter] Getting deck: {deck_id}, user: {current_user.id}")

    try:
        service = get_flashcard_service(db)
        return await service.get_deck(deck_id, user_id=current_user.id)
    except DeckNotFoundError as e:
        logger.warning(f"[DecksRouter] Deck not found: {deck_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": e.message, "code": "DECK_NOT_FOUND"},
        )
    except PermissionError:
        logger.warning(f"[DecksRouter] Access denied to deck {deck_id} for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - deck does not belong to user",
        )


@decks_router.patch(
    "/{deck_id}",
    response_model=DeckRead,
    status_code=status.HTTP_200_OK,
    summary="Update deck",
    description="Update a deck's name or description.",
    responses={
        200: {"model": DeckRead, "description": "Updated deck"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied"},
        404: {"model": FlashcardError, "description": "Deck not found"},
    },
)
async def update_deck(
    deck_id: str,
    deck_data: DeckUpdate,
    current_user: CurrentActiveUser,
    db: AsyncSession = Depends(get_db),
) -> DeckRead:
    """Update a deck."""
    logger.info(f"[DecksRouter] Updating deck: {deck_id}, user: {current_user.id}")

    try:
        service = get_flashcard_service(db)
        return await service.update_deck(deck_id, deck_data, user_id=current_user.id)
    except DeckNotFoundError as e:
        logger.warning(f"[DecksRouter] Deck not found: {deck_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": e.message, "code": "DECK_NOT_FOUND"},
        )
    except PermissionError:
        logger.warning(f"[DecksRouter] Access denied to deck {deck_id} for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - deck does not belong to user",
        )


@decks_router.delete(
    "/{deck_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete deck",
    description="Delete a deck and all its flashcards.",
    responses={
        204: {"description": "Deck deleted"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied"},
        404: {"model": FlashcardError, "description": "Deck not found"},
    },
)
async def delete_deck(
    deck_id: str,
    current_user: CurrentActiveUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a deck and all its flashcards."""
    logger.info(f"[DecksRouter] Deleting deck: {deck_id}, user: {current_user.id}")

    try:
        service = get_flashcard_service(db)
        await service.delete_deck(deck_id, user_id=current_user.id)
    except DeckNotFoundError as e:
        logger.warning(f"[DecksRouter] Deck not found: {deck_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": e.message, "code": "DECK_NOT_FOUND"},
        )
    except PermissionError:
        logger.warning(f"[DecksRouter] Access denied to deck {deck_id} for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - deck does not belong to user",
        )


# ═══════════════════════════════════════════════════════════════════════════
# FLASHCARD ROUTER
# ═══════════════════════════════════════════════════════════════════════════

flashcards_router = APIRouter(prefix="/flashcards", tags=["Flashcards"])


@flashcards_router.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate flashcards with AI",
    description="Generate flashcards from content using AI. The AI determines the appropriate number of cards based on content richness (1-20 cards). Returns preview cards that are NOT automatically saved.",
    responses={
        200: {"model": GenerateResponse, "description": "Generated cards for preview"},
        401: {"description": "Not authenticated"},
        503: {"model": FlashcardError, "description": "AI service unavailable"},
    },
)
async def generate_flashcards(
    request: GenerateRequest,
    current_user: CurrentActiveUser,
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    """Generate flashcards using AI. The AI determines the appropriate count based on content richness."""
    logger.info(f"[FlashcardsRouter] Generating cards for topic: {request.topic}, user: {current_user.id}")

    try:
        service = get_flashcard_service(db)
        return await service.generate_flashcards(request, user_id=current_user.id)
    except ExternalAPIError as e:
        logger.error(f"[FlashcardsRouter] AI generation failed: {e.message}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": e.message, "code": "AI_SERVICE_ERROR"},
        )


@flashcards_router.post(
    "/bulk",
    response_model=BulkCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create flashcards",
    description="Create multiple flashcards at once (typically after AI generation review).",
    responses={
        201: {"model": BulkCreateResponse, "description": "Cards created"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied to deck"},
        404: {"model": FlashcardError, "description": "Deck not found"},
    },
)
async def bulk_create_flashcards(
    bulk_data: FlashcardBulkCreate,
    current_user: CurrentActiveUser,
    db: AsyncSession = Depends(get_db),
) -> BulkCreateResponse:
    """Bulk create flashcards from approved cards."""
    logger.info(f"[FlashcardsRouter] Bulk creating {len(bulk_data.cards)} cards, user: {current_user.id}")

    try:
        service = get_flashcard_service(db)
        return await service.bulk_create_flashcards(bulk_data, user_id=current_user.id)
    except DeckNotFoundError as e:
        logger.warning(f"[FlashcardsRouter] Deck not found: {bulk_data.deck_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": e.message, "code": "DECK_NOT_FOUND"},
        )
    except PermissionError:
        logger.warning(f"[FlashcardsRouter] Access denied to deck {bulk_data.deck_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - deck does not belong to user",
        )


@flashcards_router.get(
    "/timeline",
    response_model=TimelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Get review timeline",
    description="Get flashcards grouped by review periods (today, tomorrow, this week, later).",
    responses={
        200: {"model": TimelineResponse, "description": "Timeline with grouped cards"},
        401: {"description": "Not authenticated"},
    },
)
async def get_timeline(
    current_user: CurrentActiveUser,
    db: AsyncSession = Depends(get_db),
) -> TimelineResponse:
    """Get flashcard review timeline grouped by periods."""
    logger.info(f"[FlashcardsRouter] Getting timeline for user: {current_user.id}")

    service = get_flashcard_service(db)
    return await service.get_timeline(user_id=current_user.id)


@flashcards_router.get(
    "/due",
    response_model=DueCardsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get cards due for review",
    description="Get flashcards that are due for review, optionally filtered by deck.",
    responses={
        200: {"model": DueCardsResponse, "description": "Due cards"},
        401: {"description": "Not authenticated"},
    },
)
async def get_due_cards(
    current_user: CurrentActiveUser,
    limit: int = Query(20, ge=1, le=100, description="Maximum cards to return"),
    deck_id: str | None = Query(None, description="Optional deck ID to filter by"),
    db: AsyncSession = Depends(get_db),
) -> DueCardsResponse:
    """Get flashcards due for review."""
    logger.info(f"[FlashcardsRouter] Getting due cards, user: {current_user.id}, deck: {deck_id}")

    try:
        service = get_flashcard_service(db)
        return await service.get_due_cards(
            user_id=current_user.id,
            limit=limit,
            deck_id=deck_id,
        )
    except DeckNotFoundError as e:
        logger.warning(f"[FlashcardsRouter] Deck not found: {deck_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": e.message, "code": "DECK_NOT_FOUND"},
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - deck does not belong to user",
        )


@flashcards_router.post(
    "/{flashcard_id}/review",
    response_model=ReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit flashcard review",
    description="Submit a review rating for a flashcard and update its SRS state.",
    responses={
        200: {"model": ReviewResponse, "description": "Review processed"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied"},
        404: {"model": FlashcardError, "description": "Flashcard not found"},
    },
)
async def review_flashcard(
    flashcard_id: str,
    review_data: ReviewRequest,
    current_user: CurrentActiveUser,
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """Submit a flashcard review."""
    logger.info(f"[FlashcardsRouter] Reviewing flashcard: {flashcard_id}, rating: {review_data.rating}")

    try:
        service = get_flashcard_service(db)
        return await service.review_flashcard(
            flashcard_id,
            review_data,
            user_id=current_user.id,
        )
    except FlashcardNotFoundError as e:
        logger.warning(f"[FlashcardsRouter] Flashcard not found: {flashcard_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": e.message, "code": "FLASHCARD_NOT_FOUND"},
        )
    except PermissionError:
        logger.warning(f"[FlashcardsRouter] Access denied to flashcard {flashcard_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - flashcard does not belong to user",
        )


@flashcards_router.patch(
    "/{flashcard_id}",
    response_model=FlashcardRead,
    status_code=status.HTTP_200_OK,
    summary="Update flashcard content",
    description="Update flashcard content without resetting SRS progress.",
    responses={
        200: {"model": FlashcardRead, "description": "Updated flashcard"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied"},
        404: {"model": FlashcardError, "description": "Flashcard not found"},
    },
)
async def update_flashcard(
    flashcard_id: str,
    flashcard_data: FlashcardUpdate,
    current_user: CurrentActiveUser,
    db: AsyncSession = Depends(get_db),
) -> FlashcardRead:
    """Update flashcard content (no SRS reset)."""
    logger.info(f"[FlashcardsRouter] Updating flashcard: {flashcard_id}, user: {current_user.id}")

    try:
        service = get_flashcard_service(db)
        return await service.update_flashcard(
            flashcard_id,
            flashcard_data,
            user_id=current_user.id,
        )
    except FlashcardNotFoundError as e:
        logger.warning(f"[FlashcardsRouter] Flashcard not found: {flashcard_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": e.message, "code": "FLASHCARD_NOT_FOUND"},
        )
    except PermissionError:
        logger.warning(f"[FlashcardsRouter] Access denied to flashcard {flashcard_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - flashcard does not belong to user",
        )


@flashcards_router.delete(
    "/{flashcard_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete flashcard",
    description="Delete a flashcard.",
    responses={
        204: {"description": "Flashcard deleted"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied"},
        404: {"model": FlashcardError, "description": "Flashcard not found"},
    },
)
async def delete_flashcard(
    flashcard_id: str,
    current_user: CurrentActiveUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a flashcard."""
    logger.info(f"[FlashcardsRouter] Deleting flashcard: {flashcard_id}, user: {current_user.id}")

    try:
        service = get_flashcard_service(db)
        await service.delete_flashcard(flashcard_id, user_id=current_user.id)
    except FlashcardNotFoundError as e:
        logger.warning(f"[FlashcardsRouter] Flashcard not found: {flashcard_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": e.message, "code": "FLASHCARD_NOT_FOUND"},
        )
    except PermissionError:
        logger.warning(f"[FlashcardsRouter] Access denied to flashcard {flashcard_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - flashcard does not belong to user",
        )
