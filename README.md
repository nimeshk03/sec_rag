# RAG Safety System
## SEC Filing Analysis for Portfolio Risk Detection

A Retrieval-Augmented Generation (RAG) system that analyzes SEC filings to detect material risks before trade execution.

## Features

- **Recent Events Check** - Analyze 8-K filings from last 14 days
- **Risk Factor Analysis** - Extract and score Item 1A risks from 10-K
- **Earnings Proximity** - Flag trades near earnings announcements
- **Fundamental Alignment** - Validate allocation vs risk profile

## Quick Start with Docker

### Prerequisites

- Docker and Docker Compose installed
- **Where to get credentials:**
- **Supabase**: Sign up at supabase.com → Create project → Copy URL and anon key from Settings > API
- **Groq (FREE)**: Sign up at console.groq.com → Create API key (no credit card needed)

### Setup

1. Clone the repository:
```bash
cd /home/nimeshk03/Documents/risk_analysis_RAG
```

2. Copy environment template:
```bash
cp .env.example .env
```

3. Edit `.env` and add your credentials:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key-here
GROQ_API_KEY=gsk-your-groq-api-key-here
```

**Get your FREE Groq API key:**
- Go to [console.groq.com](https://console.groq.com)
- Sign up (no credit card needed)
- Create API key at [console.groq.com/keys](https://console.groq.com/keys)
- See [GROQ_SETUP.md](GROQ_SETUP.md) for detailed instructions

4. Build and start the container:

**On Fedora/RHEL (using Podman):**
```bash
pip install --user podman-compose
podman-compose up --build
```

**On other systems (using Docker):**
```bash
docker-compose up --build
```

See [PODMAN_SETUP.md](PODMAN_SETUP.md) for Fedora-specific instructions.

5. Verify the API is running:
```bash
curl http://localhost:8000/health
```

6. **Initialize the Database:**
   - Copy the contents of `scripts/schema.sql`
   - Go to your Supabase Dashboard > SQL Editor
   - Paste and run the SQL to create tables and functions

### Development Mode

For development with hot-reload:
```bash
docker-compose up
```

Code changes in `src/` will automatically reload the server.

### Stop the Service

```bash
docker-compose down
```

## API Endpoints

### POST /safety-check
Check if a proposed trade is safe based on SEC filing analysis.

**Request:**
```json
{
  "ticker": "NVDA",
  "proposed_allocation": 0.25,
  "current_allocation": 0.15
}
```

**Response:**
```json
{
  "decision": "PROCEED",
  "reasoning": "No significant risks identified. Risk score: 4/10",
  "risk_score": 4,
  "risks": [],
  "earnings_days": 15,
  "cached": false,
  "latency_ms": 1234
}
```

### GET /health
Health check endpoint.

### GET /cache-stats
Cache performance metrics.

### DELETE /cache/{ticker}
Invalidate cache for a specific ticker.

## SEC Filing Parser

The `SECFilingParser` class extracts structured sections from SEC filings:

```python
from src.data import SECFilingParser

parser = SECFilingParser()

# Parse a 10-K filing
sections = parser.parse_10k(html_content)
risk_factors = sections.get("1A")  # Item 1A: Risk Factors
mda = sections.get("7")            # Item 7: MD&A

# Parse a 10-Q filing
sections = parser.parse_10q(html_content)
quarterly_mda = sections.get("2")  # Item 2: MD&A

# Parse an 8-K filing
sections = parser.parse_8k(html_content)
events = sections.get("8.01")      # Item 8.01: Other Events

# Convenience methods
risk_text = parser.get_risk_factors(html_content)
mda_text = parser.get_mda(html_content, filing_type="10-K")
```

**Supported Sections:**
- **10-K**: Items 1, 1A, 7, 7A, 8 (Business, Risk Factors, MD&A, Market Risk, Financials)
- **10-Q**: Items 1-4 (Financials, MD&A, Market Risk, Controls)
- **8-K**: All material event items (1.01-9.01)

## Text Chunker

The `FilingChunker` class splits parsed sections into overlapping chunks for embedding:

```python
from src.data import FilingChunker

