"""
Pydantic models for API request/response validation.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum


class SafetyDecisionEnum(str, Enum):
    """Safety decision outcomes."""
    PROCEED = "PROCEED"
    REDUCE = "REDUCE"
    VETO = "VETO"


class SafetyCheckRequest(BaseModel):
    """Request model for safety check endpoint."""
    ticker: str = Field(..., description="Stock ticker symbol", min_length=1, max_length=10)
    allocation_pct: float = Field(..., description="Proposed allocation percentage (0-100)", ge=0, le=100)
    use_cache: bool = Field(True, description="Whether to use cached results")
    
    @validator('ticker')
    def ticker_uppercase(cls, v):
        """Convert ticker to uppercase."""
        return v.upper().strip()
    
    class Config:
        schema_extra = {
            "example": {
                "ticker": "AAPL",
                "allocation_pct": 12.5,
                "use_cache": True
            }
        }


class SafetyCheckResponse(BaseModel):
    """Response model for safety check endpoint."""
    decision: SafetyDecisionEnum
    ticker: str
    risk_score: float
    reasoning: str
    earnings_warning: Optional[str] = None
    critical_events: Optional[List[str]] = None
    allocation_warning: Optional[str] = None
    cache_hit: bool = False
    retrieved_chunks: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        schema_extra = {
            "example": {
                "decision": "REDUCE",
                "ticker": "AAPL",
                "risk_score": 6.5,
                "reasoning": "Elevated risk score (6.5); Earnings in 2 days with high allocation (18.0%)",
                "earnings_warning": "WARNING: Earnings for AAPL in 2 day(s) on 2024-01-17 (AMC)",
                "critical_events": None,
                "allocation_warning": "High allocation: 18.0%",
                "cache_hit": False,
                "retrieved_chunks": [
                    {
                        "content": "The company faces litigation risks...",
                        "section": "1A",
                        "filing_type": "10-K",
                        "score": 0.85
                    }
                ]
            }
        }


class IndexFilingRequest(BaseModel):
    """Request model for filing indexing endpoint."""
    ticker: str = Field(..., description="Stock ticker symbol", min_length=1, max_length=10)
    cik: str = Field(..., description="CIK number", min_length=10, max_length=10)
    filing_type: str = Field(..., description="Filing type (10-K, 10-Q, 8-K)")
    filing_date: date = Field(..., description="Filing date")
    accession_number: str = Field(..., description="SEC accession number")
    primary_document: str = Field(..., description="Primary document filename")
    filing_url: str = Field(..., description="URL to the filing")
    
    @validator('ticker')
    def ticker_uppercase(cls, v):
        """Convert ticker to uppercase."""
        return v.upper().strip()
    
    @validator('filing_type')
    def filing_type_valid(cls, v):
        """Validate filing type."""
        valid_types = ["10-K", "10-Q", "8-K"]
        if v not in valid_types:
            raise ValueError(f"Filing type must be one of {valid_types}")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "ticker": "AAPL",
                "cik": "0000320193",
                "filing_type": "10-K",
                "filing_date": "2024-01-15",
                "accession_number": "0000320193-24-000001",
                "primary_document": "aapl-20240115.htm",
                "filing_url": "https://www.sec.gov/..."
            }
        }


class IndexFilingResponse(BaseModel):
    """Response model for filing indexing endpoint."""
    status: str
    message: str
    task_id: Optional[str] = None
    ticker: str
    filing_type: str
    
    class Config:
        schema_extra = {
            "example": {
                "status": "processing",
                "message": "Filing indexing started in background",
                "task_id": "abc123",
                "ticker": "AAPL",
                "filing_type": "10-K"
            }
        }


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str
    timestamp: datetime
    dependencies: Dict[str, str]
    version: str = "1.0.0"
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00",
                "dependencies": {
                    "database": "connected",
                    "embedder": "loaded",
                    "retriever": "ready"
                },
                "version": "1.0.0"
            }
        }


class CacheStatsResponse(BaseModel):
    """Response model for cache stats endpoint."""
    total_entries: int
    hit_rate: float
    total_hits: int
    total_misses: int
    avg_ttl_hours: float
    cache_size_mb: Optional[float] = None
    
    class Config:
        schema_extra = {
            "example": {
                "total_entries": 150,
                "hit_rate": 0.72,
                "total_hits": 1080,
                "total_misses": 420,
                "avg_ttl_hours": 12.5,
                "cache_size_mb": 2.3
            }
        }


class CacheInvalidationResponse(BaseModel):
    """Response model for cache invalidation endpoint."""
    status: str
    message: str
    ticker: str
    entries_deleted: int
    
    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "message": "Cache invalidated for ticker AAPL",
                "ticker": "AAPL",
                "entries_deleted": 5
            }
        }


class ErrorResponse(BaseModel):
    """Response model for errors."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime
    
    class Config:
        schema_extra = {
            "example": {
                "error": "Validation Error",
                "detail": "allocation_pct must be between 0 and 100",
                "timestamp": "2024-01-15T10:30:00"
            }
        }
