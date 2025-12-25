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

## Running Tests

```bash
docker-compose exec api pytest tests/ -v
```

## Deployment

### Render.com (Free Tier)

1. Push code to GitHub
2. Create new Web Service on Render
3. Connect repository
4. Render will use `render.yaml` configuration
5. Add environment variables in Render dashboard
6. Deploy

## Performance Targets

- API Latency (cached): <2 seconds
- API Latency (uncached): <5 seconds
- Cache Hit Rate: >70%
- Uptime: >99%

## License

MIT
