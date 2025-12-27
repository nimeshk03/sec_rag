"""
Safety Checker Core Logic.

Implements intelligent PROCEED/REDUCE/VETO decisions based on:
- Risk scores from SEC filings
- Earnings proximity
- Allocation size
- Critical events
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import hashlib
import json

from src.data.store import SupabaseStore, SafetyLog
from src.safety.earnings import EarningsChecker
from src.retrieval.hybrid import HybridRetriever


class SafetyDecision(str, Enum):
    """Safety decision outcomes."""
    PROCEED = "PROCEED"
    REDUCE = "REDUCE"
    VETO = "VETO"


@dataclass
class SafetyThresholds:
    """Configurable thresholds for safety decisions."""
    veto_risk_score: float = 8.0
    reduce_risk_score: float = 6.0
    critical_event_severity: float = 9.0
    earnings_warning_days: int = 3
    high_allocation_pct: float = 15.0
    
    def __post_init__(self):
        """Validate thresholds."""
        if self.veto_risk_score <= self.reduce_risk_score:
            raise ValueError("VETO threshold must be higher than REDUCE threshold")
        if self.earnings_warning_days < 0:
            raise ValueError("Earnings warning days must be non-negative")
        if self.high_allocation_pct <= 0 or self.high_allocation_pct > 100:
            raise ValueError("High allocation percentage must be between 0 and 100")


@dataclass
class SafetyCheckResult:
    """Result of a safety check."""
    decision: SafetyDecision
    ticker: str
    risk_score: float
    reasoning: str
    earnings_warning: Optional[str] = None
    critical_events: Optional[List[str]] = None
    allocation_warning: Optional[str] = None
    cache_hit: bool = False
    retrieved_chunks: Optional[List[Dict[str, Any]]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/API response."""
        return {
            "decision": self.decision.value,
            "ticker": self.ticker,
            "risk_score": self.risk_score,
            "reasoning": self.reasoning,
            "earnings_warning": self.earnings_warning,
            "critical_events": self.critical_events,
            "allocation_warning": self.allocation_warning,
            "cache_hit": self.cache_hit,
            "retrieved_chunks": self.retrieved_chunks,
        }


