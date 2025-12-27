"""
Safety module for SEC Filing RAG System.

Provides earnings proximity checking and safety decision logic.
"""

from .earnings import (
    EarningsChecker,
    EarningsProximity,
)
from .checker import (
    SafetyChecker,
    SafetyDecision,
    SafetyThresholds,
    SafetyCheckResult,
)

__all__ = [
    "EarningsChecker",
    "EarningsProximity",
    "SafetyChecker",
    "SafetyDecision",
    "SafetyThresholds",
    "SafetyCheckResult",
]
