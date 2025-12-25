"""
Unit tests for Supabase Store Interface.

Tests all CRUD operations with mocked Supabase client.
"""

import pytest
import numpy as np
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

from src.data.store import (
    SupabaseStore,
    Filing,
    Chunk,
    SearchResult,
    SafetyLog,
    EarningsEntry,
)


class TestSupabaseStoreInitialization:
    """Tests for store initialization."""
    
    def test_init_with_client(self):
        """Test initialization with injected client."""
        mock_client = MagicMock()
        store = SupabaseStore(client=mock_client)
        
        assert store._client is mock_client
    
    def test_init_without_client(self):
        """Test initialization without client (lazy load)."""
        store = SupabaseStore()
        
        assert store._client is None
    
    @patch('src.data.store.get_supabase')
    def test_lazy_client_loading(self, mock_get_supabase):
        """Test that client is loaded on first access."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        
        store = SupabaseStore()
        _ = store.client
        
        mock_get_supabase.assert_called_once()
        assert store._client is mock_client


class TestFilingOperations:
    """Tests for filing CRUD operations."""
    
    def test_insert_filing_success(self):
        """Test successful filing insertion."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "filing-uuid-123"}
        ]
        
        store = SupabaseStore(client=mock_client)
        filing = Filing(
            ticker="AAPL",
            filing_type="10-K",
            filing_date=date(2024, 1, 15),
            accession_number="0000320193-24-000001",
            fiscal_year=2023,
        )
        
        result = store.insert_filing(filing)
        
        assert result == "filing-uuid-123"
        mock_client.table.assert_called_with("filings")
    
    def test_insert_filing_with_all_fields(self):
        """Test filing insertion with all optional fields."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "filing-uuid-456"}
        ]
        
        store = SupabaseStore(client=mock_client)
        filing = Filing(
            ticker="MSFT",
            filing_type="10-Q",
            filing_date=date(2024, 3, 15),
            accession_number="0000789-24-000002",
            fiscal_period="Q1",
            fiscal_year=2024,
            source_url="https://sec.gov/filing/123",
        )
        
        result = store.insert_filing(filing)
        
        assert result == "filing-uuid-456"
        # Verify all fields were passed
        call_args = mock_client.table.return_value.insert.call_args[0][0]
        assert call_args["fiscal_period"] == "Q1"
        assert call_args["source_url"] == "https://sec.gov/filing/123"
    
    def test_insert_filing_failure(self):
        """Test filing insertion failure raises exception."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value.data = []
        
        store = SupabaseStore(client=mock_client)
        filing = Filing(
            ticker="AAPL",
            filing_type="10-K",
            filing_date=date(2024, 1, 15),
            accession_number="0000320193-24-000001",
        )
        
        with pytest.raises(Exception, match="Failed to insert filing"):
            store.insert_filing(filing)
    
    def test_get_filing_found(self):
        """Test getting a filing that exists."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {
                "id": "filing-uuid-123",
                "ticker": "AAPL",
                "filing_type": "10-K",
                "filing_date": "2024-01-15",
                "accession_number": "0000320193-24-000001",
                "fiscal_period": "FY",
                "fiscal_year": 2023,
                "source_url": None,
                "processed_at": "2024-01-16T10:00:00Z",
            }
        ]
        
        store = SupabaseStore(client=mock_client)
        result = store.get_filing("AAPL")
        
        assert result is not None
        assert result.ticker == "AAPL"
        assert result.filing_type == "10-K"
        assert result.filing_date == date(2024, 1, 15)
    
    def test_get_filing_not_found(self):
        """Test getting a filing that doesn't exist."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
        
        store = SupabaseStore(client=mock_client)
        result = store.get_filing("UNKNOWN")
        
        assert result is None
    
    def test_get_filing_with_filters(self):
        """Test getting filing with date and type filters."""
        mock_client = MagicMock()
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value.limit.return_value.execute.return_value.data = []
        
        store = SupabaseStore(client=mock_client)
        store.get_filing("AAPL", filing_date=date(2024, 1, 15), filing_type="10-K")
        
        # Verify filters were applied
        eq_calls = mock_query.eq.call_args_list
        assert len(eq_calls) >= 2  # ticker + at least one filter
    
    def test_get_filing_by_id(self):
        """Test getting filing by UUID."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {
                "id": "filing-uuid-123",
                "ticker": "GOOGL",
                "filing_type": "8-K",
                "filing_date": "2024-02-01",
                "accession_number": "0001234-24-000003",
            }
        ]
        
        store = SupabaseStore(client=mock_client)
        result = store.get_filing_by_id("filing-uuid-123")
        
        assert result is not None
        assert result.id == "filing-uuid-123"
        assert result.ticker == "GOOGL"
    
    def test_get_recent_filings(self):
        """Test getting recent filings with filters."""
        mock_client = MagicMock()
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value.limit.return_value.execute.return_value.data = [
            {
                "id": "f1",
                "ticker": "AAPL",
                "filing_type": "10-K",
                "filing_date": "2024-01-15",
                "accession_number": "acc1",
            },
            {
                "id": "f2",
                "ticker": "AAPL",
                "filing_type": "10-Q",
                "filing_date": "2024-03-15",
                "accession_number": "acc2",
            },
        ]
        
        store = SupabaseStore(client=mock_client)
        results = store.get_recent_filings(ticker="AAPL", days_back=180)
        
        assert len(results) == 2
        assert all(f.ticker == "AAPL" for f in results)
    
    def test_delete_filing(self):
        """Test deleting a filing."""
        mock_client = MagicMock()
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = [
            {"id": "filing-uuid-123"}
        ]
        
        store = SupabaseStore(client=mock_client)
        result = store.delete_filing("filing-uuid-123")
        
        assert result is True
    
    def test_delete_filing_not_found(self):
        """Test deleting a non-existent filing."""
        mock_client = MagicMock()
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
        
        store = SupabaseStore(client=mock_client)
        result = store.delete_filing("nonexistent-uuid")
        
        assert result is False


class TestChunkOperations:
    """Tests for chunk CRUD operations."""
    
    def test_insert_chunks_success(self):
        """Test successful batch chunk insertion."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "chunk-1"},
            {"id": "chunk-2"},
            {"id": "chunk-3"},
        ]
        
        store = SupabaseStore(client=mock_client)
        chunks = [
            Chunk(
                filing_id="filing-123",
                section_name="1A",
                content="Risk factor content",
                chunk_index=0,
                embedding=np.random.randn(384),
                total_chunks=3,
                word_count=50,
            ),
            Chunk(
                filing_id="filing-123",
                section_name="1A",
                content="More risk content",
                chunk_index=1,
                embedding=np.random.randn(384),
            ),
            Chunk(
                filing_id="filing-123",
                section_name="7",
                content="MD&A content",
                chunk_index=2,
                embedding=np.random.randn(384),
            ),
        ]
        
        result = store.insert_chunks(chunks)
        
        assert len(result) == 3
        assert result == ["chunk-1", "chunk-2", "chunk-3"]
    
    def test_insert_chunks_empty_list(self):
        """Test inserting empty chunk list."""
        mock_client = MagicMock()
        store = SupabaseStore(client=mock_client)
        
        result = store.insert_chunks([])
        
        assert result == []
        mock_client.table.assert_not_called()
    
    def test_insert_chunks_with_embeddings(self):
        """Test that embeddings are converted to lists."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "chunk-1"}
        ]
        
        store = SupabaseStore(client=mock_client)
        embedding = np.array([0.1, 0.2, 0.3] * 128)  # 384 dims
        chunks = [
            Chunk(
                filing_id="filing-123",
                section_name="1A",
                content="Content",
                chunk_index=0,
                embedding=embedding,
            )
        ]
        
        store.insert_chunks(chunks)
        
        call_data = mock_client.table.return_value.insert.call_args[0][0][0]
        assert "embedding" in call_data
        assert isinstance(call_data["embedding"], list)
        assert len(call_data["embedding"]) == 384
    
    def test_insert_chunks_failure(self):
        """Test chunk insertion failure."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value.data = []
        
        store = SupabaseStore(client=mock_client)
        chunks = [
            Chunk(
                filing_id="filing-123",
                section_name="1A",
                content="Content",
                chunk_index=0,
            )
        ]
        
        with pytest.raises(Exception, match="Failed to insert chunks"):
            store.insert_chunks(chunks)
    
    def test_get_chunks_by_filing(self):
        """Test retrieving chunks for a filing."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
            {
                "id": "chunk-1",
                "filing_id": "filing-123",
                "section_name": "1A",
                "content": "Content 1",
                "chunk_index": 0,
                "embedding": [0.1] * 384,
                "total_chunks": 2,
                "word_count": 50,
            },
            {
                "id": "chunk-2",
                "filing_id": "filing-123",
                "section_name": "1A",
                "content": "Content 2",
                "chunk_index": 1,
                "embedding": [0.2] * 384,
            },
        ]
        
        store = SupabaseStore(client=mock_client)
        results = store.get_chunks_by_filing("filing-123")
        
        assert len(results) == 2
        assert results[0].chunk_index == 0
        assert results[1].chunk_index == 1
        assert results[0].embedding is not None
        assert isinstance(results[0].embedding, np.ndarray)
    
    def test_delete_chunks_by_filing(self):
        """Test deleting chunks for a filing."""
        mock_client = MagicMock()
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = [
            {"id": "c1"}, {"id": "c2"}, {"id": "c3"}
        ]
        
        store = SupabaseStore(client=mock_client)
        result = store.delete_chunks_by_filing("filing-123")
        
        assert result == 3


class TestVectorSearch:
    """Tests for vector similarity search."""
    
    def test_vector_search_basic(self):
        """Test basic vector search."""
        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.return_value.data = [
            {
                "id": "chunk-1",
                "content": "Risk factor about market volatility",
                "section_name": "1A",
                "filing_type": "10-K",
                "filing_date": "2024-01-15",
                "similarity": 0.95,
            },
            {
                "id": "chunk-2",
                "content": "Another risk factor",
                "section_name": "1A",
                "filing_type": "10-K",
                "filing_date": "2024-01-15",
                "similarity": 0.87,
            },
        ]
        
        store = SupabaseStore(client=mock_client)
        query_embedding = np.random.randn(384)
        
        results = store.vector_search(
            query_embedding=query_embedding,
            ticker="AAPL",
            match_count=10,
        )
        
        assert len(results) == 2
        assert results[0].similarity == 0.95
        assert results[0].section_name == "1A"
        mock_client.rpc.assert_called_with("match_chunks", {
            "query_embedding": query_embedding.tolist(),
            "match_ticker": "AAPL",
            "match_count": 10,
            "days_back": 365,
        })
    
    def test_vector_search_with_filters(self):
        """Test vector search with filing type and section filters."""
        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.return_value.data = []
        
        store = SupabaseStore(client=mock_client)
        query_embedding = np.random.randn(384)
        
        store.vector_search(
            query_embedding=query_embedding,
            ticker="MSFT",
            match_count=5,
            days_back=180,
            filing_types=["10-K", "10-Q"],
            section_names=["1A", "7"],
        )
        
        call_args = mock_client.rpc.call_args[0][1]
        assert call_args["filing_types"] == ["10-K", "10-Q"]
        assert call_args["section_names"] == ["1A", "7"]
        assert call_args["days_back"] == 180
    
    def test_vector_search_returns_search_results(self):
        """Test that vector search returns SearchResult objects."""
        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.return_value.data = [
            {
                "id": "chunk-1",
                "content": "Content",
                "section_name": "1A",
                "filing_type": "10-K",
                "filing_date": "2024-01-15",
                "similarity": 0.9,
            },
        ]
        
        store = SupabaseStore(client=mock_client)
        results = store.vector_search(np.random.randn(384), "AAPL")
        
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].filing_date == date(2024, 1, 15)


class TestCacheOperations:
    """Tests for cache operations."""
    
    def test_generate_cache_key(self):
        """Test cache key generation is deterministic."""
        key1 = SupabaseStore._generate_cache_key("AAPL", "risk factors")
        key2 = SupabaseStore._generate_cache_key("AAPL", "risk factors")
        key3 = SupabaseStore._generate_cache_key("AAPL", "different query")
        
        assert key1 == key2
        assert key1 != key3
    
    def test_generate_cache_key_case_insensitive(self):
        """Test cache key handles case differences."""
        key1 = SupabaseStore._generate_cache_key("aapl", "Risk Factors")
        key2 = SupabaseStore._generate_cache_key("AAPL", "risk factors")
        
        assert key1 == key2
    
    def test_generate_cache_key_with_params(self):
        """Test cache key with additional parameters."""
        key1 = SupabaseStore._generate_cache_key("AAPL", "query", {"limit": 10})
        key2 = SupabaseStore._generate_cache_key("AAPL", "query", {"limit": 10})
        key3 = SupabaseStore._generate_cache_key("AAPL", "query", {"limit": 20})
        
        assert key1 == key2
        assert key1 != key3
    
    def test_get_cached_response_found_valid(self):
        """Test getting valid cached response."""
        mock_client = MagicMock()
        future_time = (datetime.now() + timedelta(hours=1)).isoformat()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {
                "id": "cache-1",
                "cache_key": "key123",
                "response": {"decision": "PROCEED", "risk_score": 3},
                "expires_at": future_time,
                "hit_count": 5,
            }
        ]
        
        store = SupabaseStore(client=mock_client)
        result = store.get_cached_response("key123")
        
        assert result is not None
        assert result["decision"] == "PROCEED"
        # Verify hit count was incremented
        mock_client.table.return_value.update.assert_called()
    
    def test_get_cached_response_expired(self):
        """Test that expired cache returns None."""
        mock_client = MagicMock()
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {
                "id": "cache-1",
                "cache_key": "key123",
                "response": {"data": "old"},
                "expires_at": past_time,
                "hit_count": 5,
            }
        ]
        
        store = SupabaseStore(client=mock_client)
        result = store.get_cached_response("key123")
        
        assert result is None
    
    def test_get_cached_response_not_found(self):
        """Test cache miss returns None."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        
        store = SupabaseStore(client=mock_client)
        result = store.get_cached_response("nonexistent")
        
        assert result is None
    
    def test_set_cached_response(self):
        """Test setting cache response."""
        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.return_value.data = [
            {"id": "cache-new"}
        ]
        
        store = SupabaseStore(client=mock_client)
        response = {"decision": "REDUCE", "risk_score": 7}
        
        result = store.set_cached_response("key456", response, ttl_hours=12)
        
        assert result == "cache-new"
        call_data = mock_client.table.return_value.upsert.call_args[0][0]
        assert call_data["response"] == response
    
    def test_set_cached_response_default_ttl(self):
        """Test cache uses default TTL when not specified."""
        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.return_value.data = [
            {"id": "cache-1"}
        ]
        
        store = SupabaseStore(client=mock_client)
        store.set_cached_response("key", {"data": "value"})
        
        call_data = mock_client.table.return_value.upsert.call_args[0][0]
        expires_at = datetime.fromisoformat(call_data["expires_at"])
        expected_min = datetime.now() + timedelta(hours=23)
        expected_max = datetime.now() + timedelta(hours=25)
        
        assert expected_min < expires_at < expected_max
    
    def test_invalidate_cache_with_pattern(self):
        """Test invalidating cache with pattern."""
        mock_client = MagicMock()
        mock_client.table.return_value.delete.return_value.like.return_value.execute.return_value.data = [
            {"id": "c1"}, {"id": "c2"}
        ]
        
        store = SupabaseStore(client=mock_client)
        result = store.invalidate_cache(pattern="AAPL")
        
        assert result == 2
        mock_client.table.return_value.delete.return_value.like.assert_called_with(
            "cache_key", "%AAPL%"
        )
    
    def test_invalidate_cache_expired(self):
        """Test invalidating expired cache entries."""
        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.return_value.data = 5
        
        store = SupabaseStore(client=mock_client)
        result = store.invalidate_cache()
        
        assert result == 5
        mock_client.rpc.assert_called_with("clean_expired_cache")
    
    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.return_value.data = [{
            "total_entries": 100,
            "expired_entries": 10,
            "total_hits": 500,
            "avg_hits": 5.0,
        }]
        
        store = SupabaseStore(client=mock_client)
        stats = store.get_cache_stats()
        
        assert stats["total_entries"] == 100
        assert stats["total_hits"] == 500


