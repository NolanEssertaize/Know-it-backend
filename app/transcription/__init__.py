"""
Transcription module - Audio to text using OpenAI Whisper.
"""

from app.transcription.router import router as transcription_router

__all__ = ["transcription_router"]
