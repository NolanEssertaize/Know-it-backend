"""
Custom exceptions for the application.
"""

from fastapi import HTTPException, status


class KnowItException(Exception):
    """Base exception for KnowIt application."""

    def __init__(self, message: str = "An error occurred"):
        self.message = message
        super().__init__(self.message)


class TranscriptionError(KnowItException):
    """Raised when audio transcription fails."""

    pass


class AnalysisError(KnowItException):
    """Raised when text analysis fails."""

    pass


class TopicNotFoundError(KnowItException):
    """Raised when a topic is not found."""

    pass


class SessionNotFoundError(KnowItException):
    """Raised when a session is not found."""

    pass


class ExternalAPIError(KnowItException):
    """Raised when an external API call fails."""

    pass


# HTTP Exceptions (for direct use in routes)
def not_found(detail: str = "Resource not found") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def bad_request(detail: str = "Invalid request") -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def internal_error(detail: str = "Internal server error") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
    )


def service_unavailable(detail: str = "Service temporarily unavailable") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail
    )