chunker = FilingChunker(
    chunk_size=800,      # Target chunk size in characters
    chunk_overlap=100,   # Overlap between consecutive chunks
    min_chunk_size=100   # Minimum chunk size to emit
)

# Chunk a single section with metadata
chunks = chunker.chunk_section(
    section_text="Risk factors content...",
    section_name="1A",
    filing_type="10-K",
    ticker="AAPL",
    filing_date="2024-01-15"
)

# Each chunk contains:
# - text: The chunk content
# - chunk_index: Position in sequence
# - metadata: {section, filing_type, ticker, filing_date, chunk_position}

# Chunk an entire filing (multiple sections)
sections = {"1A": "Risk content...", "7": "MD&A content..."}
all_chunks = chunker.chunk_filing(sections, "10-K", "AAPL")
```

**Features:**
- Sentence-boundary detection (breaks at `.`, `!`, `?`, `;`, `:`)
- Configurable overlap for context preservation
- Metadata preservation across chunks
- Minimum chunk size enforcement

## Local Embeddings

The `LocalEmbedder` class generates 384-dimensional embeddings using BGE-small-en-v1.5:

```python
from src.embeddings import LocalEmbedder

embedder = LocalEmbedder(
    model_name="BAAI/bge-small-en-v1.5",  # Default model
    device="cpu",                          # CPU inference
    normalize=True                         # L2 normalize embeddings
)

# Single text embedding
embedding = embedder.embed_text("Risk factors include market volatility...")
# Returns: numpy array of shape (384,)

# Batch embedding
texts = ["Text 1", "Text 2", "Text 3"]
embeddings = embedder.embed_batch(texts, batch_size=32)
# Returns: numpy array of shape (3, 384)

# Query embedding (with BGE instruction prefix for better retrieval)
query_embedding = embedder.embed_query("What are the main risk factors?")

# Compute similarity between embeddings
similarity = embedder.similarity(embedding1, embedding2)
```

**Features:**
- Lazy model loading (loads on first use)
- CPU-optimized for free tier deployments
- BGE instruction prefix for query embeddings
- Batch processing with configurable batch size
- L2 normalization for cosine similarity

## Supabase Store

The `SupabaseStore` class provides a complete interface for database operations:

```python
from src.data import SupabaseStore, Filing, SafetyLog
from datetime import date
import numpy as np

store = SupabaseStore()

# Filing operations
filing = Filing(
    ticker="AAPL",
    filing_type="10-K",
    filing_date=date(2024, 1, 15),
    accession_number="0000320193-24-000001",
)
filing_id = store.insert_filing(filing)
retrieved = store.get_filing("AAPL", filing_type="10-K")
recent = store.get_recent_filings(ticker="AAPL", days_back=365)

# Chunk operations with embeddings
from src.data.store import Chunk
chunks = [
    Chunk(filing_id=filing_id, section_name="1A", content="Risk...", 
          chunk_index=0, embedding=np.random.randn(384))
]
chunk_ids = store.insert_chunks(chunks)

# Vector similarity search
query_embedding = np.random.randn(384)
results = store.vector_search(
    query_embedding=query_embedding,
    ticker="AAPL",
    match_count=10,
    filing_types=["10-K", "10-Q"],
    section_names=["1A", "7"]
)

# Cache operations
cache_key = SupabaseStore._generate_cache_key("AAPL", "risk query")
store.set_cached_response(cache_key, {"decision": "PROCEED"}, ttl_hours=24)
cached = store.get_cached_response(cache_key)  # Returns None if expired

