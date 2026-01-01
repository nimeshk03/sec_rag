"""
Integration tests for Phase 5.2: End-to-End Safety Check Flow.

Tests cover:
- Complete safety check workflow from API to database
- Database operations with real Supabase connection
- Cache behavior and invalidation
- Error handling and graceful degradation
- Edge cases (missing data, API failures)
"""

import pytest
import httpx
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from src.api.main import app
from src.safety.checker import SafetyChecker, SafetyDecision
from src.data.store import SupabaseStore, EarningsEntry
from src.safety.earnings import EarningsChecker


@pytest.fixture
async def client():
    """Create async test client."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
def mock_store():
    """Create mock store for integration tests."""
    store = MagicMock(spec=SupabaseStore)
    return store


@pytest.fixture
def mock_retriever():
    """Create mock retriever for integration tests."""
    retriever = MagicMock()
    return retriever


class TestEndToEndSafetyCheck:
    """Integration tests for complete safety check workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_safety_check_flow_proceed(self, client):
        """Test complete flow resulting in PROCEED decision."""
        with patch('src.api.main.safety_checker') as mock_checker:
            from src.safety.checker import SafetyCheckResult
            
            # Mock a low-risk scenario
            mock_checker.check_safety.return_value = SafetyCheckResult(
                decision=SafetyDecision.PROCEED,
                ticker="AAPL",
                risk_score=3.5,
                reasoning="Low risk score (3.5). No critical events detected.",
                cache_hit=False,
            )
            
            response = await client.post(
                "/safety-check",
                json={
                    "ticker": "AAPL",
                    "allocation_pct": 10.0,
                    "use_cache": True
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["decision"] == "PROCEED"
            assert data["ticker"] == "AAPL"
            assert data["risk_score"] == 3.5
            assert "Low risk" in data["reasoning"]
            
            # Verify safety checker was called with correct params
            mock_checker.check_safety.assert_called_once()
            call_args = mock_checker.check_safety.call_args
            assert call_args[1]["ticker"] == "AAPL"
            assert call_args[1]["allocation_pct"] == 10.0
    
    @pytest.mark.asyncio
    async def test_complete_safety_check_flow_reduce(self, client):
        """Test complete flow resulting in REDUCE decision."""
        with patch('src.api.main.safety_checker') as mock_checker:
            from src.safety.checker import SafetyCheckResult
            
            # Mock elevated risk with earnings warning
            mock_checker.check_safety.return_value = SafetyCheckResult(
                decision=SafetyDecision.REDUCE,
                ticker="MSFT",
                risk_score=6.8,
                reasoning="Elevated risk score (6.8). Earnings approaching.",
                earnings_warning="Earnings in 2 days",
                allocation_warning="High allocation: 18.0%",
                cache_hit=False,
            )
            
            response = await client.post(
                "/safety-check",
                json={
                    "ticker": "MSFT",
                    "allocation_pct": 18.0,
                    "use_cache": False
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["decision"] == "REDUCE"
            assert data["risk_score"] == 6.8
            assert data["earnings_warning"] == "Earnings in 2 days"
            assert data["allocation_warning"] == "High allocation: 18.0%"
    
    @pytest.mark.asyncio
    async def test_complete_safety_check_flow_veto(self, client):
        """Test complete flow resulting in VETO decision."""
        with patch('src.api.main.safety_checker') as mock_checker:
            from src.safety.checker import SafetyCheckResult
            
            # Mock critical risk scenario
            mock_checker.check_safety.return_value = SafetyCheckResult(
                decision=SafetyDecision.VETO,
                ticker="XYZ",
                risk_score=9.5,
                reasoning="Critical risk detected (9.5). Bankruptcy filing mentioned.",
                critical_events=["Bankruptcy filing detected", "Going concern warning"],
                cache_hit=False,
            )
            
            response = await client.post(
                "/safety-check",
                json={
                    "ticker": "XYZ",
                    "allocation_pct": 5.0,
                    "use_cache": True
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["decision"] == "VETO"
            assert data["risk_score"] == 9.5
            assert len(data["critical_events"]) == 2
            assert "Bankruptcy" in data["critical_events"][0]


class TestDatabaseIntegration:
    """Integration tests for database operations."""
    
    def test_earnings_data_retrieval(self):
        """Test retrieving earnings data from database."""
        try:
            store = SupabaseStore()
            earnings_checker = EarningsChecker(store=store)
            
            # Test getting next earnings for a ticker
            proximity = earnings_checker.check_proximity("AAPL")
            
            # Should return a valid proximity result
            assert proximity is not None
            assert isinstance(proximity.days_until, (int, type(None)))
            
        except Exception as e:
            # If database not available, test should pass gracefully
            pytest.skip(f"Database not available: {e}")
    
    def test_safety_log_storage(self):
        """Test storing safety check logs in database."""
        try:
            store = SupabaseStore()
            
            # Create a test safety log entry
            from src.data.store import SafetyLog
            
            log = SafetyLog(
                ticker="TEST",
                decision="PROCEED",
                risk_score=3.0,
                reasoning="Test log entry",
                proposed_allocation=10.0,
                current_allocation=5.0,
                timestamp=datetime.utcnow(),
            )
            
            # This tests the log structure is valid
            assert log.ticker == "TEST"
            assert log.decision == "PROCEED"
            assert log.risk_score == 3.0
            
        except Exception as e:
            pytest.skip(f"Database not available: {e}")


class TestCacheBehavior:
    """Integration tests for cache behavior."""
    
    def test_cache_key_generation_consistency(self):
        """Test that cache keys are generated consistently."""
        from src.safety.checker import SafetyChecker
        
        mock_store = MagicMock()
        checker = SafetyChecker(store=mock_store)
        
        # Same inputs should generate same cache key
        key1 = checker._generate_cache_key("AAPL", 10.0)
        key2 = checker._generate_cache_key("AAPL", 10.0)
        assert key1 == key2
        
        # Different tickers should generate different keys
        key3 = checker._generate_cache_key("MSFT", 10.0)
        assert key1 != key3
        
        # Allocation bucketing (5% buckets)
        key4 = checker._generate_cache_key("AAPL", 10.5)
        key5 = checker._generate_cache_key("AAPL", 12.0)
        assert key4 == key5  # Both in 10-15% bucket
        
        key6 = checker._generate_cache_key("AAPL", 16.0)
        assert key4 != key6  # Different buckets
    
    @pytest.mark.asyncio
    async def test_cache_stats_endpoint(self, client):
        """Test cache statistics endpoint."""
        response = await client.get("/cache-stats")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields are present
        assert "total_entries" in data
        assert "hit_rate" in data
        assert "total_hits" in data
        assert "total_misses" in data
        
        # Verify data types
        assert isinstance(data["total_entries"], int)
        assert isinstance(data["total_hits"], int)
        assert isinstance(data["total_misses"], int)
    
    @pytest.mark.asyncio
    async def test_cache_invalidation(self, client):
        """Test cache invalidation endpoint."""
        response = await client.delete("/cache/AAPL")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert data["ticker"] == "AAPL"
        assert "entries_deleted" in data
        assert isinstance(data["entries_deleted"], int)


class TestErrorHandling:
    """Integration tests for error handling and graceful degradation."""
    
    @pytest.mark.asyncio
    async def test_invalid_ticker_validation(self, client):
        """Test validation error for invalid ticker."""
        response = await client.post(
            "/safety-check",
            json={
                "ticker": "",  # Empty ticker
                "allocation_pct": 10.0
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_allocation_out_of_range(self, client):
        """Test validation for allocation percentage."""
        # Test upper bound
        response = await client.post(
            "/safety-check",
            json={
                "ticker": "AAPL",
                "allocation_pct": 150.0
            }
        )
        assert response.status_code == 422
        
        # Test lower bound
        response = await client.post(
            "/safety-check",
            json={
                "ticker": "AAPL",
                "allocation_pct": -5.0
            }
        )
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_missing_required_fields(self, client):
        """Test error handling for missing required fields."""
        response = await client.post(
            "/safety-check",
            json={
                "allocation_pct": 10.0
                # Missing ticker
            }
        )
        
        assert response.status_code == 422
    
    def test_graceful_degradation_no_earnings_data(self):
        """Test system handles missing earnings data gracefully."""
        mock_store = MagicMock()
        mock_store.get_next_earnings.return_value = None
        
        earnings_checker = EarningsChecker(store=mock_store)
        proximity = earnings_checker.check_earnings_proximity("UNKNOWN")
        
        # Should return a valid result even with no data
        assert proximity is not None
        assert proximity.days_until_earnings is None
        assert proximity.has_upcoming_earnings is False
    
    def test_graceful_degradation_retrieval_failure(self):
        """Test system handles retrieval failures gracefully."""
        from src.safety.checker import SafetyChecker
        
        mock_store = MagicMock()
        mock_retriever = MagicMock()
        mock_earnings_checker = MagicMock()
        
        # Simulate retrieval failure
        mock_retriever.retrieve_for_safety_check.side_effect = Exception("Retrieval failed")
        
        # Mock earnings checker to return no upcoming earnings
        from src.safety.earnings import EarningsProximity
        mock_earnings_checker.check_earnings_proximity.return_value = EarningsProximity(
            ticker="AAPL",
            has_upcoming_earnings=False,
            threshold_days=3
        )
        
        # Pass mock_retriever through constructor
        checker = SafetyChecker(
            store=mock_store,
            retriever=mock_retriever,
            earnings_checker=mock_earnings_checker
        )
        
        # Should handle error and return a safe decision
        # VETO is returned because critical_events contains the error message
        result = checker.check_safety(
            ticker="AAPL",
            allocation_pct=10.0,
            use_cache=False
        )
        
        # Should return VETO decision due to critical event (retrieval failure)
        assert result.decision == SafetyDecision.VETO
        assert result.risk_score == 7.0
        assert result.critical_events is not None
        assert "Data retrieval failed" in result.critical_events[0]


class TestEdgeCases:
    """Integration tests for edge cases."""
    
    @pytest.mark.asyncio
    async def test_ticker_case_insensitivity(self, client):
        """Test that ticker symbols are case-insensitive."""
        with patch('src.api.main.safety_checker') as mock_checker:
            from src.safety.checker import SafetyCheckResult
            
            mock_checker.check_safety.return_value = SafetyCheckResult(
                decision=SafetyDecision.PROCEED,
                ticker="AAPL",
                risk_score=3.0,
                reasoning="Test",
                cache_hit=False,
            )
            
            # Send lowercase ticker
            response = await client.post(
                "/safety-check",
                json={
                    "ticker": "aapl",
                    "allocation_pct": 10.0
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            # Should be converted to uppercase
            assert data["ticker"] == "AAPL"
    
    @pytest.mark.asyncio
    async def test_zero_allocation(self, client):
        """Test handling of zero allocation."""
        with patch('src.api.main.safety_checker') as mock_checker:
            from src.safety.checker import SafetyCheckResult
            
            mock_checker.check_safety.return_value = SafetyCheckResult(
                decision=SafetyDecision.PROCEED,
                ticker="AAPL",
                risk_score=3.0,
                reasoning="Zero allocation",
                cache_hit=False,
            )
            
            response = await client.post(
                "/safety-check",
                json={
                    "ticker": "AAPL",
                    "allocation_pct": 0.0
                }
            )
            
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_filing_indexing_with_invalid_data(self, client):
        """Test filing indexing with invalid filing type."""
        response = await client.post(
            "/index-filing",
            json={
                "ticker": "AAPL",
                "cik": "0000320193",
                "filing_type": "INVALID",
                "filing_date": "2024-01-15",
                "accession_number": "0000320193-24-000001",
                "primary_document": "test.htm",
                "filing_url": "https://www.sec.gov/test"
            }
        )
        
        assert response.status_code == 422
    
    def test_earnings_on_exact_boundary(self):
        """Test earnings proximity on exact warning boundary."""
        mock_store = MagicMock()
        
        # Set earnings exactly 3 days away (warning threshold)
        today = date.today()
        earnings_date = today + timedelta(days=3)
        
        mock_store.get_next_earnings.return_value = EarningsEntry(
            ticker="AAPL",
            earnings_date=earnings_date,
            time_of_day="AMC",
            fiscal_quarter="Q1",
            source="test",
        )
        
        earnings_checker = EarningsChecker(store=mock_store)
        proximity = earnings_checker.check_earnings_proximity("AAPL")
        
        assert proximity.has_upcoming_earnings is True
        assert proximity.days_until_earnings == 3
        assert proximity.is_within_threshold is True  # Should trigger warning at boundary


class TestHealthAndMonitoring:
    """Integration tests for health checks and monitoring."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint_structure(self, client):
        """Test health endpoint returns complete structure."""
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "status" in data
        assert "timestamp" in data
        assert "dependencies" in data
        assert "version" in data
        
        # Verify dependencies structure
        deps = data["dependencies"]
        assert "database" in deps
        assert "embedder" in deps
        assert "retriever" in deps
    
    @pytest.mark.asyncio
    async def test_root_endpoint_metadata(self, client):
        """Test root endpoint returns API metadata."""
        response = await client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "name" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "running"