class SafetyChecker:
    """
    Core safety checker that makes PROCEED/REDUCE/VETO decisions.
    
    Decision Logic:
    - VETO: Risk score ≥8 OR critical event (severity ≥9)
    - REDUCE: Risk score ≥6 OR (earnings within 3 days AND high allocation)
    - PROCEED: Otherwise
    """
    
    def __init__(
        self,
        store: Optional[SupabaseStore] = None,
        earnings_checker: Optional[EarningsChecker] = None,
        retriever: Optional[HybridRetriever] = None,
        thresholds: Optional[SafetyThresholds] = None,
    ):
        """
        Initialize SafetyChecker.
        
        Args:
            store: Database store (lazy-loaded if not provided)
            earnings_checker: Earnings proximity checker (lazy-loaded if not provided)
            retriever: Hybrid retriever for SEC data (lazy-loaded if not provided)
            thresholds: Safety decision thresholds (uses defaults if not provided)
        """
        self._store = store
        self._earnings_checker = earnings_checker
        self._retriever = retriever
        self.thresholds = thresholds or SafetyThresholds()
    
    @property
    def store(self) -> SupabaseStore:
        """Lazy-load store."""
        if self._store is None:
            self._store = SupabaseStore()
        return self._store
    
    @property
    def earnings_checker(self) -> EarningsChecker:
        """Lazy-load earnings checker."""
        if self._earnings_checker is None:
            self._earnings_checker = EarningsChecker(
                store=self.store,
                threshold_days=self.thresholds.earnings_warning_days
            )
        return self._earnings_checker
    
    @property
    def retriever(self) -> HybridRetriever:
        """Lazy-load retriever."""
        if self._retriever is None:
            self._retriever = HybridRetriever(store=self.store)
        return self._retriever
    
    def check_safety(
        self,
        ticker: str,
        allocation_pct: float,
        reference_date: Optional[date] = None,
        use_cache: bool = True,
    ) -> SafetyCheckResult:
        """
        Perform safety check for a ticker and allocation.
        
        Args:
            ticker: Stock ticker symbol
            allocation_pct: Proposed allocation percentage (0-100)
            reference_date: Reference date for checks (defaults to today)
            use_cache: Whether to use cached results
        
        Returns:
            SafetyCheckResult with decision and reasoning
        """
        if reference_date is None:
            reference_date = date.today()
        
        # Check cache first
        if use_cache:
            cache_key = self._generate_cache_key(ticker, allocation_pct)
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                cached_result.cache_hit = True
                return cached_result
        
        # Step 1: Check earnings proximity
        earnings_result = self.earnings_checker.check_earnings_proximity(
            ticker, reference_date=reference_date
        )
        
        # Step 2: Retrieve and analyze SEC filings
        risk_analysis = self._analyze_risks(ticker, reference_date)
        
        # Step 3: Make decision based on all factors
        decision_result = self._make_decision(
            ticker=ticker,
            allocation_pct=allocation_pct,
            risk_score=risk_analysis["risk_score"],
            critical_events=risk_analysis["critical_events"],
            earnings_result=earnings_result,
            retrieved_chunks=risk_analysis["chunks"],
        )
        
        # Step 4: Log decision
        self._log_decision(decision_result, reference_date)
        
        # Step 5: Cache result
        if use_cache:
            cache_key = self._generate_cache_key(ticker, allocation_pct)
            self._cache_result(cache_key, decision_result, risk_analysis["risk_score"])
        
        return decision_result
    
    def _analyze_risks(
        self,
        ticker: str,
        reference_date: date,
    ) -> Dict[str, Any]:
        """
        Analyze risks from SEC filings.
        
        Args:
            ticker: Stock ticker
            reference_date: Reference date for analysis
        
        Returns:
            Dictionary with risk_score, critical_events, and chunks
        """
        # Retrieve relevant SEC filing chunks
        query = "litigation risks regulatory compliance financial risks operational risks"
        results = self.retriever.retrieve_for_safety_check(
            query=query,
            ticker=ticker,
            max_results=10,
        )
        
        if not results:
            # No filings found - conservative approach
            return {
                "risk_score": 5.0,  # Medium risk when no data available
                "critical_events": [],
                "chunks": [],
            }
        
        # Analyze retrieved chunks for risk indicators
        risk_score = self._calculate_risk_score(results)
        critical_events = self._extract_critical_events(results)
        
        return {
            "risk_score": risk_score,
            "critical_events": critical_events,
            "chunks": [
                {
                    "content": r.content[:200],
                    "section": r.section_name,
                    "filing_type": r.filing_type,
                    "score": r.combined_score,
                }
                for r in results[:5]  # Top 5 chunks
            ],
        }
    
    def _calculate_risk_score(self, results: List[Any]) -> float:
        """
        Calculate overall risk score from retrieved chunks.
        
        Uses a simple heuristic based on risk keywords and filing sections.
        In production, this would use LLM analysis (GPT-4o-mini).
        
        Args:
            results: List of retrieval results
        
        Returns:
            Risk score from 0-10
        """
        if not results:
            return 5.0
        
        risk_keywords = {
            "litigation": 2.0,
            "lawsuit": 2.0,
            "regulatory": 1.5,
            "investigation": 2.5,
            "violation": 2.0,
            "penalty": 1.5,
            "fraud": 3.0,
            "breach": 2.0,
            "default": 2.5,
            "bankruptcy": 3.0,
            "material weakness": 2.5,
            "going concern": 3.0,
            "restatement": 2.0,
        }
        
        total_risk = 0.0
        chunk_count = 0
        
        for result in results[:10]:  # Analyze top 10 chunks
            content_lower = result.content.lower()
            chunk_risk = 0.0
            
            # Check for risk keywords
            for keyword, weight in risk_keywords.items():
                if keyword in content_lower:
                    chunk_risk += weight
            
            # Weight by section importance (Item 1A is most important)
            section_weight = 1.5 if result.section_name == "1A" else 1.0
            chunk_risk *= section_weight
            
            total_risk += chunk_risk
            chunk_count += 1
        
        # Normalize to 0-10 scale
        avg_risk = total_risk / max(chunk_count, 1)
        normalized_risk = min(avg_risk, 10.0)
        
        return round(normalized_risk, 1)
    
    def _extract_critical_events(self, results: List[Any]) -> List[str]:
        """
        Extract critical events from retrieved chunks.
        
        Critical events are those with severity ≥9.
        
        Args:
            results: List of retrieval results
        
        Returns:
            List of critical event descriptions
        """
        critical_keywords = [
            "bankruptcy",
            "going concern",
            "material weakness",
            "fraud",
            "criminal investigation",
            "delisting",
            "default",
        ]
        
        critical_events = []
        
        for result in results[:10]:
            content_lower = result.content.lower()
            for keyword in critical_keywords:
                if keyword in content_lower:
                    # Extract context around keyword
                    idx = content_lower.find(keyword)
                    start = max(0, idx - 50)
                    end = min(len(result.content), idx + 100)
                    context = result.content[start:end].strip()
                    critical_events.append(f"{keyword.title()}: {context}")
                    break  # One event per chunk
        
        return critical_events[:3]  # Return top 3 critical events
    
    def _make_decision(
        self,
        ticker: str,
        allocation_pct: float,
        risk_score: float,
        critical_events: List[str],
        earnings_result: Any,
        retrieved_chunks: List[Dict[str, Any]],
    ) -> SafetyCheckResult:
        """
        Make final safety decision based on all factors.
        
        Decision Logic:
        1. VETO if: risk_score >= 8 OR critical event exists
        2. REDUCE if: risk_score >= 6 OR (earnings within threshold AND high allocation)
        3. PROCEED otherwise
        
        Args:
            ticker: Stock ticker
            allocation_pct: Proposed allocation percentage
            risk_score: Calculated risk score (0-10)
            critical_events: List of critical events found
            earnings_result: EarningsProximity result
            retrieved_chunks: Retrieved SEC filing chunks
        
        Returns:
            SafetyCheckResult with decision and reasoning
        """
        reasons = []
        
        # Check for VETO conditions
        if critical_events:
            return SafetyCheckResult(
                decision=SafetyDecision.VETO,
                ticker=ticker,
                risk_score=risk_score,
                reasoning=f"Critical event detected: {critical_events[0][:100]}",
                critical_events=critical_events,
                earnings_warning=earnings_result.warning_message,
                retrieved_chunks=retrieved_chunks,
            )
        
        if risk_score >= self.thresholds.veto_risk_score:
            return SafetyCheckResult(
                decision=SafetyDecision.VETO,
                ticker=ticker,
                risk_score=risk_score,
                reasoning=f"High risk score ({risk_score}) exceeds VETO threshold ({self.thresholds.veto_risk_score})",
                earnings_warning=earnings_result.warning_message,
                retrieved_chunks=retrieved_chunks,
            )
        
        # Check for REDUCE conditions
        if risk_score >= self.thresholds.reduce_risk_score:
            reasons.append(f"Elevated risk score ({risk_score})")
        
        is_high_allocation = allocation_pct > self.thresholds.high_allocation_pct
        
        if earnings_result.is_within_threshold and is_high_allocation:
            reasons.append(
                f"Earnings in {earnings_result.days_until_earnings} days with high allocation ({allocation_pct:.1f}%)"
            )
        
        if reasons:
            return SafetyCheckResult(
                decision=SafetyDecision.REDUCE,
                ticker=ticker,
                risk_score=risk_score,
                reasoning="; ".join(reasons),
                earnings_warning=earnings_result.warning_message,
                allocation_warning=f"High allocation: {allocation_pct:.1f}%" if is_high_allocation else None,
                retrieved_chunks=retrieved_chunks,
            )
        
        # PROCEED - all checks passed
        proceed_reasons = [f"Low risk score ({risk_score})"]
        if not earnings_result.is_within_threshold and earnings_result.has_upcoming_earnings:
            proceed_reasons.append(
                f"Earnings in {earnings_result.days_until_earnings} days (outside threshold)"
            )
        
        return SafetyCheckResult(
            decision=SafetyDecision.PROCEED,
            ticker=ticker,
            risk_score=risk_score,
            reasoning="; ".join(proceed_reasons),
            earnings_warning=earnings_result.warning_message if earnings_result.has_upcoming_earnings else None,
            retrieved_chunks=retrieved_chunks,
        )
    
    def _generate_cache_key(self, ticker: str, allocation_pct: float) -> str:
        """
        Generate cache key with 5% allocation buckets.
        
        This ensures similar allocations share cache entries.
        
        Args:
            ticker: Stock ticker
            allocation_pct: Allocation percentage
        
        Returns:
            Cache key string
        """
        # Bucket allocation to nearest 5%
        bucketed_allocation = round(allocation_pct / 5.0) * 5.0
        
        # Create cache key
        key_data = f"{ticker}:{bucketed_allocation}"
        cache_key = hashlib.md5(key_data.encode()).hexdigest()
        
        return cache_key
    
    def _get_cached_result(self, cache_key: str) -> Optional[SafetyCheckResult]:
        """
        Retrieve cached safety check result.
        
        Args:
            cache_key: Cache key
        
        Returns:
            Cached SafetyCheckResult or None
        """
        # This would query the cache table in production
        # For now, return None (cache miss)
        return None
    
    def _cache_result(
        self,
        cache_key: str,
        result: SafetyCheckResult,
        risk_score: float,
    ) -> None:
        """
        Cache safety check result with dynamic TTL.
        
        TTL Logic:
        - High risk (≥8): 1 hour
        - Medium risk (6-7.9): 4 hours
        - Low risk (<6): 24 hours
        
        Args:
            cache_key: Cache key
            result: Safety check result
            risk_score: Risk score for TTL calculation
        """
        # Determine TTL based on risk score
        if risk_score >= 8.0:
            ttl_hours = 1
        elif risk_score >= 6.0:
            ttl_hours = 4
        else:
            ttl_hours = 24
        
        # This would insert into cache table in production
        # For now, just pass (no-op)
        pass
    
    def _log_decision(
        self,
        result: SafetyCheckResult,
        reference_date: date,
    ) -> None:
        """
        Log safety decision to database.
        
        Args:
            result: Safety check result
            reference_date: Reference date for the check
        """
        # Note: SafetyLog expects proposed_allocation and current_allocation
        # For now, we'll use placeholder values since we don't track current allocation
        log_entry = SafetyLog(
            ticker=result.ticker,
            proposed_allocation=0.0,  # Placeholder - would come from allocation_pct in full implementation
            current_allocation=0.0,   # Placeholder - would come from portfolio state
            decision=result.decision.value,
            reasoning=result.reasoning,
            risk_score=int(result.risk_score),
            timestamp=datetime.now(),
        )
        
        try:
            self.store.log_safety_decision(log_entry)
        except Exception as e:
            # Log error but don't fail the safety check
            print(f"Warning: Failed to log safety decision: {e}")
