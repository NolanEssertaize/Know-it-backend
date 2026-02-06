"""
KnowIt Backend - Main FastAPI Application

Entry point for the API server.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import create_tables
from app.rate_limit import limiter

from app.auth import auth_router
from app.transcription import transcription_router
from app.analysis import analysis_router
from app.topics import topics_router
from app.flashcards import decks_router, flashcards_router
from app.subscriptions import subscriptions_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Runs startup and shutdown logic.
    """
    # Startup
    logger.info(f"[Startup] Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"[Startup] Debug mode: {settings.debug}")

    # Create database tables
    try:
        await create_tables()
        logger.info("[Startup] Database tables created/verified")
    except Exception as e:
        logger.error(f"[Startup] Database initialization failed: {e}")
        # Don't fail startup - tables might already exist

    yield

    # Shutdown
    logger.info("[Shutdown] Application shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    KnowIt Backend API - Learning through voice and AI feedback.

    ## Features

    * **Authentication** - User registration, login, and Google OAuth
    * **Transcription** - Convert audio recordings to text using OpenAI Whisper
    * **Analysis** - Analyze transcribed text with GPT-4 for structured feedback
    * **Topics** - Manage learning topics and sessions

    ## Architecture

    Built with FastAPI, SQLAlchemy 2.0 (async), and PostgreSQL.
    Uses a 3-layer architecture: Router → Service → Repository.
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions globally."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "code": "INTERNAL_ERROR"},
    )


# Health check endpoints
@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API info."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# API v1 routes
API_V1_PREFIX = "/api/v1"


@app.get(f"{API_V1_PREFIX}/health", tags=["Health"])
async def api_health():
    """API health check with version."""
    return {
        "status": "healthy",
        "version": settings.app_version,
    }


# Include routers
app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(transcription_router, prefix=API_V1_PREFIX)
app.include_router(analysis_router, prefix=API_V1_PREFIX)
app.include_router(topics_router, prefix=API_V1_PREFIX)
app.include_router(decks_router, prefix=API_V1_PREFIX)
app.include_router(flashcards_router, prefix=API_V1_PREFIX)
app.include_router(subscriptions_router, prefix=API_V1_PREFIX)