class TestSafetyLogOperations:
    """Tests for safety log operations."""
    
    def test_log_safety_check(self):
        """Test logging a safety check."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "log-123"}
        ]
        
        store = SupabaseStore(client=mock_client)
        log = SafetyLog(
            ticker="AAPL",
            proposed_allocation=0.15,
            current_allocation=0.10,
            decision="REDUCE",
            reasoning="High risk score due to pending litigation",
            risk_score=7,
            risks={"litigation": True, "earnings_proximity": False},
            chunks_retrieved=5,
            latency_ms=150,
            cached=False,
            rl_allocation=0.12,
            final_allocation=0.08,
        )
        
        result = store.log_safety_check(log)
        
        assert result == "log-123"
        call_data = mock_client.table.return_value.insert.call_args[0][0]
        assert call_data["ticker"] == "AAPL"
        assert call_data["decision"] == "REDUCE"
        assert call_data["risk_score"] == 7
    
    def test_log_safety_check_minimal(self):
        """Test logging with minimal required fields."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "log-456"}
        ]
        
        store = SupabaseStore(client=mock_client)
        log = SafetyLog(
            ticker="MSFT",
            proposed_allocation=0.05,
            current_allocation=0.05,
            decision="PROCEED",
            reasoning="No significant risks",
            risk_score=2,
        )
        
        result = store.log_safety_check(log)
        
        assert result == "log-456"
    
    def test_get_safety_history(self):
        """Test querying safety check history."""
        mock_client = MagicMock()
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value.limit.return_value.execute.return_value.data = [
            {
                "id": "log-1",
                "timestamp": "2024-01-15T10:00:00Z",
                "ticker": "AAPL",
                "proposed_allocation": 0.10,
                "current_allocation": 0.08,
                "decision": "PROCEED",
                "reasoning": "Low risk",
                "risk_score": 2,
                "risks": {},
                "chunks_retrieved": 3,
                "latency_ms": 100,
                "cached": True,
            },
        ]
        
        store = SupabaseStore(client=mock_client)
        results = store.get_safety_history(ticker="AAPL", days_back=7)
        
        assert len(results) == 1
        assert results[0].ticker == "AAPL"
        assert results[0].decision == "PROCEED"
    
    def test_get_safety_history_with_decision_filter(self):
        """Test filtering safety history by decision."""
        mock_client = MagicMock()
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value.limit.return_value.execute.return_value.data = []
        
        store = SupabaseStore(client=mock_client)
        store.get_safety_history(decision="VETO")
        
        # Verify decision filter was applied
        eq_calls = [call[0] for call in mock_query.eq.call_args_list]
        assert ("decision", "VETO") in eq_calls
    
    def test_get_safety_stats(self):
        """Test getting aggregated safety statistics."""
        mock_client = MagicMock()
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value.limit.return_value.execute.return_value.data = [
            {"id": "1", "ticker": "AAPL", "decision": "PROCEED", "risk_score": 2, 
             "latency_ms": 100, "cached": True, "proposed_allocation": 0.1,
             "current_allocation": 0.1, "reasoning": "ok", "risks": {}},
            {"id": "2", "ticker": "AAPL", "decision": "REDUCE", "risk_score": 6,
             "latency_ms": 150, "cached": False, "proposed_allocation": 0.1,
             "current_allocation": 0.1, "reasoning": "risk", "risks": {}},
            {"id": "3", "ticker": "AAPL", "decision": "VETO", "risk_score": 9,
             "latency_ms": 200, "cached": False, "proposed_allocation": 0.1,
             "current_allocation": 0.1, "reasoning": "high risk", "risks": {}},
        ]
        
        store = SupabaseStore(client=mock_client)
        stats = store.get_safety_stats(ticker="AAPL")
        
        assert stats["total_checks"] == 3
        assert stats["proceed_count"] == 1
        assert stats["reduce_count"] == 1
        assert stats["veto_count"] == 1
        assert stats["avg_risk_score"] == (2 + 6 + 9) / 3
        assert stats["cache_hit_rate"] == 1 / 3
    
    def test_get_safety_stats_empty(self):
        """Test safety stats with no data."""
        mock_client = MagicMock()
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.order.return_value.limit.return_value.execute.return_value.data = []
        
        store = SupabaseStore(client=mock_client)
        stats = store.get_safety_stats()
        
        assert stats["total_checks"] == 0
        assert stats["cache_hit_rate"] == 0