# Safety logging
log = SafetyLog(
    ticker="AAPL",
    proposed_allocation=0.15,
    current_allocation=0.10,
    decision="REDUCE",
    reasoning="High risk due to litigation",
    risk_score=7,
)
store.log_safety_check(log)
history = store.get_safety_history(ticker="AAPL", days_back=30)

# Earnings calendar
from src.data.store import EarningsEntry
entry = EarningsEntry(ticker="AAPL", earnings_date=date(2024, 2, 1), time_of_day="AMC")
store.update_earnings(entry)
next_earnings = store.get_next_earnings("AAPL")
```

**Features:**
- Full CRUD for filings, chunks, cache, safety logs, and earnings
- Vector similarity search using pgvector
- Automatic cache expiration handling
- Batch chunk insertion with embeddings
- Safety check audit trail with statistics

## Data Population

The `populate_data.py` script downloads SEC filings, parses them, generates embeddings, and stores everything in Supabase.

### Supported Tickers

AAPL, AMZN, BAC, GOOGL, JPM, MSFT, NVDA, SPY, TLT, GLD

### Usage

```bash
# Populate all tickers (full run - takes time due to embedding generation)
python scripts/populate_data.py

# Populate specific tickers
python scripts/populate_data.py --tickers AAPL,MSFT,NVDA

# Dry run (no database writes)
python scripts/populate_data.py --dry-run

# Skip embedding generation (faster for testing)
python scripts/populate_data.py --skip-embeddings

# Skip certain filing types
python scripts/populate_data.py --no-10k --no-10q  # Only 8-K filings

# Custom options
python scripts/populate_data.py --days-back-8k 14 --chunk-size 1000
```

### Pipeline Steps

1. **Download** - Fetches filings from SEC EDGAR with rate limiting
2. **Parse** - Extracts sections (Risk Factors, MD&A, etc.)
3. **Chunk** - Splits text into overlapping chunks (800 chars default)
4. **Embed** - Generates 384-dim embeddings using BGE model
5. **Store** - Inserts filings and chunks into Supabase

## Project Structure

```
risk_analysis_RAG/
├── src/
│   ├── api/          # FastAPI application
│   ├── data/         # SEC filing download and parsing
│   │   ├── sec_downloader.py # SECDownloader for EDGAR API
│   │   ├── parser.py # SECFilingParser for 10-K, 10-Q, 8-K
│   │   ├── chunker.py # FilingChunker for text splitting
│   │   ├── supabase.py # Database client singleton
│   │   └── store.py  # SupabaseStore for all DB operations
│   ├── embeddings/   # Local embedding generation
│   │   └── embedder.py # LocalEmbedder using BGE model
│   ├── retrieval/    # Vector search and hybrid retrieval
│   └── safety/       # Safety checker logic
├── tests/            # Unit and integration tests
├── scripts/          # Utility scripts
│   ├── populate_data.py # Data population pipeline
│   ├── schema.sql    # Supabase database schema
│   └── verify_db_setup.py # Database verification
├── Dockerfile        # Container definition
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Hybrid Retrieval System

The system uses a hybrid approach combining semantic vector search with BM25 keyword search for optimal retrieval performance.

### Architecture

**Components:**
- `HybridRetriever`: Main retrieval orchestrator
- `BM25Searcher`: Keyword-based search using BM25 algorithm
- `QueryPreprocessor`: Query normalization and term expansion
- `RetrievalConfig`: Configurable weights and parameters

**Default Configuration:**
- Semantic weight: 70%
- Keyword weight: 30%
- Max results: 10
- Days back: 365

### Usage

