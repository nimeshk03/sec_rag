#!/bin/bash

# Performance Testing Script for RAG Safety Checker API
# Tests latency, cache behavior, and generates performance baselines

API_URL="${1:-http://localhost:8000}"
NUM_REQUESTS="${2:-10}"

echo "=========================================="
echo "Performance Testing: RAG Safety Checker"
echo "=========================================="
echo "API URL: $API_URL"
echo "Number of requests: $NUM_REQUESTS"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to measure response time
measure_time() {
    local url=$1
    local method=${2:-GET}
    local data=$3
    
    if [ "$method" = "POST" ]; then
        curl -s -w "%{time_total}" -o /dev/null -X POST "$url" \
            -H "Content-Type: application/json" \
            -d "$data"
    else
        curl -s -w "%{time_total}" -o /dev/null "$url"
    fi
}

# Function to calculate average
calculate_avg() {
    local sum=0
    local count=0
    for val in "$@"; do
        sum=$(echo "$sum + $val" | bc)
        count=$((count + 1))
    done
    echo "scale=3; $sum / $count" | bc
}

# Function to find min/max
find_min() {
    local min=$1
    shift
    for val in "$@"; do
        if (( $(echo "$val < $min" | bc -l) )); then
            min=$val
        fi
    done
    echo "$min"
}

find_max() {
    local max=$1
    shift
    for val in "$@"; do
        if (( $(echo "$val > $max" | bc -l) )); then
            max=$val
        fi
    done
    echo "$max"
}

echo ""
echo "1. Testing Health Endpoint Performance"
echo "--------------------------------------"
health_times=()
for i in $(seq 1 $NUM_REQUESTS); do
    time=$(measure_time "$API_URL/health")
    health_times+=($time)
    echo -n "."
done
echo ""
avg_health=$(calculate_avg "${health_times[@]}")
min_health=$(find_min "${health_times[@]}")
max_health=$(find_max "${health_times[@]}")
echo "Average: ${avg_health}s | Min: ${min_health}s | Max: ${max_health}s"

echo ""
echo "2. Testing Root Endpoint Performance"
echo "------------------------------------"
root_times=()
for i in $(seq 1 $NUM_REQUESTS); do
    time=$(measure_time "$API_URL/")
    root_times+=($time)
    echo -n "."
done
echo ""
avg_root=$(calculate_avg "${root_times[@]}")
min_root=$(find_min "${root_times[@]}")
max_root=$(find_max "${root_times[@]}")
echo "Average: ${avg_root}s | Min: ${min_root}s | Max: ${max_root}s"

echo ""
echo "3. Testing Safety Check - First Request (Uncached)"
echo "--------------------------------------------------"
# Clear cache first
curl -s -X DELETE "$API_URL/cache/AAPL" > /dev/null 2>&1
sleep 1

uncached_time=$(measure_time "$API_URL/safety-check" "POST" '{"ticker":"AAPL","allocation_pct":10.0}')
echo "First request (uncached): ${uncached_time}s"

echo ""
echo "4. Testing Safety Check - Subsequent Requests (Cached)"
echo "------------------------------------------------------"
cached_times=()
for i in $(seq 1 $NUM_REQUESTS); do
    time=$(measure_time "$API_URL/safety-check" "POST" '{"ticker":"AAPL","allocation_pct":10.0}')
    cached_times+=($time)
    echo -n "."
done
echo ""
avg_cached=$(calculate_avg "${cached_times[@]}")
min_cached=$(find_min "${cached_times[@]}")
max_cached=$(find_max "${cached_times[@]}")
echo "Average: ${avg_cached}s | Min: ${min_cached}s | Max: ${max_cached}s"

echo ""
echo "5. Testing Cache Stats Endpoint"
echo "-------------------------------"
cache_stats=$(curl -s "$API_URL/cache-stats")
echo "$cache_stats" | python3 -m json.tool 2>/dev/null || echo "$cache_stats"

echo ""
echo "6. Testing Different Tickers (Cache Miss Scenarios)"
echo "--------------------------------------------------"
tickers=("MSFT" "GOOGL" "TSLA")
ticker_times=()
for ticker in "${tickers[@]}"; do
    time=$(measure_time "$API_URL/safety-check" "POST" "{\"ticker\":\"$ticker\",\"allocation_pct\":15.0}")
    ticker_times+=($time)
    echo "$ticker: ${time}s"
done
avg_ticker=$(calculate_avg "${ticker_times[@]}")
echo "Average for new tickers: ${avg_ticker}s"

echo ""
echo "=========================================="
echo "Performance Summary"
echo "=========================================="
echo ""
echo "Endpoint Performance:"
echo "  Health Check:     ${avg_health}s (${min_health}s - ${max_health}s)"
echo "  Root:             ${avg_root}s (${min_root}s - ${max_root}s)"
echo "  Safety (uncached): ${uncached_time}s"
echo "  Safety (cached):   ${avg_cached}s (${min_cached}s - ${max_cached}s)"
echo "  New tickers:       ${avg_ticker}s"
echo ""

# Performance targets check
echo "Performance Targets:"
if (( $(echo "$avg_cached < 2.0" | bc -l) )); then
    echo -e "  ${GREEN}✓${NC} Cached responses: ${avg_cached}s < 2s target"
else
    echo -e "  ${RED}✗${NC} Cached responses: ${avg_cached}s >= 2s target"
fi

if (( $(echo "$uncached_time < 5.0" | bc -l) )); then
    echo -e "  ${GREEN}✓${NC} Uncached responses: ${uncached_time}s < 5s target"
else
    echo -e "  ${RED}✗${NC} Uncached responses: ${uncached_time}s >= 5s target"
fi

# Cache efficiency
echo ""
echo "Cache Efficiency:"
cache_hit_rate=$(echo "$cache_stats" | grep -o '"hit_rate":[0-9.]*' | cut -d: -f2)
if [ ! -z "$cache_hit_rate" ]; then
    cache_hit_pct=$(echo "$cache_hit_rate * 100" | bc)
    echo "  Hit Rate: ${cache_hit_pct}%"
    if (( $(echo "$cache_hit_rate > 0.7" | bc -l) )); then
        echo -e "  ${GREEN}✓${NC} Cache hit rate > 70% target"
    else
        echo -e "  ${YELLOW}!${NC} Cache hit rate < 70% (expected for new deployment)"
    fi
else
    echo "  Cache statistics not available"
fi

echo ""
echo "=========================================="
echo "Performance testing complete!"
echo "=========================================="