class TestEarningsOperations:
    """Tests for earnings calendar operations."""
    
    def test_get_next_earnings(self):
        """Test getting next earnings date."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {
                "id": "earn-1",
                "ticker": "AAPL",
                "earnings_date": "2024-02-01",
                "time_of_day": "AMC",
                "fiscal_quarter": "Q1",
                "source": "company",
            }
        ]
        
        store = SupabaseStore(client=mock_client)
        result = store.get_next_earnings("AAPL")
        
        assert result is not None
        assert result.ticker == "AAPL"
        assert result.earnings_date == date(2024, 2, 1)
        assert result.time_of_day == "AMC"
    
    def test_get_next_earnings_not_found(self):
        """Test when no upcoming earnings exist."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value.data = []
        
        store = SupabaseStore(client=mock_client)
        result = store.get_next_earnings("UNKNOWN")
        
        assert result is None
    
    def test_get_upcoming_earnings(self):
        """Test getting all upcoming earnings."""
        mock_client = MagicMock()
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.lte.return_value = mock_query
        mock_query.in_.return_value = mock_query
        mock_query.order.return_value.execute.return_value.data = [
            {"id": "e1", "ticker": "AAPL", "earnings_date": "2024-02-01", "time_of_day": "AMC"},
            {"id": "e2", "ticker": "MSFT", "earnings_date": "2024-02-05", "time_of_day": "BMO"},
        ]
        
        store = SupabaseStore(client=mock_client)
        results = store.get_upcoming_earnings(days_ahead=14, tickers=["AAPL", "MSFT"])
        
        assert len(results) == 2
    
    def test_update_earnings(self):
        """Test inserting/updating earnings entry."""
        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.return_value.data = [
            {"id": "earn-new"}
        ]
        
        store = SupabaseStore(client=mock_client)
        entry = EarningsEntry(
            ticker="GOOGL",
            earnings_date=date(2024, 2, 15),
            time_of_day="AMC",
            fiscal_quarter="Q4",
            source="investor_relations",
        )
        
        result = store.update_earnings(entry)
        
        assert result == "earn-new"
    
    def test_delete_earnings(self):
        """Test deleting earnings entry."""
        mock_client = MagicMock()
        mock_client.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"id": "earn-1"}
        ]
        
        store = SupabaseStore(client=mock_client)
        result = store.delete_earnings("AAPL", date(2024, 2, 1))
        
        assert result is True