```python
from src.retrieval.hybrid import HybridRetriever, RetrievalConfig

# Initialize with default config
retriever = HybridRetriever()

# Or with custom config
config = RetrievalConfig(
    semantic_weight=0.6,
    keyword_weight=0.4,
    max_results=20
)
retriever = HybridRetriever(config=config)

# Basic retrieval
results = retriever.retrieve(
    query="litigation risks",
    ticker="AAPL",
    filing_types=["10-K"],
    section_names=["1A"]
)

# Multi-faceted safety check retrieval
results = retriever.retrieve_for_safety_check(
    ticker="AAPL",
    query_aspects=[
        "litigation and legal risks",
        "regulatory compliance issues",
        "financial stability concerns"
    ]
)

# Convenience methods
risk_results = retriever.retrieve_risk_factors(
    query="patent litigation",
    ticker="AAPL"
)

mda_results = retriever.retrieve_mda(
    query="revenue trends",
    ticker="AAPL",
    filing_type="10-K"
)
```

### Features

**Query Preprocessing:**
- Whitespace normalization
- Financial term expansion (e.g., "litigation" → "lawsuit, legal proceedings")
- Optional stopword removal
- Tokenization for BM25

**Score Combination:**
- Normalized semantic similarity scores (0-1)
- Normalized BM25 keyword scores (0-1)
- Weighted combination based on configuration
- Configurable minimum score threshold

**Filtering:**
- By ticker symbol
- By filing type (10-K, 10-Q, 8-K)
- By section name (1A, 7, 2, etc.)
- By date range (days back from present)

**Specialized Retrieval:**
- `retrieve_for_safety_check()`: Multi-aspect retrieval with deduplication
- `retrieve_risk_factors()`: Targets Item 1A in 10-K filings
- `retrieve_mda()`: Targets MD&A sections (Item 7 for 10-K, Item 2 for 10-Q)
- `retrieve_by_section()`: Generic section-specific retrieval

### Verification

Run the verification script to test the implementation:

```bash
python scripts/verify_hybrid_retrieval.py
```

## Earnings Proximity Checker

The system monitors upcoming earnings announcements and provides warnings when earnings are within the configured threshold (default: 3 days).

### Architecture

**Components:**
- `EarningsChecker`: Main checker for earnings proximity detection
- `EarningsProximity`: Result dataclass with warning information
- Integration with `SupabaseStore` earnings calendar

**Default Configuration:**
- Warning threshold: 3 days before earnings
- Blackout period: 3 days before and after earnings

### Usage

```python
from src.safety.earnings import EarningsChecker

# Initialize checker
checker = EarningsChecker(threshold_days=3)

# Check single ticker
result = checker.check_earnings_proximity("AAPL")

if result.is_within_threshold:
    print(result.warning_message)
    # Output: "WARNING: Earnings for AAPL in 2 day(s) on 2024-01-17 (AMC)"

# Check multiple tickers
results = checker.check_multiple_tickers(["AAPL", "MSFT", "GOOGL"])
for ticker, result in results.items():
    if result.is_within_threshold:
        print(f"{ticker}: {result.warning_message}")

# Check if in blackout period (before or after earnings)
is_blackout = checker.is_earnings_blackout("AAPL")
if is_blackout:
    print("Ticker is in earnings blackout period")

# Get tickers with upcoming earnings
upcoming_tickers = checker.get_tickers_with_upcoming_earnings(
    tickers=["AAPL", "MSFT", "GOOGL"],
    days_ahead=14
)
```

### Populating Earnings Data

```python
from datetime import date
from src.safety.earnings import EarningsChecker

checker = EarningsChecker()

# Add single earnings entry
checker.populate_earnings_data(
    ticker="AAPL",
    earnings_date=date(2024, 1, 25),
    time_of_day="AMC",  # After Market Close
    fiscal_quarter="Q1 2024",
    source="manual"
)

# Bulk populate earnings
earnings_data = [
    {
        "ticker": "AAPL",
        "earnings_date": "2024-01-25",
        "time_of_day": "AMC",
        "fiscal_quarter": "Q1 2024"
    },
    {
        "ticker": "MSFT",
        "earnings_date": "2024-01-30",
        "time_of_day": "BMO",  # Before Market Open
        "fiscal_quarter": "Q2 2024"
    }
]

entry_ids = checker.bulk_populate_earnings(earnings_data)
```

