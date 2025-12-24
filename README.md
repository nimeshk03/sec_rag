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

## Project Structure

```
risk_analysis_RAG/
├── src/
│   ├── api/          # FastAPI application
│   ├── data/         # SEC filing download and parsing
│   │   ├── parser.py # SECFilingParser for 10-K, 10-Q, 8-K
│   │   ├── chunker.py # FilingChunker for text splitting
│   │   └── supabase.py # Database client
│   ├── embeddings/   # Local embedding generation
│   ├── retrieval/    # Vector search and hybrid retrieval
│   └── safety/       # Safety checker logic
├── tests/            # Unit and integration tests
├── scripts/          # Utility scripts
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
