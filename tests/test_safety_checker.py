"""
Unit tests for the Safety Checker Core Logic.

Tests cover:
- SafetyThresholds validation
- SafetyCheckResult dataclass
- SafetyChecker initialization
- Risk score calculation
- Critical event detection
- Decision logic (PROCEED/REDUCE/VETO)
- Cache key generation
- Decision logging
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch, call

from src.safety.checker import (
    SafetyChecker,
    SafetyDecision,
    SafetyThresholds,
    SafetyCheckResult,
)
from src.safety.earnings import EarningsProximity, EarningsEntry
from src.retrieval.hybrid import RetrievalResult


class TestSafetyThresholds:
    """Tests for SafetyThresholds dataclass."""
    
    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = SafetyThresholds()
        
        assert thresholds.veto_risk_score == 8.0
        assert thresholds.reduce_risk_score == 6.0
        assert thresholds.critical_event_severity == 9.0
        assert thresholds.earnings_warning_days == 3
        assert thresholds.high_allocation_pct == 15.0
    
    def test_custom_thresholds(self):
        """Test custom threshold values."""
        thresholds = SafetyThresholds(
            veto_risk_score=9.0,
            reduce_risk_score=7.0,
            earnings_warning_days=5,
            high_allocation_pct=20.0
        )
        
        assert thresholds.veto_risk_score == 9.0
        assert thresholds.reduce_risk_score == 7.0
        assert thresholds.earnings_warning_days == 5
        assert thresholds.high_allocation_pct == 20.0
    
    def test_invalid_thresholds(self):
        """Test validation of invalid thresholds."""
        # VETO must be higher than REDUCE
        with pytest.raises(ValueError, match="VETO threshold must be higher"):
            SafetyThresholds(veto_risk_score=6.0, reduce_risk_score=8.0)
        
        # Earnings days must be non-negative
        with pytest.raises(ValueError, match="must be non-negative"):
            SafetyThresholds(earnings_warning_days=-1)
        
        # Allocation percentage must be valid
        with pytest.raises(ValueError, match="between 0 and 100"):
            SafetyThresholds(high_allocation_pct=150.0)


class TestSafetyCheckResult:
    """Tests for SafetyCheckResult dataclass."""
    
    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = SafetyCheckResult(
            decision=SafetyDecision.REDUCE,
            ticker="AAPL",
            risk_score=6.5,
            reasoning="Elevated risk score",
            earnings_warning="Earnings in 2 days",
            critical_events=None,
            allocation_warning="High allocation: 18.0%",
            cache_hit=False,
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["decision"] == "REDUCE"
        assert result_dict["ticker"] == "AAPL"
        assert result_dict["risk_score"] == 6.5
        assert result_dict["reasoning"] == "Elevated risk score"
        assert result_dict["earnings_warning"] == "Earnings in 2 days"
        assert result_dict["allocation_warning"] == "High allocation: 18.0%"
        assert result_dict["cache_hit"] is False


class TestSafetyCheckerInitialization:
    """Tests for SafetyChecker initialization."""
    
    def test_default_initialization(self):
        """Test initialization with defaults."""
        checker = SafetyChecker()
        
        assert checker._store is None
        assert checker._earnings_checker is None
        assert checker._retriever is None
        assert checker.thresholds.veto_risk_score == 8.0
    
    def test_custom_thresholds(self):
        """Test initialization with custom thresholds."""
        thresholds = SafetyThresholds(veto_risk_score=9.0)
        checker = SafetyChecker(thresholds=thresholds)
        
        assert checker.thresholds.veto_risk_score == 9.0
    
    def test_with_injected_dependencies(self):
        """Test initialization with injected dependencies."""
        mock_store = MagicMock()
        mock_earnings = MagicMock()
        mock_retriever = MagicMock()
        
        checker = SafetyChecker(
            store=mock_store,
            earnings_checker=mock_earnings,
            retriever=mock_retriever,
        )
        
        assert checker._store is mock_store
        assert checker._earnings_checker is mock_earnings
        assert checker._retriever is mock_retriever


class TestRiskScoreCalculation:
    """Tests for risk score calculation."""
    
    def test_calculate_risk_score_no_results(self):
        """Test risk score when no results available."""
        checker = SafetyChecker()
        
        risk_score = checker._calculate_risk_score([])
        
        assert risk_score == 5.0  # Default medium risk
    
    def test_calculate_risk_score_with_keywords(self):
        """Test risk score calculation with risk keywords."""
        checker = SafetyChecker()
        
        # Create mock results with risk keywords
        mock_results = [
            MagicMock(
                content="The company faces significant litigation risks and ongoing lawsuits.",
                section_name="1A",
            ),
            MagicMock(
                content="Regulatory investigation into potential violations.",
                section_name="1A",
            ),
        ]
        
        risk_score = checker._calculate_risk_score(mock_results)
        
        # Should be elevated due to litigation, lawsuit, regulatory, investigation keywords
        assert risk_score > 5.0
    
    def test_calculate_risk_score_section_weighting(self):
        """Test that Item 1A sections are weighted higher."""
        checker = SafetyChecker()
        
        # Same content, different sections
        results_1a = [
            MagicMock(content="litigation risks", section_name="1A"),
        ]
        results_7 = [
            MagicMock(content="litigation risks", section_name="7"),
        ]
        
        score_1a = checker._calculate_risk_score(results_1a)
        score_7 = checker._calculate_risk_score(results_7)
        
        assert score_1a > score_7


class TestCriticalEventDetection:
    """Tests for critical event detection."""
    
    def test_extract_no_critical_events(self):
        """Test when no critical events are found."""
        checker = SafetyChecker()
        
        mock_results = [
            MagicMock(content="Normal business operations continue."),
        ]
        
        events = checker._extract_critical_events(mock_results)
        
        assert events == []
    
    def test_extract_critical_events(self):
        """Test extracting critical events."""
        checker = SafetyChecker()
        
        mock_results = [
            MagicMock(
                content="The company has identified a material weakness in internal controls."
            ),
            MagicMock(
                content="There is substantial doubt about the company's ability to continue as a going concern."
            ),
        ]
        
        events = checker._extract_critical_events(mock_results)
        
        assert len(events) == 2
        assert "material weakness" in events[0].lower()
        assert "going concern" in events[1].lower()
    
    def test_extract_critical_events_limit(self):
        """Test that only top 3 critical events are returned."""
        checker = SafetyChecker()
        
        mock_results = [
            MagicMock(content=f"Critical event {i}: bankruptcy") for i in range(10)
        ]
        
        events = checker._extract_critical_events(mock_results)
        
        assert len(events) == 3


class TestDecisionLogic:
    """Tests for safety decision logic."""
    
    def test_veto_on_high_risk_score(self):
        """Test VETO decision when risk score >= 8."""
        checker = SafetyChecker()
        
        earnings_result = EarningsProximity(
            ticker="AAPL",
            has_upcoming_earnings=False,
            threshold_days=3,
        )
        
        result = checker._make_decision(
            ticker="AAPL",
            allocation_pct=10.0,
            risk_score=8.5,
            critical_events=[],
            earnings_result=earnings_result,
            retrieved_chunks=[],
        )
        
        assert result.decision == SafetyDecision.VETO
        assert "High risk score" in result.reasoning
        assert result.risk_score == 8.5
    
    def test_veto_on_critical_event(self):
        """Test VETO decision when critical event exists."""
        checker = SafetyChecker()
        
        earnings_result = EarningsProximity(
            ticker="AAPL",
            has_upcoming_earnings=False,
            threshold_days=3,
        )
        
        result = checker._make_decision(
            ticker="AAPL",
            allocation_pct=10.0,
            risk_score=5.0,  # Low risk score
            critical_events=["Bankruptcy: Company filed for Chapter 11"],
            earnings_result=earnings_result,
            retrieved_chunks=[],
        )
        
        assert result.decision == SafetyDecision.VETO
        assert "Critical event detected" in result.reasoning
        assert result.critical_events is not None
    
    def test_reduce_on_medium_risk(self):
        """Test REDUCE decision when risk score >= 6."""
        checker = SafetyChecker()
        
        earnings_result = EarningsProximity(
            ticker="AAPL",
            has_upcoming_earnings=False,
            threshold_days=3,
        )
        
        result = checker._make_decision(
            ticker="AAPL",
            allocation_pct=10.0,
            risk_score=6.5,
            critical_events=[],
            earnings_result=earnings_result,
            retrieved_chunks=[],
        )
        
        assert result.decision == SafetyDecision.REDUCE
        assert "Elevated risk score" in result.reasoning
    
    def test_reduce_on_earnings_and_high_allocation(self):
        """Test REDUCE when earnings near and allocation high."""
        checker = SafetyChecker()
        
        earnings_result = EarningsProximity(
            ticker="AAPL",
            has_upcoming_earnings=True,
            days_until_earnings=2,
            earnings_date=date.today() + timedelta(days=2),
            is_within_threshold=True,
            threshold_days=3,
        )
        
        result = checker._make_decision(
            ticker="AAPL",
            allocation_pct=18.0,  # High allocation
            risk_score=4.0,  # Low risk
            critical_events=[],
            earnings_result=earnings_result,
            retrieved_chunks=[],
        )
        
        assert result.decision == SafetyDecision.REDUCE
        assert "Earnings in 2 days" in result.reasoning
        assert "high allocation" in result.reasoning.lower()
    
    def test_proceed_on_low_risk(self):
        """Test PROCEED decision when all checks pass."""
        checker = SafetyChecker()
        
        earnings_result = EarningsProximity(
            ticker="AAPL",
            has_upcoming_earnings=True,
            days_until_earnings=10,
            earnings_date=date.today() + timedelta(days=10),
            is_within_threshold=False,
            threshold_days=3,
        )
        
        result = checker._make_decision(
            ticker="AAPL",
            allocation_pct=10.0,
            risk_score=3.0,  # Low risk
            critical_events=[],
            earnings_result=earnings_result,
            retrieved_chunks=[],
        )
        
        assert result.decision == SafetyDecision.PROCEED
        assert "Low risk score" in result.reasoning


class TestCacheKeyGeneration:
    """Tests for cache key generation."""
    
    def test_cache_key_bucketing(self):
        """Test that allocations are bucketed to 5%."""
        checker = SafetyChecker()
        
        # These should all generate the same key (bucket to 10%)
        key1 = checker._generate_cache_key("AAPL", 8.0)
        key2 = checker._generate_cache_key("AAPL", 10.0)
        key3 = checker._generate_cache_key("AAPL", 12.0)
        
        assert key1 == key2 == key3
    
    def test_cache_key_different_tickers(self):
        """Test that different tickers generate different keys."""
        checker = SafetyChecker()
        
        key_aapl = checker._generate_cache_key("AAPL", 10.0)
        key_msft = checker._generate_cache_key("MSFT", 10.0)
        
        assert key_aapl != key_msft
    
    def test_cache_key_different_buckets(self):
        """Test that different buckets generate different keys."""
        checker = SafetyChecker()
        
        key_10 = checker._generate_cache_key("AAPL", 10.0)
        key_20 = checker._generate_cache_key("AAPL", 20.0)
        
        assert key_10 != key_20


class TestSafetyCheckIntegration:
    """Integration tests for full safety check flow."""
    
    def test_check_safety_veto_scenario(self):
        """Test full safety check resulting in VETO."""
        # Setup mocks
        mock_store = MagicMock()
        mock_earnings = MagicMock()
        mock_retriever = MagicMock()
        
        # Mock earnings check - no upcoming earnings
        mock_earnings.check_earnings_proximity.return_value = EarningsProximity(
            ticker="AAPL",
            has_upcoming_earnings=False,
            threshold_days=3,
        )
        
        # Mock retrieval - high risk content
        mock_retriever.retrieve_for_safety_check.return_value = [
            MagicMock(
                content="Company faces bankruptcy and going concern issues.",
                section_name="1A",
                filing_type="10-K",
                combined_score=0.9,
            ),
        ]
        
        checker = SafetyChecker(
            store=mock_store,
            earnings_checker=mock_earnings,
            retriever=mock_retriever,
        )
        
        result = checker.check_safety(
            ticker="AAPL",
            allocation_pct=10.0,
            use_cache=False,
        )
        
        assert result.decision == SafetyDecision.VETO
        assert result.ticker == "AAPL"
        assert result.critical_events is not None
    
    def test_check_safety_reduce_scenario(self):
        """Test full safety check resulting in REDUCE."""
        mock_store = MagicMock()
        mock_earnings = MagicMock()
        mock_retriever = MagicMock()
        
        # Mock earnings check - earnings within threshold
        mock_earnings.check_earnings_proximity.return_value = EarningsProximity(
            ticker="AAPL",
            has_upcoming_earnings=True,
            days_until_earnings=2,
            earnings_date=date.today() + timedelta(days=2),
            is_within_threshold=True,
            threshold_days=3,
        )
        
        # Mock retrieval - medium risk
        mock_retriever.retrieve_for_safety_check.return_value = [
            MagicMock(
                content="Some litigation risks exist.",
                section_name="1A",
                filing_type="10-K",
                combined_score=0.7,
            ),
        ]
        
        checker = SafetyChecker(
            store=mock_store,
            earnings_checker=mock_earnings,
            retriever=mock_retriever,
        )
        
        result = checker.check_safety(
            ticker="AAPL",
            allocation_pct=20.0,  # High allocation
            use_cache=False,
        )
        
        assert result.decision == SafetyDecision.REDUCE
        assert result.earnings_warning is not None
    
    def test_check_safety_proceed_scenario(self):
        """Test full safety check resulting in PROCEED."""
        mock_store = MagicMock()
        mock_earnings = MagicMock()
        mock_retriever = MagicMock()
        
        # Mock earnings check - no upcoming earnings
        mock_earnings.check_earnings_proximity.return_value = EarningsProximity(
            ticker="AAPL",
            has_upcoming_earnings=False,
            threshold_days=3,
        )
        
        # Mock retrieval - low risk
        mock_retriever.retrieve_for_safety_check.return_value = [
            MagicMock(
                content="Normal business operations.",
                section_name="7",
                filing_type="10-K",
                combined_score=0.5,
            ),
        ]
        
        checker = SafetyChecker(
            store=mock_store,
            earnings_checker=mock_earnings,
            retriever=mock_retriever,
        )
        
        result = checker.check_safety(
            ticker="AAPL",
            allocation_pct=10.0,
            use_cache=False,
        )
        
        assert result.decision == SafetyDecision.PROCEED
        assert result.risk_score < 6.0
    
    def test_check_safety_no_filings(self):
        """Test safety check when no filings are available."""
        mock_store = MagicMock()
        mock_earnings = MagicMock()
        mock_retriever = MagicMock()
        
        # Mock earnings check
        mock_earnings.check_earnings_proximity.return_value = EarningsProximity(
            ticker="NEWCO",
            has_upcoming_earnings=False,
            threshold_days=3,
        )
        
        # Mock retrieval - no results
        mock_retriever.retrieve_for_safety_check.return_value = []
        
        checker = SafetyChecker(
            store=mock_store,
            earnings_checker=mock_earnings,
            retriever=mock_retriever,
        )
        
        result = checker.check_safety(
            ticker="NEWCO",
            allocation_pct=10.0,
            use_cache=False,
        )
        
        # Should default to medium risk (5.0) when no data
        assert result.risk_score == 5.0
        # With medium risk and low allocation, should PROCEED
        assert result.decision == SafetyDecision.PROCEED