### Features

**Proximity Detection:**
- Calculates days until next earnings announcement
- Configurable warning threshold (default: 3 days)
- Handles missing earnings data gracefully
- Returns detailed `EarningsProximity` result

**Blackout Period:**
- Detects if ticker is within threshold before earnings
- Detects if ticker is within threshold after earnings
- Useful for avoiding trades during volatile periods

**Multi-Ticker Support:**
- Check multiple tickers in one call
- Get list of tickers with upcoming earnings
- Filter by date range

**Data Management:**
- Single entry population
- Bulk import support
- Automatic date conversion from ISO strings
- Upsert logic (updates existing entries)

### EarningsProximity Result

```python
@dataclass
class EarningsProximity:
    ticker: str
    has_upcoming_earnings: bool
    days_until_earnings: Optional[int]
    earnings_date: Optional[date]
    time_of_day: Optional[str]  # "BMO", "AMC", "UNKNOWN"
    is_within_threshold: bool
    threshold_days: int
    
    @property
    def warning_message(self) -> Optional[str]:
        # Returns formatted warning message if applicable
```

## Safety Checker Core Logic

The Safety Checker makes intelligent PROCEED/REDUCE/VETO decisions based on risk analysis, earnings proximity, and allocation size.

### Architecture

**Components:**
- `SafetyChecker`: Main decision engine
- `SafetyDecision`: Enum (PROCEED, REDUCE, VETO)
- `SafetyThresholds`: Configurable decision thresholds
- `SafetyCheckResult`: Structured result with reasoning

**Decision Logic:**
1. **VETO**: Risk score ≥8 OR critical event detected
2. **REDUCE**: Risk score ≥6 OR (earnings within 3 days AND high allocation >15%)
3. **PROCEED**: All checks pass

### Default Thresholds

```python
SafetyThresholds(
    veto_risk_score=8.0,           # VETO threshold
    reduce_risk_score=6.0,          # REDUCE threshold
    critical_event_severity=9.0,    # Critical event threshold
    earnings_warning_days=3,        # Earnings proximity warning
    high_allocation_pct=15.0        # High allocation threshold
)
```

### Usage

```python
from src.safety.checker import SafetyChecker, SafetyDecision

# Initialize checker
checker = SafetyChecker()

# Perform safety check
result = checker.check_safety(
    ticker="AAPL",
    allocation_pct=12.0,
    use_cache=True
)

# Handle decision
if result.decision == SafetyDecision.VETO:
    print(f"❌ VETO: {result.reasoning}")
    print(f"Risk Score: {result.risk_score}")
    if result.critical_events:
        print(f"Critical Events: {result.critical_events}")

elif result.decision == SafetyDecision.REDUCE:
    print(f"⚠️  REDUCE: {result.reasoning}")
    print(f"Risk Score: {result.risk_score}")
    if result.earnings_warning:
        print(f"Earnings Warning: {result.earnings_warning}")

else:  # PROCEED
    print(f"✓ PROCEED: {result.reasoning}")
    print(f"Risk Score: {result.risk_score}")
```

### Risk Scoring

The system analyzes SEC filings to calculate risk scores (0-10):

**Risk Keywords (with weights):**
- Bankruptcy, going concern: 3.0
- Fraud, investigation: 2.5-3.0
- Litigation, lawsuit: 2.0
- Regulatory, violation: 1.5-2.0
- Material weakness, restatement: 2.0-2.5

**Section Weighting:**
- Item 1A (Risk Factors): 1.5x weight
- Other sections: 1.0x weight

**Risk Score Ranges:**
- 0-3: Low risk → PROCEED
- 4-5.9: Medium risk → PROCEED (monitor)
- 6-7.9: Elevated risk → REDUCE
- 8-10: High risk → VETO

### Critical Events

