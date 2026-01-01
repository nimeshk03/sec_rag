-- Monitoring Queries for RAG Safety Checker
-- Run these queries in Supabase SQL Editor to monitor system health and performance

-- ============================================
-- System Health Queries
-- ============================================

-- 1. Check total filings indexed
SELECT 
    COUNT(*) as total_filings,
    COUNT(DISTINCT ticker) as unique_tickers,
    COUNT(DISTINCT filing_type) as filing_types
FROM filings;

-- 2. Filings by ticker
SELECT 
    ticker,
    COUNT(*) as filing_count,
    MAX(filing_date) as latest_filing
FROM filings
GROUP BY ticker
ORDER BY filing_count DESC;

-- 3. Filings by type
SELECT 
    filing_type,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
FROM filings
GROUP BY filing_type
ORDER BY count DESC;

-- ============================================
-- Cache Performance Queries
-- ============================================

-- 4. Current cache entries
SELECT 
    COUNT(*) as total_entries,
    COUNT(DISTINCT SUBSTRING(cache_key FROM 'safety_check:([^:]+):')) as unique_tickers,
    ROUND(AVG(EXTRACT(EPOCH FROM (expires_at - created_at)) / 3600), 2) as avg_ttl_hours
FROM cache_entries
WHERE expires_at > NOW();

-- 5. Cache entries by ticker
SELECT 
    SUBSTRING(cache_key FROM 'safety_check:([^:]+):') as ticker,
    COUNT(*) as cache_entries,
    MIN(created_at) as first_cached,
    MAX(created_at) as last_cached
FROM cache_entries
WHERE expires_at > NOW()
GROUP BY ticker
ORDER BY cache_entries DESC;

-- 6. Expired cache entries (cleanup needed)
SELECT 
    COUNT(*) as expired_entries,
    ROUND(SUM(LENGTH(response_data::text)) / 1024.0 / 1024.0, 2) as size_mb
FROM cache_entries
WHERE expires_at <= NOW();

-- ============================================
-- Safety Check Performance Queries
-- ============================================

-- 7. Safety check statistics (last 7 days)
SELECT 
    COUNT(*) as total_checks,
    COUNT(DISTINCT ticker) as unique_tickers,
    ROUND(AVG(risk_score), 2) as avg_risk_score,
    SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) as cache_hits,
    SUM(CASE WHEN NOT cache_hit THEN 1 ELSE 0 END) as cache_misses,
    ROUND(100.0 * SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) / COUNT(*), 2) as cache_hit_rate_pct
FROM safety_logs
WHERE created_at > NOW() - INTERVAL '7 days';

-- 8. Safety decisions breakdown
SELECT 
    decision,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage,
    ROUND(AVG(risk_score), 2) as avg_risk_score
FROM safety_logs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY decision
ORDER BY count DESC;

-- 9. Safety checks by ticker (last 7 days)
SELECT 
    ticker,
    COUNT(*) as check_count,
    ROUND(AVG(risk_score), 2) as avg_risk_score,
    MODE() WITHIN GROUP (ORDER BY decision) as most_common_decision,
    MAX(created_at) as last_check
FROM safety_logs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY ticker
ORDER BY check_count DESC
LIMIT 10;

-- 10. Daily safety check volume
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_checks,
    COUNT(DISTINCT ticker) as unique_tickers,
    SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) as cache_hits,
    ROUND(100.0 * SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) / COUNT(*), 2) as hit_rate_pct
FROM safety_logs
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- ============================================
-- Earnings Data Queries
-- ============================================

-- 11. Upcoming earnings (next 30 days)
SELECT 
    ticker,
    earnings_date,
    earnings_date - CURRENT_DATE as days_until,
    updated_at
FROM earnings_dates
WHERE earnings_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
ORDER BY earnings_date;

-- 12. Earnings data freshness
SELECT 
    COUNT(*) as total_entries,
    COUNT(CASE WHEN updated_at > NOW() - INTERVAL '7 days' THEN 1 END) as updated_last_week,
    COUNT(CASE WHEN updated_at > NOW() - INTERVAL '30 days' THEN 1 END) as updated_last_month,
    MIN(updated_at) as oldest_update,
    MAX(updated_at) as newest_update
FROM earnings_dates;

-- ============================================
-- Chunk and Embedding Queries
-- ============================================

-- 13. Chunks by filing
SELECT 
    f.ticker,
    f.filing_type,
    COUNT(c.id) as chunk_count,
    ROUND(AVG(LENGTH(c.text)), 0) as avg_chunk_length,
    COUNT(CASE WHEN c.embedding IS NOT NULL THEN 1 END) as chunks_with_embeddings
FROM filings f
LEFT JOIN chunks c ON f.id = c.filing_id
GROUP BY f.ticker, f.filing_type
ORDER BY chunk_count DESC
LIMIT 10;

-- 14. Chunks by section
SELECT 
    section,
    COUNT(*) as chunk_count,
    ROUND(AVG(LENGTH(text)), 0) as avg_length,
    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as with_embeddings
FROM chunks
GROUP BY section
ORDER BY chunk_count DESC;

-- 15. Embedding coverage
SELECT 
    COUNT(*) as total_chunks,
    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as chunks_with_embeddings,
    ROUND(100.0 * COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) / COUNT(*), 2) as coverage_pct
FROM chunks;

-- ============================================
-- Performance and Optimization Queries
-- ============================================

