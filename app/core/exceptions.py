"""
Custom exceptions for the application.
"""

from fastapi import HTTPException, status


class KnowItException(Exception):
    """Base exception for KnowIt application."""

    def __init__(self, message: str = "An error occurred"):
        self.message = message
        super().__init__(self.message)


# ═══════════════════════════════════════════════════════════════════════════
# AUTHENTICATION EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════


class AuthenticationError(KnowItException):
    """Raised when authentication fails."""
    pass


class InvalidTokenError(KnowItException):
    """Raised when a JWT token is invalid or expired."""
    pass


class UserAlreadyExistsError(KnowItException):
    """Raised when trying to register with an existing email."""
    pass


class UserNotFoundError(KnowItException):
    """Raised when user is not found."""
    pass


class OAuthError(KnowItException):
    """Raised when OAuth authentication fails."""
    pass


# ═══════════════════════════════════════════════════════════════════════════
# TRANSCRIPTION & ANALYSIS EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════


class TranscriptionError(KnowItException):
    """Raised when audio transcription fails."""
    pass


class AnalysisError(KnowItException):
    """Raised when text analysis fails."""
    pass


# ═══════════════════════════════════════════════════════════════════════════
# TOPIC & SESSION EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════


class TopicNotFoundError(KnowItException):
    """Raised when a topic is not found."""
    pass


class TopicAlreadyExistsError(KnowItException):
    """Raised when a topic with the same title already exists."""
    pass


class SessionNotFoundError(KnowItException):
    """Raised when a session is not found."""
    pass


# ═══════════════════════════════════════════════════════════════════════════
# EXTERNAL API EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════


class ExternalAPIError(KnowItException):
    """Raised when an external API call fails."""
    pass


# ═══════════════════════════════════════════════════════════════════════════
# HTTP EXCEPTION HELPERS
# ═══════════════════════════════════════════════════════════════════════════


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


def unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden(detail: str = "Access denied") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)