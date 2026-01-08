"""
FastAPI dependencies for dependency injection.
"""

from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db

# Type aliases for cleaner dependency injection
DBSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def get_openai_client() -> AsyncGenerator:
    """
    Provides an OpenAI client instance.
    Can be extended for connection pooling or rate limiting.
    """
    from openai import AsyncOpenAI

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        yield client
    finally:
        await client.close()


OpenAIClient = Annotated[any, Depends(get_openai_client)]