Critical events trigger immediate VETO regardless of risk score:
- Bankruptcy filing
- Going concern doubts
- Material weakness in controls
- Fraud allegations
- Criminal investigations
- Delisting notices
- Debt defaults

### Caching

**Cache Key Generation:**
- Allocations bucketed to nearest 5% (e.g., 8%, 10%, 12% → same key)
- Reduces cache misses for similar allocations

**Dynamic TTL:**
- High risk (≥8): 1 hour
- Medium risk (6-7.9): 4 hours
- Low risk (<6): 24 hours

### Custom Thresholds

```python
from src.safety.checker import SafetyChecker, SafetyThresholds

# Create custom thresholds
thresholds = SafetyThresholds(
    veto_risk_score=9.0,      # More lenient VETO
    reduce_risk_score=7.0,     # More lenient REDUCE
    earnings_warning_days=5,   # Wider earnings window
    high_allocation_pct=20.0   # Higher allocation threshold
)

checker = SafetyChecker(thresholds=thresholds)
```

### Integration Example

```python
from src.safety.checker import SafetyChecker

checker = SafetyChecker()

# Check multiple tickers
portfolio = [
    ("AAPL", 15.0),
    ("MSFT", 12.0),
    ("GOOGL", 18.0),
]

for ticker, allocation in portfolio:
    result = checker.check_safety(ticker, allocation)
    
    print(f"\n{ticker} ({allocation}% allocation):")
    print(f"  Decision: {result.decision.value}")
    print(f"  Risk Score: {result.risk_score}")
    print(f"  Reasoning: {result.reasoning}")
    
    if result.earnings_warning:
        print(f"  ⚠️  {result.earnings_warning}")
```

### SafetyCheckResult Structure

```python
@dataclass
class SafetyCheckResult:
    decision: SafetyDecision          # PROCEED/REDUCE/VETO
    ticker: str                       # Stock ticker
    risk_score: float                 # Risk score (0-10)
    reasoning: str                    # Decision explanation
    earnings_warning: Optional[str]   # Earnings proximity warning
    critical_events: Optional[List]   # Critical events found
    allocation_warning: Optional[str] # High allocation warning
    cache_hit: bool                   # Whether result was cached
    retrieved_chunks: Optional[List]  # SEC filing chunks analyzed
```

## REST API

The system provides a FastAPI REST API for safety checks and filing management.

### Starting the API Server

```bash
# Development
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### API Endpoints

#### POST /safety-check

Perform comprehensive safety check for stock allocation.

**Request:**
```json
{
  "ticker": "AAPL",
  "allocation_pct": 12.5,
  "use_cache": true
}
```

**Response:**
```json
{
  "decision": "REDUCE",
  "ticker": "AAPL",
  "risk_score": 6.5,
  "reasoning": "Elevated risk score (6.5); Earnings in 2 days with high allocation (18.0%)",
  "earnings_warning": "WARNING: Earnings for AAPL in 2 day(s) on 2024-01-17 (AMC)",
  "critical_events": null,
  "allocation_warning": "High allocation: 18.0%",
  "cache_hit": false,
  "retrieved_chunks": [...]
}
```

**Status Codes:**
- `200 OK`: Success
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error

#### POST /index-filing

Start background task to index a new SEC filing.

**Request:**
```json
{
  "ticker": "AAPL",
  "cik": "0000320193",
  "filing_type": "10-K",
  "filing_date": "2024-01-15",
  "filing_url": "https://www.sec.gov/..."
}
```

**Response:**
```json
{
  "status": "processing",
  "message": "Filing indexing started in background for AAPL",
  "task_id": "AAPL_10-K_1234567890.123",
  "ticker": "AAPL",
  "filing_type": "10-K"
}
```

**Status Codes:**
- `202 Accepted`: Task started
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error

#### GET /health

Health check with dependency status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "dependencies": {
    "database": "connected",
    "embedder": "loaded",
    "retriever": "ready"
  },
  "version": "1.0.0"
}
```

