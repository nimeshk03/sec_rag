"""
API tests for Phase 5.1 FastAPI Implementation.

Tests cover:
- Root endpoint
- Health check endpoint
- Safety check endpoint validation
- Filing indexing endpoint
- Cache stats endpoint
- Cache invalidation endpoint
- Request validation
"""

import pytest
import httpx

from src.api.main import app


@pytest.fixture
async def client():
    """Create async test client."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c


class TestRootEndpoint:
    """Tests for root endpoint."""
    
    @pytest.mark.asyncio
    async def test_root_returns_api_info(self, client):
        """Test root endpoint returns API information."""
        response = await client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "SEC Filing RAG Safety System"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    @pytest.mark.asyncio
    async def test_health_check_returns_status(self, client):
        """Test health endpoint returns status."""
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "dependencies" in data
        assert "version" in data
    
    @pytest.mark.asyncio
    async def test_health_check_includes_dependencies(self, client):
        """Test health check includes dependency status."""
        response = await client.get("/health")
        
        data = response.json()
        assert "database" in data["dependencies"]
        assert "embedder" in data["dependencies"]
        assert "retriever" in data["dependencies"]


class TestSafetyCheckEndpoint:
    """Tests for safety check endpoint validation."""
    
    @pytest.mark.asyncio
    async def test_safety_check_invalid_allocation_too_high(self, client):
        """Test validation error for allocation > 100."""
        response = await client.post(
            "/safety-check",
            json={
                "ticker": "AAPL",
                "allocation_pct": 150.0,
                "use_cache": True
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_safety_check_invalid_allocation_negative(self, client):
        """Test validation error for negative allocation."""
        response = await client.post(
            "/safety-check",
            json={
                "ticker": "AAPL",
                "allocation_pct": -10.0,
                "use_cache": True
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_safety_check_missing_ticker(self, client):
        """Test validation error for missing ticker."""
        response = await client.post(
            "/safety-check",
            json={
                "allocation_pct": 10.0,
                "use_cache": True
            }
        )
        
        assert response.status_code == 422


class TestIndexFilingEndpoint:
    """Tests for filing indexing endpoint."""
    
    @pytest.mark.asyncio
    async def test_index_filing_starts_background_task(self, client):
        """Test that filing indexing starts without blocking."""
        response = await client.post(
            "/index-filing",
            json={
                "ticker": "AAPL",
                "cik": "0000320193",
                "filing_type": "10-K",
                "filing_date": "2024-01-15",
                "accession_number": "0000320193-24-000001",
                "primary_document": "aapl-20240115.htm",
                "filing_url": "https://www.sec.gov/test"
            }
        )
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "processing"
        assert data["ticker"] == "AAPL"
        assert data["filing_type"] == "10-K"
    
    @pytest.mark.asyncio
    async def test_index_filing_invalid_filing_type(self, client):
        """Test validation error for invalid filing type."""
        response = await client.post(
            "/index-filing",
            json={
                "ticker": "AAPL",
                "cik": "0000320193",
                "filing_type": "INVALID",
                "filing_date": "2024-01-15",
                "accession_number": "0000320193-24-000001",
                "primary_document": "aapl-20240115.htm",
                "filing_url": "https://www.sec.gov/test"
            }
        )
        
        assert response.status_code == 422


class TestCacheEndpoints:
    """Tests for cache management endpoints."""
    
    @pytest.mark.asyncio
    async def test_cache_stats_returns_metrics(self, client):
        """Test cache stats endpoint returns metrics."""
        response = await client.get("/cache-stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_entries" in data
        assert "hit_rate" in data
        assert "total_hits" in data
        assert "total_misses" in data
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_success(self, client):
        """Test cache invalidation for ticker."""
        response = await client.delete("/cache/AAPL")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["ticker"] == "AAPL"
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_uppercase_conversion(self, client):
        """Test that ticker is converted to uppercase."""
        response = await client.delete("/cache/aapl")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"


class TestRequestValidation:
    """Tests for request validation."""
    
    @pytest.mark.asyncio
    async def test_safety_check_validates_allocation_range(self, client):
        """Test allocation percentage validation."""
        # Test upper bound
        response = await client.post(
            "/safety-check",
            json={"ticker": "AAPL", "allocation_pct": 101.0}
        )
        assert response.status_code == 422
        
        # Test lower bound
        response = await client.post(
            "/safety-check",
            json={"ticker": "AAPL", "allocation_pct": -1.0}
        )
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_index_filing_validates_cik_length(self, client):
        """Test CIK validation."""
        response = await client.post(
            "/index-filing",
            json={
                "ticker": "AAPL",
                "cik": "123",  # Too short
                "filing_type": "10-K",
                "filing_date": "2024-01-15",
                "accession_number": "0000320193-24-000001",
                "primary_document": "aapl-20240115.htm",
                "filing_url": "https://www.sec.gov/test"
            }
        )
        
        assert response.status_code == 422