-- 16. Slow safety checks (>5 seconds response time)
SELECT 
    ticker,
    decision,
    risk_score,
    cache_hit,
    created_at,
    EXTRACT(EPOCH FROM (updated_at - created_at)) as response_time_seconds
FROM safety_logs
WHERE updated_at - created_at > INTERVAL '5 seconds'
ORDER BY response_time_seconds DESC
LIMIT 20;

-- 17. Database size by table
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY size_bytes DESC;

-- 18. Most accessed tickers (cache + direct)
SELECT 
    ticker,
    COUNT(*) as total_requests,
    SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) as cache_hits,
    SUM(CASE WHEN NOT cache_hit THEN 1 ELSE 0 END) as cache_misses,
    ROUND(100.0 * SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) / COUNT(*), 2) as hit_rate_pct
FROM safety_logs
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY ticker
ORDER BY total_requests DESC
LIMIT 10;

-- ============================================
-- Data Quality Queries
-- ============================================

-- 19. Filings without chunks
SELECT 
    ticker,
    filing_type,
    filing_date,
    created_at
FROM filings f
WHERE NOT EXISTS (
    SELECT 1 FROM chunks c WHERE c.filing_id = f.id
)
ORDER BY created_at DESC;

-- 20. Chunks without embeddings
SELECT 
    f.ticker,
    f.filing_type,
    c.section,
    COUNT(*) as chunks_without_embeddings
FROM chunks c
JOIN filings f ON c.filing_id = f.id
WHERE c.embedding IS NULL
GROUP BY f.ticker, f.filing_type, c.section
ORDER BY chunks_without_embeddings DESC
LIMIT 10;

-- ============================================
-- Maintenance Queries
-- ============================================

-- 21. Clean up expired cache entries
DELETE FROM cache_entries
WHERE expires_at < NOW() - INTERVAL '1 day';

-- 22. Archive old safety logs (older than 90 days)
-- Note: Create archive table first if needed
-- CREATE TABLE safety_logs_archive AS SELECT * FROM safety_logs WHERE 1=0;

-- INSERT INTO safety_logs_archive
-- SELECT * FROM safety_logs
-- WHERE created_at < NOW() - INTERVAL '90 days';

-- DELETE FROM safety_logs
-- WHERE created_at < NOW() - INTERVAL '90 days';

-- 23. Vacuum and analyze tables (run periodically)
-- VACUUM ANALYZE filings;
-- VACUUM ANALYZE chunks;
-- VACUUM ANALYZE cache_entries;
-- VACUUM ANALYZE safety_logs;

-- ============================================
-- Alerting Queries (Run these to detect issues)
-- ============================================

-- 24. Check for high error rate (>5% in last hour)
SELECT 
    COUNT(*) as total_checks,
    COUNT(CASE WHEN decision = 'VETO' AND reasoning LIKE '%error%' THEN 1 END) as error_checks,
    ROUND(100.0 * COUNT(CASE WHEN decision = 'VETO' AND reasoning LIKE '%error%' THEN 1 END) / COUNT(*), 2) as error_rate_pct
FROM safety_logs
WHERE created_at > NOW() - INTERVAL '1 hour'
HAVING COUNT(CASE WHEN decision = 'VETO' AND reasoning LIKE '%error%' THEN 1 END) > COUNT(*) * 0.05;

-- 25. Check for stale earnings data (not updated in 30 days)
SELECT 
    ticker,
    earnings_date,
    updated_at,
    CURRENT_DATE - DATE(updated_at) as days_since_update
FROM earnings_dates
WHERE updated_at < NOW() - INTERVAL '30 days'
ORDER BY updated_at;

-- 26. Check for cache hit rate drop (below 50% in last 24 hours)
SELECT 
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as total_checks,
    SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) as cache_hits,
    ROUND(100.0 * SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) / COUNT(*), 2) as hit_rate_pct
FROM safety_logs
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', created_at)
HAVING SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) < COUNT(*) * 0.5
ORDER BY hour DESC;

-- ============================================
-- Usage Statistics for Reporting
-- ============================================

-- 27. Monthly usage summary
SELECT 
    DATE_TRUNC('month', created_at) as month,
    COUNT(*) as total_checks,
    COUNT(DISTINCT ticker) as unique_tickers,
    ROUND(AVG(risk_score), 2) as avg_risk_score,
    COUNT(CASE WHEN decision = 'PROCEED' THEN 1 END) as proceed_count,
    COUNT(CASE WHEN decision = 'REDUCE' THEN 1 END) as reduce_count,
    COUNT(CASE WHEN decision = 'VETO' THEN 1 END) as veto_count
FROM safety_logs
GROUP BY DATE_TRUNC('month', created_at)
ORDER BY month DESC;

-- 28. Peak usage hours
SELECT 
    EXTRACT(HOUR FROM created_at) as hour,
    COUNT(*) as request_count,
    ROUND(AVG(risk_score), 2) as avg_risk_score
FROM safety_logs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY EXTRACT(HOUR FROM created_at)
ORDER BY request_count DESC;

-- ============================================
-- End of Monitoring Queries
-- ============================================

-- Notes:
-- - Run queries 1-18 regularly for monitoring
-- - Run queries 19-20 to identify data quality issues
-- - Run queries 21-23 for maintenance (with caution)
-- - Run queries 24-26 for alerting/anomaly detection
-- - Run queries 27-28 for usage reporting
