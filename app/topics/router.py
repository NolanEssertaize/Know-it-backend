"""
Topics router - API endpoints for topic management.
"""

import logging

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import TopicNotFoundError
from app.database import get_db
from app.topics.schemas import (
    TopicCreate,
    TopicDetail,
    TopicError,
    TopicList,
    TopicRead,
    TopicUpdate,
)
from app.topics.service import TopicService, get_topic_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/topics", tags=["Topics"])


@router.post(
    "",
    response_model=TopicRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new topic",
    description="Create a new learning topic.",
    responses={
        201: {"model": TopicRead, "description": "Topic created"},
        400: {"model": TopicError, "description": "Invalid request"},
    },
)
async def create_topic(
    topic_data: TopicCreate,
    db: AsyncSession = Depends(get_db),
) -> TopicRead:
    """
    Create a new learning topic.

    Args:
        topic_data: Topic creation data

    Returns:
        Created topic
    """
    logger.info(f"[TopicsRouter] Creating topic: {topic_data.title}")

    try:
        service = get_topic_service(db)
        return await service.create_topic(topic_data)

    except Exception as e:
        logger.exception(f"[TopicsRouter] Error creating topic: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e), "code": "CREATE_FAILED"},
        )


@router.get(
    "",
    response_model=TopicList,
    status_code=status.HTTP_200_OK,
    summary="List all topics",
    description="Get a paginated list of all topics.",
    responses={
        200: {"model": TopicList, "description": "List of topics"},
    },
)
async def list_topics(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    db: AsyncSession = Depends(get_db),
) -> TopicList:
    """
    List all topics with pagination.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records

    Returns:
        List of topics with total count
    """
    logger.info(f"[TopicsRouter] Listing topics (skip={skip}, limit={limit})")

    service = get_topic_service(db)
    return await service.list_topics(skip=skip, limit=limit)


@router.get(
    "/{topic_id}",
    response_model=TopicDetail,
    status_code=status.HTTP_200_OK,
    summary="Get topic by ID",
    description="Get a specific topic with all its sessions.",
    responses={
        200: {"model": TopicDetail, "description": "Topic with sessions"},
        404: {"model": TopicError, "description": "Topic not found"},
    },
)
async def get_topic(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
) -> TopicDetail:
    """
    Get a specific topic with all sessions.

    Args:
        topic_id: Topic UUID

    Returns:
        Topic with all sessions
    """
    logger.info(f"[TopicsRouter] Getting topic: {topic_id}")

    try:
        service = get_topic_service(db)
        return await service.get_topic(topic_id)

    except TopicNotFoundError as e:
        logger.warning(f"[TopicsRouter] Topic not found: {topic_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": e.message, "code": "TOPIC_NOT_FOUND"},
        )


@router.patch(
    "/{topic_id}",
    response_model=TopicRead,
    status_code=status.HTTP_200_OK,
    summary="Update topic",
    description="Update a topic's title.",
    responses={
        200: {"model": TopicRead, "description": "Updated topic"},
        404: {"model": TopicError, "description": "Topic not found"},
    },
)
async def update_topic(
    topic_id: str,
    topic_data: TopicUpdate,
    db: AsyncSession = Depends(get_db),
) -> TopicRead:
    """
    Update a topic.

    Args:
        topic_id: Topic UUID
        topic_data: Update data

    Returns:
        Updated topic
    """
    logger.info(f"[TopicsRouter] Updating topic: {topic_id}")

    try:
        service = get_topic_service(db)
        return await service.update_topic(topic_id, topic_data)

    except TopicNotFoundError as e:
        logger.warning(f"[TopicsRouter] Topic not found: {topic_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": e.message, "code": "TOPIC_NOT_FOUND"},
        )


@router.delete(
    "/{topic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete topic",
    description="Delete a topic and all its sessions.",
    responses={
        204: {"description": "Topic deleted"},
        404: {"model": TopicError, "description": "Topic not found"},
    },
)
async def delete_topic(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a topic and all its sessions.

    Args:
        topic_id: Topic UUID
    """
    logger.info(f"[TopicsRouter] Deleting topic: {topic_id}")

    try:
        service = get_topic_service(db)
        await service.delete_topic(topic_id)

    except TopicNotFoundError as e:
        logger.warning(f"[TopicsRouter] Topic not found: {topic_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": e.message, "code": "TOPIC_NOT_FOUND"},
        )
