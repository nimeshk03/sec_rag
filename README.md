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

## Project Structure

```
risk_analysis_RAG/
├── src/
│   ├── api/          # FastAPI application
│   ├── data/         # SEC filing download and parsing
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