**Status Codes:**
- `200 OK`: Success

#### GET /cache-stats

Get cache performance metrics.

**Response:**
```json
{
  "total_entries": 150,
  "hit_rate": 0.72,
  "total_hits": 1080,
  "total_misses": 420,
  "avg_ttl_hours": 12.5,
  "cache_size_mb": 2.3
}
```

**Status Codes:**
- `200 OK`: Success

#### DELETE /cache/{ticker}

Invalidate cache for specific ticker.

**Response:**
```json
{
  "status": "success",
  "message": "Cache invalidated for ticker AAPL",
  "ticker": "AAPL",
  "entries_deleted": 5
}
```

**Status Codes:**
- `200 OK`: Success
- `500 Internal Server Error`: Server error

### API Documentation

Interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### CORS Configuration

The API allows cross-origin requests from any origin with:
- All HTTP methods
- All headers
- Credentials support

### Request Validation

**SafetyCheckRequest:**
- `ticker`: 1-10 characters, converted to uppercase
- `allocation_pct`: 0-100 (inclusive)
- `use_cache`: boolean (default: true)

**IndexFilingRequest:**
- `ticker`: 1-10 characters, converted to uppercase
- `cik`: Exactly 10 characters
- `filing_type`: Must be "10-K", "10-Q", or "8-K"
- `filing_date`: Valid ISO date
- `filing_url`: Valid URL string

### Example Usage

**Python:**
```python
import requests

# Safety check
response = requests.post(
    "http://localhost:8000/safety-check",
    json={
        "ticker": "AAPL",
        "allocation_pct": 15.0,
        "use_cache": True
    }
)

result = response.json()
print(f"Decision: {result['decision']}")
print(f"Risk Score: {result['risk_score']}")
print(f"Reasoning: {result['reasoning']}")
```

**cURL:**
```bash
# Safety check
curl -X POST "http://localhost:8000/safety-check" \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "allocation_pct": 15.0,
    "use_cache": true
  }'

# Health check
curl "http://localhost:8000/health"

# Cache stats
curl "http://localhost:8000/cache-stats"

# Invalidate cache
curl -X DELETE "http://localhost:8000/cache/AAPL"
```

## Running Tests

The project includes comprehensive unit, integration, and end-to-end tests with 92% code coverage.

### Quick Test Commands

```bash
# Run all unit and integration tests with coverage
podman exec rag-safety-api pytest tests/ -v --cov=src --cov-report=term-missing

# Run end-to-end tests (local)
./test_e2e.sh http://localhost:8000

# Run end-to-end tests (production)
./test_e2e.sh https://rag-safety-checker.onrender.com

# Run performance tests
./test_performance.sh http://localhost:8000 10

# Run load tests (100 requests, 10 concurrent)
python3 scripts/load_test.py --url http://localhost:8000 --requests 100 --concurrency 10

# Quick load test (20 requests, 5 concurrent)
python3 scripts/load_test.py --url http://localhost:8000 --requests 20 --concurrency 5
```

### Test Categories

```bash
# Unit Tests - Core Logic
podman exec rag-safety-api pytest tests/test_safety_checker.py -v  # Safety decision logic
podman exec rag-safety-api pytest tests/test_earnings_checker.py -v  # Earnings proximity
podman exec rag-safety-api pytest tests/test_hybrid_retrieval.py -v  # Hybrid retrieval

# Integration Tests - End-to-End
podman exec rag-safety-api pytest tests/test_integration.py -v  # Full workflow tests
podman exec rag-safety-api pytest tests/test_api.py -v  # API endpoints

# Data Layer Tests
podman exec rag-safety-api pytest tests/test_store.py -v  # Database operations
podman exec rag-safety-api pytest tests/test_parser.py -v  # SEC filing parsing
podman exec rag-safety-api pytest tests/test_chunker.py -v  # Text chunking
podman exec rag-safety-api pytest tests/test_embedder.py -v  # Embedding generation
```

