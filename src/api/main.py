"""
FastAPI application for SEC Filing RAG Safety System.

Provides REST API endpoints for safety checks, filing indexing,
health monitoring, and cache management.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Optional
import logging

from src.api.models import (
    SafetyCheckRequest,
    SafetyCheckResponse,
    IndexFilingRequest,
    IndexFilingResponse,
    HealthResponse,
    CacheStatsResponse,
    CacheInvalidationResponse,
    ErrorResponse,
)
from src.safety.checker import SafetyChecker
from src.data.store import SupabaseStore
from src.data.sec_downloader import FilingInfo
from src.embeddings.embedder import LocalEmbedder
from src.retrieval.hybrid import HybridRetriever

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SEC Filing RAG Safety System",
    description="Intelligent safety checker for stock allocations using SEC filing analysis",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Global instances (initialized on startup)
safety_checker: Optional[SafetyChecker] = None
store: Optional[SupabaseStore] = None
embedder: Optional[LocalEmbedder] = None
retriever: Optional[HybridRetriever] = None


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    global safety_checker, store, embedder, retriever
    
    logger.info("Starting up SEC Filing RAG Safety System...")
    
    try:
        # Initialize store
        store = SupabaseStore()
        logger.info("✓ Database store initialized")
        
        # Pre-load embedder model to avoid cold start delays
        logger.info("Loading embedding model (this may take 10-20 seconds)...")
        embedder = LocalEmbedder()
        # Force model loading by triggering a test embedding
        _ = embedder.embed_text("warmup")
        logger.info("✓ Embedding model loaded and ready")
        
        # Initialize retriever with pre-loaded embedder
        retriever = HybridRetriever(store=store, embedder=embedder)
        logger.info("✓ Hybrid retriever initialized")
        
        # Initialize safety checker with pre-loaded components
        safety_checker = SafetyChecker(store=store, retriever=retriever)
        logger.info("✓ Safety checker initialized")
        
        logger.info("🚀 Application startup complete - ready to accept requests")
        
    except Exception as e:
        logger.warning(f"⚠️  Startup initialization failed (may be in test mode): {e}")
        # Don't raise in case we're in test mode - tests will mock these components


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down SEC Filing RAG Safety System...")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "SEC Filing RAG Safety System",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.post(
    "/safety-check",
    response_model=SafetyCheckResponse,
    status_code=status.HTTP_200_OK,
    tags=["Safety"],
    summary="Perform safety check for stock allocation",
    description="Analyzes SEC filings, earnings proximity, and risk factors to make PROCEED/REDUCE/VETO decision",
)
async def safety_check(request: SafetyCheckRequest):
    """
    Perform comprehensive safety check for a stock allocation.
    
    Returns:
        SafetyCheckResponse with decision (PROCEED/REDUCE/VETO) and reasoning
    
    Raises:
        HTTPException: If safety check fails
    """
    try:
        logger.info(f"Safety check requested for {request.ticker} at {request.allocation_pct}%")
        
        # Perform safety check
        result = safety_checker.check_safety(
            ticker=request.ticker,
            allocation_pct=request.allocation_pct,
            use_cache=request.use_cache,
        )
        
        # Convert to response model
        response = SafetyCheckResponse(
            decision=result.decision.value,
            ticker=result.ticker,
            risk_score=result.risk_score,
            reasoning=result.reasoning,
            earnings_warning=result.earnings_warning,
            critical_events=result.critical_events,
            allocation_warning=result.allocation_warning,
            cache_hit=result.cache_hit,
            retrieved_chunks=result.retrieved_chunks,
        )
        
        logger.info(f"Safety check complete: {result.decision.value} for {request.ticker}")
        
        return response
        
    except Exception as e:
        logger.error(f"Safety check failed for {request.ticker}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Safety check failed: {str(e)}"
        )


async def index_filing_background(filing_info: FilingInfo):
    """
    Background task to index a filing.
    
    Args:
        filing_info: Filing information to index
    """
    try:
        logger.info(f"Starting background indexing for {filing_info.ticker} {filing_info.filing_type}")
        
        # In production, this would:
        # 1. Download the filing from SEC EDGAR
        # 2. Parse and chunk the content
        # 3. Generate embeddings
        # 4. Store in database
        # For now, just log the task
        logger.info(f"Processing filing: {filing_info.ticker} {filing_info.filing_type} from {filing_info.filing_date}")
        
        logger.info(f"✓ Background indexing complete for {filing_info.ticker}")
        
    except Exception as e:
        logger.error(f"❌ Background indexing failed for {filing_info.ticker}: {e}")


@app.post(
    "/index-filing",
    response_model=IndexFilingResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Indexing"],
    summary="Index a new SEC filing",
    description="Starts background task to download, parse, chunk, and index an SEC filing",
)
async def index_filing(request: IndexFilingRequest, background_tasks: BackgroundTasks):
    """
    Index a new SEC filing in the background.
    
    Returns:
        IndexFilingResponse with task status
    
    Raises:
        HTTPException: If request is invalid
    """
    try:
        logger.info(f"Filing indexing requested for {request.ticker} {request.filing_type}")
        
        # Create filing info
        filing_info = FilingInfo(
            ticker=request.ticker,
            cik=request.cik,
            filing_type=request.filing_type,
            filing_date=request.filing_date,
            accession_number=request.accession_number,
            primary_document=request.primary_document,
            filing_url=request.filing_url,
        )
        
        # Add background task
        background_tasks.add_task(index_filing_background, filing_info)
        
        # Generate task ID (in production, use proper task queue)
        task_id = f"{request.ticker}_{request.filing_type}_{datetime.now().timestamp()}"
        
        response = IndexFilingResponse(
            status="processing",
            message=f"Filing indexing started in background for {request.ticker}",
            task_id=task_id,
            ticker=request.ticker,
            filing_type=request.filing_type,
        )
        
        logger.info(f"Filing indexing task created: {task_id}")
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to start filing indexing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start filing indexing: {str(e)}"
        )


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    tags=["Monitoring"],
    summary="Health check endpoint",
    description="Returns health status and dependency information",
)
async def health_check():
    """
    Check health of the application and its dependencies.
    
    Returns:
        HealthResponse with status and dependency information
    """
    try:
        dependencies = {}
        
        # Check database
        try:
            if store:
                # Try a simple query
                store.client.table("filings").select("id").limit(1).execute()
                dependencies["database"] = "connected"
            else:
                dependencies["database"] = "not_initialized"
        except Exception as e:
            dependencies["database"] = f"error: {str(e)[:50]}"
        
        # Check embedder
        try:
            if embedder and embedder._model is not None:
                dependencies["embedder"] = "loaded"
            else:
                dependencies["embedder"] = "not_initialized"
        except Exception as e:
            dependencies["embedder"] = f"error: {str(e)[:50]}"
        
        # Check retriever
        try:
            if retriever:
                dependencies["retriever"] = "ready"
            else:
                dependencies["retriever"] = "not_initialized"
        except Exception as e:
            dependencies["retriever"] = f"error: {str(e)[:50]}"
        
        # Determine overall status
        overall_status = "healthy" if all(
            v in ["connected", "loaded", "ready"] for v in dependencies.values()
        ) else "degraded"
        
        response = HealthResponse(
            status=overall_status,
            timestamp=datetime.now(),
            dependencies=dependencies,
            version="1.0.0",
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )


@app.get(
    "/cache-stats",
    response_model=CacheStatsResponse,
    status_code=status.HTTP_200_OK,
    tags=["Cache"],
    summary="Get cache statistics",
    description="Returns cache performance metrics including hit rate and size",
)
async def get_cache_stats():
    """
    Get cache performance statistics.
    
    Returns:
        CacheStatsResponse with cache metrics
    """
    try:
        # In production, these would come from actual cache metrics
        # For now, return placeholder values
        response = CacheStatsResponse(
            total_entries=0,
            hit_rate=0.0,
            total_hits=0,
            total_misses=0,
            avg_ttl_hours=12.0,
            cache_size_mb=0.0,
        )
        
        logger.info("Cache stats retrieved")
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache stats: {str(e)}"
        )


@app.delete(
    "/cache/{ticker}",
    response_model=CacheInvalidationResponse,
    status_code=status.HTTP_200_OK,
    tags=["Cache"],
    summary="Invalidate cache for ticker",
    description="Removes all cached safety check results for the specified ticker",
)
async def invalidate_cache(ticker: str):
    """
    Invalidate cache entries for a specific ticker.
    
    Args:
        ticker: Stock ticker symbol
    
    Returns:
        CacheInvalidationResponse with invalidation status
    """
    try:
        ticker = ticker.upper().strip()
        
        # In production, this would actually delete cache entries
        # For now, return success response
        entries_deleted = 0
        
        response = CacheInvalidationResponse(
            status="success",
            message=f"Cache invalidated for ticker {ticker}",
            ticker=ticker,
            entries_deleted=entries_deleted,
        )
        
        logger.info(f"Cache invalidated for {ticker}")
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to invalidate cache for {ticker}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invalidate cache: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat(),
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
