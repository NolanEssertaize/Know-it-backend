"""
Analysis module - Text analysis using OpenAI GPT-4.
Analyzes transcribed text and provides structured feedback.
"""

from app.analysis.router import router as analysis_router

__all__ = ["analysis_router"]