class TestDataclasses:
    """Tests for dataclass creation and defaults."""
    
    def test_filing_creation(self):
        """Test Filing dataclass."""
        filing = Filing(
            ticker="AAPL",
            filing_type="10-K",
            filing_date=date(2024, 1, 15),
            accession_number="0000320193-24-000001",
        )
        
        assert filing.ticker == "AAPL"
        assert filing.fiscal_period is None
        assert filing.id is None
    
    def test_chunk_creation(self):
        """Test Chunk dataclass."""
        chunk = Chunk(
            filing_id="filing-123",
            section_name="1A",
            content="Risk content",
            chunk_index=0,
        )
        
        assert chunk.embedding is None
        assert chunk.word_count is None
    
    def test_search_result_creation(self):
        """Test SearchResult dataclass."""
        result = SearchResult(
            id="chunk-1",
            content="Content",
            section_name="1A",
            filing_type="10-K",
            filing_date=date(2024, 1, 15),
            similarity=0.95,
        )
        
        assert result.similarity == 0.95
    
    def test_safety_log_defaults(self):
        """Test SafetyLog default values."""
        log = SafetyLog(
            ticker="AAPL",
            proposed_allocation=0.1,
            current_allocation=0.1,
            decision="PROCEED",
            reasoning="OK",
            risk_score=2,
        )
        
        assert log.risks == {}
        assert log.chunks_retrieved == 0
        assert log.cached is False
    
    def test_earnings_entry_defaults(self):
        """Test EarningsEntry default values."""
        entry = EarningsEntry(
            ticker="AAPL",
            earnings_date=date(2024, 2, 1),
        )
        
        assert entry.time_of_day == "UNKNOWN"
        assert entry.fiscal_quarter is None


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_insert_filing_handles_exception(self):
        """Test that insert_filing raises on failure."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value.data = None
        
        store = SupabaseStore(client=mock_client)
        filing = Filing(
            ticker="AAPL",
            filing_type="10-K",
            filing_date=date(2024, 1, 15),
            accession_number="acc-123",
        )
        
        with pytest.raises(Exception):
            store.insert_filing(filing)
    
    def test_set_cache_handles_exception(self):
        """Test that set_cached_response raises on failure."""
        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.return_value.data = None
        
        store = SupabaseStore(client=mock_client)
        
        with pytest.raises(Exception, match="Failed to set cache"):
            store.set_cached_response("key", {"data": "value"})
    
    def test_log_safety_check_handles_exception(self):
        """Test that log_safety_check raises on failure."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value.data = None
        
        store = SupabaseStore(client=mock_client)
        log = SafetyLog(
            ticker="AAPL",
            proposed_allocation=0.1,
            current_allocation=0.1,
            decision="PROCEED",
            reasoning="OK",
            risk_score=2,
        )
        
        with pytest.raises(Exception, match="Failed to log safety check"):
            store.log_safety_check(log)