### Coverage Report

Current test coverage: **91% overall**

| Module | Coverage |
|--------|----------|
| `src/safety/checker.py` | 88% |
| `src/safety/earnings.py` | 99% |
| `src/api/models.py` | 100% |
| `src/data/store.py` | 98% |
| `src/data/parser.py` | 99% |
| `src/retrieval/hybrid.py` | 96% |

Generate HTML coverage report:
```bash
podman exec rag-safety-api pytest tests/ --cov=src --cov-report=html
# Report available at htmlcov/index.html
```

### Test Configuration

Tests are configured in `pytest.ini`:
- Async mode: auto (for FastAPI async tests)
- Coverage: enabled by default
- Verbose output with short tracebacks

## Deployment

### Render.com (Free Tier)

This project is configured for one-click deployment to Render.com using the included `render.yaml` Blueprint.

#### Quick Deploy

1. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "feat(deployment): prepare for Render deployment"
   git push origin main
   ```

2. **Deploy on Render**:
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click **"New +"** → **"Blueprint"**
   - Connect your GitHub repository
   - Select this repository
   - Click **"Apply"**

3. **Add Environment Variables**:
   Navigate to your service and add these secrets:
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_KEY`: Your Supabase anon/public key
   - `GROQ_API_KEY`: Your Groq API key from [console.groq.com](https://console.groq.com/keys)

4. **Verify Deployment**:
   ```bash
   # Test with your Render URL
   ./test_deployment.sh https://rag-safety-checker.onrender.com
   ```

#### Configuration

The `render.yaml` Blueprint includes:
- **Service**: Docker-based web service
- **Region**: Oregon (free tier)
- **Health Check**: `/health` endpoint
- **Auto-deploy**: Enabled on git push
- **Environment**: Pre-configured with Groq LLM (free)

#### Free Tier Notes

- **Cold Starts**: Service sleeps after 15 minutes of inactivity
- **First Request**: May take 30-60 seconds after sleep
- **Build Time**: ~5-10 minutes for initial deployment
- **Memory**: 512 MB RAM (sufficient for this application)

For detailed deployment instructions, troubleshooting, and production tips, see [`DEPLOYMENT.md`](./DEPLOYMENT.md).

## Performance & Monitoring

### Performance Targets

All targets met in production:

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Cached responses | <2s | 0.9s | ✅ |
| Uncached responses | <5s | 3.5s | ✅ |
| Cache hit rate | >70% | Monitoring | ⏳ |
| Uptime | >99% | 99.9% | ✅ |
| Memory usage | <512MB | 310MB | ✅ |

### Performance Testing

Run automated performance tests:

```bash
# Local testing
./test_performance.sh http://localhost:8000 10

# Production testing
./test_performance.sh https://rag-safety-checker.onrender.com 10
```

### Monitoring Resources

- **Performance Guide:** [`MONITORING.md`](./MONITORING.md) - Comprehensive monitoring setup
- **Database Queries:** [`monitoring_queries.sql`](./monitoring_queries.sql) - 28 monitoring queries
- **Baselines:** [`PERFORMANCE_BASELINES.md`](./PERFORMANCE_BASELINES.md) - Detailed metrics
- **Render Dashboard:** https://dashboard.render.com - Real-time metrics
- **API Docs:** https://rag-safety-checker.onrender.com/docs

### Key Monitoring Endpoints

```bash
# Health check
curl https://rag-safety-checker.onrender.com/health

# Cache statistics
curl https://rag-safety-checker.onrender.com/cache-stats
```

### Cost Monitoring

**Current Costs:** $0/month (all free tiers)
- Groq LLM: Free tier (14,400 requests/day)
- Supabase: Free tier (500 MB database)
- Render: Free tier (512 MB RAM)

## License

MIT
