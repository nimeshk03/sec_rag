"""
Supabase Store Interface for SEC Filing RAG System.

Provides CRUD operations for filings, chunks, cache, safety logs, and earnings.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
import numpy as np

from .supabase import get_supabase


@dataclass
class Filing:
    """Filing metadata."""
    ticker: str
    filing_type: str
    filing_date: date
    accession_number: str
    fiscal_period: Optional[str] = None
    fiscal_year: Optional[int] = None
    source_url: Optional[str] = None
    id: Optional[str] = None
    processed_at: Optional[datetime] = None


@dataclass
class Chunk:
    """Text chunk with embedding."""
    filing_id: str
    section_name: str
    content: str
    chunk_index: int
    embedding: Optional[np.ndarray] = None
    total_chunks: Optional[int] = None
    word_count: Optional[int] = None
    id: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class SearchResult:
    """Vector search result."""
    id: str
    content: str
    section_name: str
    filing_type: str
    filing_date: date
    similarity: float


@dataclass
class SafetyLog:
    """Safety check audit log entry."""
    ticker: str
    proposed_allocation: float
    current_allocation: float
    decision: str
    reasoning: str
    risk_score: int
    risks: Dict[str, Any] = field(default_factory=dict)
    chunks_retrieved: int = 0
    latency_ms: int = 0
    cached: bool = False
    rl_allocation: Optional[float] = None
    final_allocation: Optional[float] = None
    id: Optional[str] = None
    timestamp: Optional[datetime] = None


@dataclass
class EarningsEntry:
    """Earnings calendar entry."""
    ticker: str
    earnings_date: date
    time_of_day: str = "UNKNOWN"
    fiscal_quarter: Optional[str] = None
    source: Optional[str] = None
    id: Optional[str] = None
    updated_at: Optional[datetime] = None


class SupabaseStore:
    """
    Supabase store interface for the RAG system.
    
    Provides operations for:
    - Filings: insert, get, query
    - Chunks: insert batch, vector search
    - Cache: get, set, invalidate
    - Safety logs: log, query history
    - Earnings: get next, update
    """
    
    DEFAULT_CACHE_TTL_HOURS = 24
    
    def __init__(self, client=None):
        """
        Initialize store with optional client injection for testing.
        
        Args:
            client: Optional Supabase client (uses singleton if not provided)
        """
        self._client = client
    
    @property
    def client(self):
        """Lazy load Supabase client."""
        if self._client is None:
            self._client = get_supabase()
        return self._client
    
    # =========================================================================
    # Filing Operations
    # =========================================================================
    
    def insert_filing(self, filing: Filing) -> str:
        """
        Insert a filing record.
        
        Args:
            filing: Filing metadata to insert
            
        Returns:
            UUID of inserted filing
            
        Raises:
            Exception: If insert fails
        """
        data = {
            "ticker": filing.ticker,
            "filing_type": filing.filing_type,
            "filing_date": filing.filing_date.isoformat(),
            "accession_number": filing.accession_number,
        }
        
        if filing.fiscal_period:
            data["fiscal_period"] = filing.fiscal_period
        if filing.fiscal_year:
            data["fiscal_year"] = filing.fiscal_year
        if filing.source_url:
            data["source_url"] = filing.source_url
            
        result = self.client.table("filings").insert(data).execute()
        
        if not result.data:
            raise Exception("Failed to insert filing")
            
        return result.data[0]["id"]
    
    def get_filing(
        self,
        ticker: str,
        filing_date: Optional[date] = None,
        filing_type: Optional[str] = None
    ) -> Optional[Filing]:
        """
        Get a filing by ticker and optional filters.
        
        Args:
            ticker: Stock ticker symbol
            filing_date: Optional specific filing date
            filing_type: Optional filing type filter
            
        Returns:
            Filing if found, None otherwise
        """
        query = self.client.table("filings").select("*").eq("ticker", ticker)
        
        if filing_date:
            query = query.eq("filing_date", filing_date.isoformat())
        if filing_type:
            query = query.eq("filing_type", filing_type)
            
        query = query.order("filing_date", desc=True).limit(1)
        result = query.execute()
        
        if not result.data:
            return None
            
        row = result.data[0]
        return Filing(
            id=row["id"],
            ticker=row["ticker"],
            filing_type=row["filing_type"],
            filing_date=date.fromisoformat(row["filing_date"]),
            accession_number=row["accession_number"],
            fiscal_period=row.get("fiscal_period"),
            fiscal_year=row.get("fiscal_year"),
            source_url=row.get("source_url"),
            processed_at=row.get("processed_at"),
        )
    
    def get_filing_by_id(self, filing_id: str) -> Optional[Filing]:
        """
        Get a filing by its UUID.
        
        Args:
            filing_id: Filing UUID
            
        Returns:
            Filing if found, None otherwise
        """
        result = self.client.table("filings").select("*").eq("id", filing_id).execute()
        
        if not result.data:
            return None
            
        row = result.data[0]
        return Filing(
            id=row["id"],
            ticker=row["ticker"],
            filing_type=row["filing_type"],
            filing_date=date.fromisoformat(row["filing_date"]),
            accession_number=row["accession_number"],
            fiscal_period=row.get("fiscal_period"),
            fiscal_year=row.get("fiscal_year"),
            source_url=row.get("source_url"),
            processed_at=row.get("processed_at"),
        )
    
    def get_recent_filings(
        self,
        ticker: Optional[str] = None,
        filing_type: Optional[str] = None,
        days_back: int = 365,
        limit: int = 50
    ) -> List[Filing]:
        """
        Get recent filings with optional filters.
        
        Args:
            ticker: Optional ticker filter
            filing_type: Optional filing type filter
            days_back: Number of days to look back
            limit: Maximum number of results
            
        Returns:
            List of matching filings
        """
        cutoff_date = (datetime.now() - timedelta(days=days_back)).date()
        
        query = self.client.table("filings").select("*")
        query = query.gte("filing_date", cutoff_date.isoformat())
        
        if ticker:
            query = query.eq("ticker", ticker)
        if filing_type:
            query = query.eq("filing_type", filing_type)
            
        query = query.order("filing_date", desc=True).limit(limit)
        result = query.execute()
        
        filings = []
        for row in result.data:
            filings.append(Filing(
                id=row["id"],
                ticker=row["ticker"],
                filing_type=row["filing_type"],
                filing_date=date.fromisoformat(row["filing_date"]),
                accession_number=row["accession_number"],
                fiscal_period=row.get("fiscal_period"),
                fiscal_year=row.get("fiscal_year"),
                source_url=row.get("source_url"),
                processed_at=row.get("processed_at"),
            ))
            
        return filings
    
    def delete_filing(self, filing_id: str) -> bool:
        """
        Delete a filing and its chunks (cascades).
        
        Args:
            filing_id: Filing UUID to delete
            
        Returns:
            True if deleted, False if not found
        """
        result = self.client.table("filings").delete().eq("id", filing_id).execute()
        return len(result.data) > 0
    
    # =========================================================================
    # Chunk Operations
    # =========================================================================
    
    def insert_chunks(self, chunks: List[Chunk]) -> List[str]:
        """
        Batch insert chunks with embeddings.
        
        Args:
            chunks: List of chunks to insert
            
        Returns:
            List of inserted chunk UUIDs
        """
        if not chunks:
            return []
            
        data = []
        for chunk in chunks:
            chunk_data = {
                "filing_id": chunk.filing_id,
                "section_name": chunk.section_name,
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
            }
            
            if chunk.embedding is not None:
                # Convert numpy array to list for JSON serialization
                embedding_list = chunk.embedding.tolist()
                chunk_data["embedding"] = embedding_list
                
            if chunk.total_chunks is not None:
                chunk_data["total_chunks"] = chunk.total_chunks
            if chunk.word_count is not None:
                chunk_data["word_count"] = chunk.word_count
                
            data.append(chunk_data)
        
        result = self.client.table("chunks").insert(data).execute()
        
        if not result.data:
            raise Exception("Failed to insert chunks")
            
        return [row["id"] for row in result.data]
    
    def get_chunks_by_filing(self, filing_id: str) -> List[Chunk]:
        """
        Get all chunks for a filing.
        
        Args:
            filing_id: Filing UUID
            
        Returns:
            List of chunks ordered by index
        """
        result = (
            self.client.table("chunks")
            .select("*")
            .eq("filing_id", filing_id)
            .order("chunk_index")
            .execute()
        )
        
        chunks = []
        for row in result.data:
            embedding = None
            if row.get("embedding"):
                embedding = np.array(row["embedding"])
                
            chunks.append(Chunk(
                id=row["id"],
                filing_id=row["filing_id"],
                section_name=row["section_name"],
                content=row["content"],
                chunk_index=row["chunk_index"],
                embedding=embedding,
                total_chunks=row.get("total_chunks"),
                word_count=row.get("word_count"),
                created_at=row.get("created_at"),
            ))
            
        return chunks
    
    def vector_search(
        self,
        query_embedding: np.ndarray,
        ticker: str,
        match_count: int = 10,
        days_back: int = 365,
        filing_types: Optional[List[str]] = None,
        section_names: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """
        Perform semantic similarity search using pgvector.
        
        Args:
            query_embedding: 384-dimensional query embedding
            ticker: Stock ticker to search
            match_count: Number of results to return
            days_back: How far back to search
            filing_types: Optional list of filing types to filter
            section_names: Optional list of section names to filter
            
        Returns:
            List of search results ordered by similarity
        """
        # Convert numpy array to list for RPC call
        embedding_list = query_embedding.tolist()
        
        params = {
            "query_embedding": embedding_list,
            "match_ticker": ticker,
            "match_count": match_count,
            "days_back": days_back,
        }
        
        if filing_types:
            params["filing_types"] = filing_types
        if section_names:
            params["section_names"] = section_names
            
        result = self.client.rpc("match_chunks", params).execute()
        
        results = []
        for row in result.data:
            results.append(SearchResult(
                id=row["id"],
                content=row["content"],
                section_name=row["section_name"],
                filing_type=row["filing_type"],
                filing_date=date.fromisoformat(row["filing_date"]),
                similarity=row["similarity"],
            ))
            
        return results
    
    def delete_chunks_by_filing(self, filing_id: str) -> int:
        """
        Delete all chunks for a filing.
        
        Args:
            filing_id: Filing UUID
            
        Returns:
            Number of deleted chunks
        """
        result = self.client.table("chunks").delete().eq("filing_id", filing_id).execute()
        return len(result.data)
    
    # =========================================================================
    # Cache Operations
    # =========================================================================
    
    @staticmethod
    def _generate_cache_key(
        ticker: str,
        query: str,
        additional_params: Optional[Dict] = None
    ) -> str:
        """Generate a deterministic cache key."""
        key_parts = [ticker.upper(), query.lower().strip()]
        
        if additional_params:
            # Sort for deterministic ordering
            sorted_params = sorted(additional_params.items())
            key_parts.append(json.dumps(sorted_params))
            
        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached response if not expired.
        
        Args:
            cache_key: Cache key to look up
            
        Returns:
            Cached response dict if valid, None if expired or not found
        """
        result = (
            self.client.table("cache")
            .select("*")
            .eq("cache_key", cache_key)
            .execute()
        )
        
        if not result.data:
            return None
            
        row = result.data[0]
        expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        
        # Check if expired
        if expires_at < datetime.now(expires_at.tzinfo):
            return None
            
        # Increment hit count
        self.client.table("cache").update(
            {"hit_count": row["hit_count"] + 1}
        ).eq("id", row["id"]).execute()
        
        return row["response"]
    
    def set_cached_response(
        self,
        cache_key: str,
        response: Dict[str, Any],
        ttl_hours: Optional[int] = None
    ) -> str:
        """
        Store response in cache.
        
        Args:
            cache_key: Cache key
            response: Response data to cache
            ttl_hours: Time to live in hours (default: 24)
            
        Returns:
            Cache entry UUID
        """
        if ttl_hours is None:
            ttl_hours = self.DEFAULT_CACHE_TTL_HOURS
            
        expires_at = datetime.now() + timedelta(hours=ttl_hours)
        
        data = {
            "cache_key": cache_key,
            "response": response,
            "expires_at": expires_at.isoformat(),
            "hit_count": 0,
        }
        
        # Upsert to handle existing keys
        result = (
            self.client.table("cache")
            .upsert(data, on_conflict="cache_key")
            .execute()
        )
        
        if not result.data:
            raise Exception("Failed to set cache")
            
        return result.data[0]["id"]
    
    def invalidate_cache(self, pattern: Optional[str] = None) -> int:
        """
        Invalidate cache entries.
        
        Args:
            pattern: Optional pattern to match cache keys (uses LIKE)
                     If None, invalidates all expired entries
                     
        Returns:
            Number of invalidated entries
        """
        if pattern:
            # Delete matching pattern
            result = (
                self.client.table("cache")
                .delete()
                .like("cache_key", f"%{pattern}%")
                .execute()
            )
            return len(result.data)
        else:
            # Clean expired entries using RPC function
            result = self.client.rpc("clean_expired_cache").execute()
            return result.data if isinstance(result.data, int) else 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache stats
        """
        result = self.client.rpc("get_cache_stats").execute()
        
        if result.data:
            return result.data[0] if isinstance(result.data, list) else result.data
        return {}
    
    # =========================================================================
    # Safety Log Operations
    # =========================================================================
    
    def log_safety_check(self, log: SafetyLog) -> str:
        """
        Log a safety check for audit trail.
        
        Args:
            log: Safety log entry
            
        Returns:
            Log entry UUID
        """
        data = {
            "ticker": log.ticker,
            "proposed_allocation": log.proposed_allocation,
            "current_allocation": log.current_allocation,
            "decision": log.decision,
            "reasoning": log.reasoning,
            "risk_score": log.risk_score,
            "risks": log.risks,
            "chunks_retrieved": log.chunks_retrieved,
            "latency_ms": log.latency_ms,
            "cached": log.cached,
        }
        
        if log.rl_allocation is not None:
            data["rl_allocation"] = log.rl_allocation
        if log.final_allocation is not None:
            data["final_allocation"] = log.final_allocation
            
        result = self.client.table("safety_logs").insert(data).execute()
        
        if not result.data:
            raise Exception("Failed to log safety check")
            
        return result.data[0]["id"]
    
    def get_safety_history(
        self,
        ticker: Optional[str] = None,
        decision: Optional[str] = None,
        days_back: int = 30,
        limit: int = 100
    ) -> List[SafetyLog]:
        """
        Query safety check history.
        
        Args:
            ticker: Optional ticker filter
            decision: Optional decision filter (PROCEED, REDUCE, VETO)
            days_back: Number of days to look back
            limit: Maximum number of results
            
        Returns:
            List of safety log entries
        """
        cutoff = datetime.now() - timedelta(days=days_back)
        
        query = self.client.table("safety_logs").select("*")
        query = query.gte("timestamp", cutoff.isoformat())
        
        if ticker:
            query = query.eq("ticker", ticker)
        if decision:
            query = query.eq("decision", decision)
            
        query = query.order("timestamp", desc=True).limit(limit)
        result = query.execute()
        
        logs = []
        for row in result.data:
            logs.append(SafetyLog(
                id=row["id"],
                timestamp=row.get("timestamp"),
                ticker=row["ticker"],
                proposed_allocation=row["proposed_allocation"],
                current_allocation=row["current_allocation"],
                decision=row["decision"],
                reasoning=row["reasoning"],
                risk_score=row["risk_score"],
                risks=row.get("risks", {}),
                chunks_retrieved=row.get("chunks_retrieved", 0),
                latency_ms=row.get("latency_ms", 0),
                cached=row.get("cached", False),
                rl_allocation=row.get("rl_allocation"),
                final_allocation=row.get("final_allocation"),
            ))
            
        return logs
    
    def get_safety_stats(
        self,
        ticker: Optional[str] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Get aggregated safety check statistics.
        
        Args:
            ticker: Optional ticker filter
            days_back: Number of days to analyze
            
        Returns:
            Dict with statistics
        """
        logs = self.get_safety_history(ticker=ticker, days_back=days_back, limit=1000)
        
        if not logs:
            return {
                "total_checks": 0,
                "proceed_count": 0,
                "reduce_count": 0,
                "veto_count": 0,
                "avg_risk_score": 0,
                "avg_latency_ms": 0,
                "cache_hit_rate": 0,
            }
        
        total = len(logs)
        proceed = sum(1 for log in logs if log.decision == "PROCEED")
        reduce = sum(1 for log in logs if log.decision == "REDUCE")
        veto = sum(1 for log in logs if log.decision == "VETO")
        cached = sum(1 for log in logs if log.cached)
        
        return {
            "total_checks": total,
            "proceed_count": proceed,
            "reduce_count": reduce,
            "veto_count": veto,
            "avg_risk_score": sum(log.risk_score for log in logs) / total,
            "avg_latency_ms": sum(log.latency_ms for log in logs) / total,
            "cache_hit_rate": cached / total if total > 0 else 0,
        }
    
    # =========================================================================
    # Earnings Calendar Operations
    # =========================================================================
    
    def get_next_earnings(
        self,
        ticker: str,
        after_date: Optional[date] = None
    ) -> Optional[EarningsEntry]:
        """
        Get next upcoming earnings date for a ticker.
        
        Args:
            ticker: Stock ticker
            after_date: Date to search after (default: today)
            
        Returns:
            Next earnings entry if found
        """
        if after_date is None:
            after_date = date.today()
            
        result = (
            self.client.table("earnings_calendar")
            .select("*")
            .eq("ticker", ticker)
            .gte("earnings_date", after_date.isoformat())
            .order("earnings_date")
            .limit(1)
            .execute()
        )
        
        if not result.data:
            return None
            
        row = result.data[0]
        return EarningsEntry(
            id=row["id"],
            ticker=row["ticker"],
            earnings_date=date.fromisoformat(row["earnings_date"]),
            time_of_day=row.get("time_of_day", "UNKNOWN"),
            fiscal_quarter=row.get("fiscal_quarter"),
            source=row.get("source"),
            updated_at=row.get("updated_at"),
        )
    
    def get_upcoming_earnings(
        self,
        days_ahead: int = 14,
        tickers: Optional[List[str]] = None
    ) -> List[EarningsEntry]:
        """
        Get all upcoming earnings within a time window.
        
        Args:
            days_ahead: Number of days to look ahead
            tickers: Optional list of tickers to filter
            
        Returns:
            List of upcoming earnings entries
        """
        today = date.today()
        end_date = today + timedelta(days=days_ahead)
        
        query = (
            self.client.table("earnings_calendar")
            .select("*")
            .gte("earnings_date", today.isoformat())
            .lte("earnings_date", end_date.isoformat())
        )
        
        if tickers:
            query = query.in_("ticker", tickers)
            
        query = query.order("earnings_date")
        result = query.execute()
        
        entries = []
        for row in result.data:
            entries.append(EarningsEntry(
                id=row["id"],
                ticker=row["ticker"],
                earnings_date=date.fromisoformat(row["earnings_date"]),
                time_of_day=row.get("time_of_day", "UNKNOWN"),
                fiscal_quarter=row.get("fiscal_quarter"),
                source=row.get("source"),
                updated_at=row.get("updated_at"),
            ))
            
        return entries
    
    def update_earnings(self, entry: EarningsEntry) -> str:
        """
        Insert or update an earnings calendar entry.
        
        Args:
            entry: Earnings entry to upsert
            
        Returns:
            Entry UUID
        """
        data = {
            "ticker": entry.ticker,
            "earnings_date": entry.earnings_date.isoformat(),
            "time_of_day": entry.time_of_day,
            "updated_at": datetime.now().isoformat(),
        }
        
        if entry.fiscal_quarter:
            data["fiscal_quarter"] = entry.fiscal_quarter
        if entry.source:
            data["source"] = entry.source
            
        # Upsert based on unique constraint
        result = (
            self.client.table("earnings_calendar")
            .upsert(data, on_conflict="ticker,earnings_date")
            .execute()
        )
        
        if not result.data:
            raise Exception("Failed to update earnings")
            
        return result.data[0]["id"]
    
    def delete_earnings(self, ticker: str, earnings_date: date) -> bool:
        """
        Delete an earnings calendar entry.
        
        Args:
            ticker: Stock ticker
            earnings_date: Earnings date
            
        Returns:
            True if deleted
        """
        result = (
            self.client.table("earnings_calendar")
            .delete()
            .eq("ticker", ticker)
            .eq("earnings_date", earnings_date.isoformat())
            .execute()
        )
        return len(result.data) > 0
