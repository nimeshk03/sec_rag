-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Filings metadata table
CREATE TABLE IF NOT EXISTS filings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker TEXT NOT NULL,
    filing_type TEXT NOT NULL CHECK (filing_type IN ('10-K', '10-Q', '8-K')),
    filing_date DATE NOT NULL,
    accession_number TEXT UNIQUE NOT NULL,
    fiscal_period TEXT,
    fiscal_year INTEGER,
    source_url TEXT,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT unique_filing UNIQUE (ticker, filing_type, filing_date)
);

CREATE INDEX IF NOT EXISTS idx_filings_ticker ON filings(ticker);
CREATE INDEX IF NOT EXISTS idx_filings_date ON filings(filing_date DESC);
CREATE INDEX IF NOT EXISTS idx_filings_type ON filings(filing_type);

-- Text chunks with embeddings
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filing_id UUID REFERENCES filings(id) ON DELETE CASCADE,
    section_name TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),  -- bge-small-en-v1.5 dimensions
    chunk_index INTEGER NOT NULL,
    total_chunks INTEGER,
    word_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Vector similarity search index
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_chunks_filing ON chunks(filing_id);
CREATE INDEX IF NOT EXISTS idx_chunks_section ON chunks(section_name);

-- Response cache table
CREATE TABLE IF NOT EXISTS cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key TEXT UNIQUE NOT NULL,
    response JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    hit_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_cache_key ON cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_cache_expiry ON cache(expires_at);

-- Safety check audit log
CREATE TABLE IF NOT EXISTS safety_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ticker TEXT NOT NULL,
    proposed_allocation FLOAT,
    current_allocation FLOAT,
    decision TEXT CHECK (decision IN ('PROCEED', 'REDUCE', 'VETO')),
    reasoning TEXT,
    risk_score INTEGER CHECK (risk_score BETWEEN 1 AND 10),
    risks JSONB,
    chunks_retrieved INTEGER,
    latency_ms INTEGER,
    cached BOOLEAN DEFAULT FALSE,
    
    -- For analysis
    rl_allocation FLOAT,
    final_allocation FLOAT
);

CREATE INDEX IF NOT EXISTS idx_safety_logs_ticker ON safety_logs(ticker);
CREATE INDEX IF NOT EXISTS idx_safety_logs_time ON safety_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_safety_logs_decision ON safety_logs(decision);

-- Earnings calendar (for proximity check)
CREATE TABLE IF NOT EXISTS earnings_calendar (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker TEXT NOT NULL,
    earnings_date DATE NOT NULL,
    time_of_day TEXT CHECK (time_of_day IN ('BMO', 'AMC', 'UNKNOWN')),
    fiscal_quarter TEXT,
    source TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_earnings UNIQUE (ticker, earnings_date)
);

CREATE INDEX IF NOT EXISTS idx_earnings_ticker ON earnings_calendar(ticker);
CREATE INDEX IF NOT EXISTS idx_earnings_date ON earnings_calendar(earnings_date);

-- Function to clean expired cache
CREATE OR REPLACE FUNCTION clean_expired_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM cache WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Vector search function
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(384),
    match_ticker TEXT,
    match_count INT DEFAULT 10,
    days_back INT DEFAULT 365,
    filing_types TEXT[] DEFAULT NULL,
    section_names TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    section_name TEXT,
    filing_type TEXT,
    filing_date DATE,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.id,
        c.content,
        c.section_name,
        f.filing_type,
        f.filing_date,
        1 - (c.embedding <=> query_embedding) AS similarity
    FROM chunks c
    JOIN filings f ON c.filing_id = f.id
    WHERE 
        f.ticker = match_ticker
        AND f.filing_date >= CURRENT_DATE - make_interval(days => days_back)
        AND (filing_types IS NULL OR f.filing_type = ANY(filing_types))
        AND (section_names IS NULL OR c.section_name = ANY(section_names))
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Function to get cache statistics
CREATE OR REPLACE FUNCTION get_cache_stats()
RETURNS TABLE (
    total_entries BIGINT,
    expired_entries BIGINT,
    total_hits BIGINT,
    avg_hits NUMERIC,
    oldest_entry TIMESTAMP WITH TIME ZONE,
    newest_entry TIMESTAMP WITH TIME ZONE
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*) AS total_entries,
        COUNT(*) FILTER (WHERE expires_at < NOW()) AS expired_entries,
        SUM(hit_count) AS total_hits,
        AVG(hit_count) AS avg_hits,
        MIN(created_at) AS oldest_entry,
        MAX(created_at) AS newest_entry
    FROM cache;
END;
$$;
