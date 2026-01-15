"""
Topics router - API endpoints for topic management.
All routes require authentication and filter by user.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import TopicNotFoundError
from app.database import get_db
from app.dependencies import CurrentActiveUser
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
    description="Create a new learning topic for the authenticated user.",
    responses={
        201: {"model": TopicRead, "description": "Topic created"},
        400: {"model": TopicError, "description": "Invalid request"},
        401: {"description": "Not authenticated"},
        403: {"description": "User account is deactivated"},
    },
)
async def create_topic(
        topic_data: TopicCreate,
        current_user: CurrentActiveUser,
        db: AsyncSession = Depends(get_db),
) -> TopicRead:
    """
    Create a new learning topic.

    The topic will be associated with the authenticated user.

    Requires authentication.

    Args:
        topic_data: Topic creation data
        current_user: Authenticated user (injected by dependency)

    Returns:
        Created topic
    """
    logger.info(f"[TopicsRouter] Creating topic: {topic_data.title}, user: {current_user.id}")

    try:
        service = get_topic_service(db)
        return await service.create_topic(topic_data, user_id=current_user.id)

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
    description="Get a paginated list of all topics belonging to the authenticated user.",
    responses={
        200: {"model": TopicList, "description": "List of topics"},
        401: {"description": "Not authenticated"},
        403: {"description": "User account is deactivated"},
    },
)
async def list_topics(
        current_user: CurrentActiveUser,
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
        db: AsyncSession = Depends(get_db),
) -> TopicList:
    """
    List all topics for the authenticated user with pagination.

    Only returns topics belonging to the current user.

    Requires authentication.

    Args:
        current_user: Authenticated user (injected by dependency)
        skip: Number of records to skip
        limit: Maximum number of records

    Returns:
        List of topics with total count
    """
    logger.info(f"[TopicsRouter] Listing topics (skip={skip}, limit={limit}), user: {current_user.id}")

    service = get_topic_service(db)
    return await service.list_topics(user_id=current_user.id, skip=skip, limit=limit)


@router.get(
    "/{topic_id}",
    response_model=TopicDetail,
    status_code=status.HTTP_200_OK,
    summary="Get topic by ID",
    description="Get a specific topic with all its sessions. Topic must belong to the authenticated user.",
    responses={
        200: {"model": TopicDetail, "description": "Topic with sessions"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied - topic does not belong to user"},
        404: {"model": TopicError, "description": "Topic not found"},
    },
)
async def get_topic(
        topic_id: str,
        current_user: CurrentActiveUser,
        db: AsyncSession = Depends(get_db),
) -> TopicDetail:
    """
    Get a specific topic with all sessions.

    Topic must belong to the authenticated user.

    Requires authentication.

    Args:
        topic_id: Topic UUID
        current_user: Authenticated user (injected by dependency)

    Returns:
        Topic with all sessions
    """
    logger.info(f"[TopicsRouter] Getting topic: {topic_id}, user: {current_user.id}")

    try:
        service = get_topic_service(db)
        return await service.get_topic(topic_id, user_id=current_user.id)

    except TopicNotFoundError as e:
        logger.warning(f"[TopicsRouter] Topic not found: {topic_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": e.message, "code": "TOPIC_NOT_FOUND"},
        )

    except PermissionError as e:
        logger.warning(f"[TopicsRouter] Access denied to topic {topic_id} for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - topic does not belong to user",
        )


@router.patch(
    "/{topic_id}",
    response_model=TopicRead,
    status_code=status.HTTP_200_OK,
    summary="Update topic",
    description="Update a topic's title. Topic must belong to the authenticated user.",
    responses={
        200: {"model": TopicRead, "description": "Updated topic"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied - topic does not belong to user"},
        404: {"model": TopicError, "description": "Topic not found"},
    },
)
async def update_topic(
        topic_id: str,
        topic_data: TopicUpdate,
        current_user: CurrentActiveUser,
        db: AsyncSession = Depends(get_db),
) -> TopicRead:
    """
    Update a topic.

    Topic must belong to the authenticated user.

    Requires authentication.

    Args:
        topic_id: Topic UUID
        topic_data: Update data
        current_user: Authenticated user (injected by dependency)

    Returns:
        Updated topic
    """
    logger.info(f"[TopicsRouter] Updating topic: {topic_id}, user: {current_user.id}")

    try:
        service = get_topic_service(db)
        return await service.update_topic(topic_id, topic_data, user_id=current_user.id)

    except TopicNotFoundError as e:
        logger.warning(f"[TopicsRouter] Topic not found: {topic_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": e.message, "code": "TOPIC_NOT_FOUND"},
        )

    except PermissionError as e:
        logger.warning(f"[TopicsRouter] Access denied to topic {topic_id} for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - topic does not belong to user",
        )


@router.delete(
    "/{topic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete topic",
    description="Delete a topic and all its sessions. Topic must belong to the authenticated user.",
    responses={
        204: {"description": "Topic deleted"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied - topic does not belong to user"},
        404: {"model": TopicError, "description": "Topic not found"},
    },
)
async def delete_topic(
        topic_id: str,
        current_user: CurrentActiveUser,
        db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a topic and all its sessions.

    Topic must belong to the authenticated user.

    Requires authentication.

    Args:
        topic_id: Topic UUID
        current_user: Authenticated user (injected by dependency)
    """
    logger.info(f"[TopicsRouter] Deleting topic: {topic_id}, user: {current_user.id}")

    try:
        service = get_topic_service(db)
        await service.delete_topic(topic_id, user_id=current_user.id)

    except TopicNotFoundError as e:
        logger.warning(f"[TopicsRouter] Topic not found: {topic_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": e.message, "code": "TOPIC_NOT_FOUND"},
        )

    except PermissionError as e:
        logger.warning(f"[TopicsRouter] Access denied to topic {topic_id} for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - topic does not belong to user",
        )