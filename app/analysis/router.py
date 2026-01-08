"""
Analysis router - API endpoints for text analysis.
"""

import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AnalysisError, ExternalAPIError, SessionNotFoundError
from app.database import get_db
from app.analysis.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisError as AnalysisErrorSchema,
    SessionRead,
)
from app.analysis.service import AnalysisService, get_analysis_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.post(
    "",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze transcribed text",
    description="Analyze text using GPT-4 and return structured feedback with valid points, corrections, and missing concepts.",
    responses={
        200: {"model": AnalysisResponse, "description": "Successful analysis"},
        400: {"model": AnalysisErrorSchema, "description": "Invalid request"},
        500: {"model": AnalysisErrorSchema, "description": "Analysis failed"},
        503: {"model": AnalysisErrorSchema, "description": "External API unavailable"},
    },
)
async def analyze_text(
    request: AnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    """
    Analyze transcribed text and optionally save the session.

    The analysis returns:
    - valid: Points correctly mentioned by the user
    - corrections: Factual errors or inaccuracies
    - missing: Key concepts the user forgot

    If topic_id is provided, the session will be saved to the database.

    Args:
        request: Analysis request with text and topic title

    Returns:
        AnalysisResponse with structured analysis
    """
    logger.info(
        f"[AnalysisRouter] Received analysis request for topic: {request.topic_title}"
    )

    try:
        service = get_analysis_service(db)
        result = await service.analyze_text(request)

        logger.info(
            f"[AnalysisRouter] Analysis successful"
            + (f", session_id: {result.session_id}" if result.session_id else "")
        )

        return result

    except AnalysisError as e:
        logger.error(f"[AnalysisRouter] Analysis error: {e.message}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": e.message, "code": "ANALYSIS_FAILED"},
        )

    except ExternalAPIError as e:
        logger.error(f"[AnalysisRouter] External API error: {e.message}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": e.message, "code": "EXTERNAL_API_ERROR"},
        )

    except Exception as e:
        logger.exception(f"[AnalysisRouter] Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An unexpected error occurred", "code": "INTERNAL_ERROR"},
        )


@router.get(
    "/sessions/{session_id}",
    response_model=SessionRead,
    status_code=status.HTTP_200_OK,
    summary="Get session by ID",
    description="Retrieve a specific analysis session by its ID.",
    responses={
        200: {"model": SessionRead, "description": "Session found"},
        404: {"model": AnalysisErrorSchema, "description": "Session not found"},
    },
)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    """
    Get a specific session by ID.

    Args:
        session_id: Session UUID

    Returns:
        Session data with analysis results
    """
    logger.info(f"[AnalysisRouter] Getting session: {session_id}")

    try:
        service = get_analysis_service(db)
        return await service.get_session(session_id)

    except SessionNotFoundError as e:
        logger.warning(f"[AnalysisRouter] Session not found: {session_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": e.message, "code": "SESSION_NOT_FOUND"},
        )

    except Exception as e:
        logger.exception(f"[AnalysisRouter] Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An unexpected error occurred", "code": "INTERNAL_ERROR"},
        )
