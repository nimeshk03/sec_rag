"""
API module for SEC Filing RAG Safety System.

Provides FastAPI REST endpoints for safety checks and filing management.
"""

from .main import app

__all__ = ["app"]
