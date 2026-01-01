#!/bin/bash

# Load Testing Script for RAG Safety Checker API
# Tests system stability under realistic load conditions

API_URL="${1:-http://localhost:8000}"
TOTAL_REQUESTS="${2:-100}"
CONCURRENT_USERS="${3:-10}"

echo "=========================================="
echo "Load Testing: RAG Safety Checker"
echo "=========================================="
echo "API URL: $API_URL"
echo "Total Requests: $TOTAL_REQUESTS"
echo "Concurrent Users: $CONCURRENT_USERS"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Results storage
RESULTS_FILE="/tmp/load_test_results_$$.txt"
ERRORS_FILE="/tmp/load_test_errors_$$.txt"
> "$RESULTS_FILE"
> "$ERRORS_FILE"

# Tickers to test
TICKERS=("MSFT" "AAPL" "GOOGL" "TSLA" "AMZN")
ALLOCATIONS=(5 10 15 20 25)

# Function to make a single request and record timing
make_request() {
    local request_num=$1
    local ticker=${TICKERS[$((RANDOM % ${#TICKERS[@]}))]}
    local allocation=${ALLOCATIONS[$((RANDOM % ${#ALLOCATIONS[@]}))]}
    
    local start_time=$(date +%s.%N)
    
    response=$(curl -s -w "\n%{http_code}\n%{time_total}" \
        -X POST "$API_URL/safety-check" \
        -H "Content-Type: application/json" \
        -d "{\"ticker\":\"$ticker\",\"allocation_pct\":$allocation.0}" 2>&1)
    
    local end_time=$(date +%s.%N)
    
    # Parse response
    local http_code=$(echo "$response" | tail -2 | head -1)
    local time_total=$(echo "$response" | tail -1)
    local body=$(echo "$response" | head -n -2)
    
    # Check for success
    if [[ "$http_code" == "200" ]]; then
        echo "$request_num,$ticker,$allocation,$time_total,success" >> "$RESULTS_FILE"
    else
        echo "$request_num,$ticker,$allocation,$time_total,error,$http_code" >> "$RESULTS_FILE"
        echo "Request $request_num failed: HTTP $http_code" >> "$ERRORS_FILE"
    fi
}

# Function to run concurrent requests
run_concurrent_batch() {
    local batch_start=$1
    local batch_size=$2
    
    for ((i=0; i<batch_size; i++)); do
        make_request $((batch_start + i)) &
    done
    wait
}

echo "=========================================="
echo "PHASE 1: Warm-up (5 requests)"
echo "=========================================="
echo ""

# Warm-up phase
for i in {1..5}; do
    curl -s -X POST "$API_URL/safety-check" \
        -H "Content-Type: application/json" \
        -d '{"ticker":"MSFT","allocation_pct":10.0}' > /dev/null
    echo -e "${GREEN}Warm-up request $i complete${NC}"
done
echo ""

echo "=========================================="
echo "PHASE 2: Sequential Load Test"
echo "=========================================="
echo ""

echo "Running $((TOTAL_REQUESTS / 2)) sequential requests..."
SEQ_START=$(date +%s.%N)

for ((i=1; i<=TOTAL_REQUESTS/2; i++)); do
    make_request $i
    if ((i % 10 == 0)); then
        echo -e "${BLUE}Completed $i sequential requests${NC}"
    fi
done

SEQ_END=$(date +%s.%N)
SEQ_DURATION=$(echo "$SEQ_END - $SEQ_START" | bc)
echo ""
echo -e "${GREEN}Sequential phase complete in ${SEQ_DURATION}s${NC}"
echo ""

echo "=========================================="
echo "PHASE 3: Concurrent Load Test"
echo "=========================================="
echo ""

echo "Running $((TOTAL_REQUESTS / 2)) concurrent requests ($CONCURRENT_USERS at a time)..."
CONC_START=$(date +%s.%N)

batch_count=$((TOTAL_REQUESTS / 2 / CONCURRENT_USERS))
for ((batch=0; batch<batch_count; batch++)); do
    batch_start=$((TOTAL_REQUESTS / 2 + batch * CONCURRENT_USERS + 1))
    run_concurrent_batch $batch_start $CONCURRENT_USERS
    echo -e "${BLUE}Completed batch $((batch + 1))/$batch_count${NC}"
done

CONC_END=$(date +%s.%N)
CONC_DURATION=$(echo "$CONC_END - $CONC_START" | bc)
echo ""
echo -e "${GREEN}Concurrent phase complete in ${CONC_DURATION}s${NC}"
echo ""

echo "=========================================="
echo "PHASE 4: Stress Test (Burst)"
echo "=========================================="
echo ""

echo "Running burst of $CONCURRENT_USERS simultaneous requests..."
BURST_START=$(date +%s.%N)

for ((i=0; i<CONCURRENT_USERS; i++)); do
    curl -s -X POST "$API_URL/safety-check" \
        -H "Content-Type: application/json" \
        -d '{"ticker":"MSFT","allocation_pct":10.0}' > /dev/null &
done
wait

BURST_END=$(date +%s.%N)
BURST_DURATION=$(echo "$BURST_END - $BURST_START" | bc)
echo -e "${GREEN}Burst complete in ${BURST_DURATION}s${NC}"
echo ""

echo "=========================================="
echo "PHASE 5: Health Check Under Load"
echo "=========================================="
echo ""

# Check health endpoint responds correctly after load
health_response=$(curl -s "$API_URL/health")
if echo "$health_response" | grep -q '"status":"healthy"'; then
    echo -e "${GREEN}Health check: PASSED${NC}"
    echo "$health_response" | python3 -m json.tool 2>/dev/null || echo "$health_response"
else
    echo -e "${RED}Health check: FAILED${NC}"
    echo "$health_response"
fi
echo ""

echo "=========================================="
echo "PHASE 6: Memory Check"
echo "=========================================="
echo ""

# Check cache stats
cache_response=$(curl -s "$API_URL/cache-stats")
echo "Cache Statistics:"
echo "$cache_response" | python3 -m json.tool 2>/dev/null || echo "$cache_response"
echo ""

echo "=========================================="
echo "LOAD TEST RESULTS"
echo "=========================================="
echo ""

# Calculate statistics
total_requests=$(wc -l < "$RESULTS_FILE")
successful=$(grep -c ",success" "$RESULTS_FILE" 2>/dev/null || echo 0)
failed=$(grep -c ",error" "$RESULTS_FILE" 2>/dev/null || echo 0)

# Calculate response times
if [[ -s "$RESULTS_FILE" ]]; then
    avg_time=$(awk -F',' '{sum+=$4; count++} END {if(count>0) printf "%.3f", sum/count; else print "0"}' "$RESULTS_FILE")
    min_time=$(awk -F',' 'NR==1 || $4<min {min=$4} END {printf "%.3f", min}' "$RESULTS_FILE")
    max_time=$(awk -F',' '$4>max {max=$4} END {printf "%.3f", max}' "$RESULTS_FILE")
    
    # Calculate percentiles
    p50=$(sort -t',' -k4 -n "$RESULTS_FILE" | awk -F',' -v p=0.5 'NR==1{count=0} {times[count++]=$4} END {idx=int(count*p); printf "%.3f", times[idx]}')
    p95=$(sort -t',' -k4 -n "$RESULTS_FILE" | awk -F',' -v p=0.95 'NR==1{count=0} {times[count++]=$4} END {idx=int(count*p); printf "%.3f", times[idx]}')
    p99=$(sort -t',' -k4 -n "$RESULTS_FILE" | awk -F',' -v p=0.99 'NR==1{count=0} {times[count++]=$4} END {idx=int(count*p); printf "%.3f", times[idx]}')
else
    avg_time="0"
    min_time="0"
    max_time="0"
    p50="0"
    p95="0"
    p99="0"
fi

# Calculate throughput
total_duration=$(echo "$SEQ_DURATION + $CONC_DURATION" | bc)
if [[ $(echo "$total_duration > 0" | bc) -eq 1 ]]; then
    throughput=$(echo "scale=2; $total_requests / $total_duration" | bc)
else
    throughput="N/A"
fi

success_rate=$(echo "scale=2; $successful * 100 / $total_requests" | bc 2>/dev/null || echo "0")

echo "Summary:"
echo "--------"
echo "Total Requests: $total_requests"
echo -e "Successful: ${GREEN}$successful${NC}"
echo -e "Failed: ${RED}$failed${NC}"
echo "Success Rate: ${success_rate}%"
echo ""
echo "Response Times:"
echo "---------------"
echo "Average: ${avg_time}s"
echo "Min: ${min_time}s"
echo "Max: ${max_time}s"
echo "P50 (Median): ${p50}s"
echo "P95: ${p95}s"
echo "P99: ${p99}s"
echo ""
echo "Throughput:"
echo "-----------"
echo "Sequential Duration: ${SEQ_DURATION}s"
echo "Concurrent Duration: ${CONC_DURATION}s"
echo "Burst Duration: ${BURST_DURATION}s"
echo "Requests/Second: ${throughput}"
echo ""

# Performance targets check
echo "=========================================="
echo "PERFORMANCE TARGETS"
echo "=========================================="
echo ""

targets_met=0
targets_total=5

# Target 1: Success rate > 99%
if (( $(echo "$success_rate >= 99" | bc -l) )); then
    echo -e "${GREEN}[PASS]${NC} Success Rate >= 99% (${success_rate}%)"
    ((targets_met++))
else
    echo -e "${RED}[FAIL]${NC} Success Rate >= 99% (${success_rate}%)"
fi

# Target 2: Average response time < 5s
if (( $(echo "$avg_time < 5" | bc -l) )); then
    echo -e "${GREEN}[PASS]${NC} Average Response Time < 5s (${avg_time}s)"
    ((targets_met++))
else
    echo -e "${RED}[FAIL]${NC} Average Response Time < 5s (${avg_time}s)"
fi

# Target 3: P95 < 10s
if (( $(echo "$p95 < 10" | bc -l) )); then
    echo -e "${GREEN}[PASS]${NC} P95 Response Time < 10s (${p95}s)"
    ((targets_met++))
else
    echo -e "${RED}[FAIL]${NC} P95 Response Time < 10s (${p95}s)"
fi

# Target 4: No errors
if [[ "$failed" -eq 0 ]]; then
    echo -e "${GREEN}[PASS]${NC} Zero Errors"
    ((targets_met++))
else
    echo -e "${RED}[FAIL]${NC} Zero Errors ($failed errors)"
fi

# Target 5: Health check passes after load
if echo "$health_response" | grep -q '"status":"healthy"'; then
    echo -e "${GREEN}[PASS]${NC} System Healthy After Load"
    ((targets_met++))
else
    echo -e "${RED}[FAIL]${NC} System Healthy After Load"
fi

echo ""
echo "Targets Met: $targets_met/$targets_total"
echo ""

# Show errors if any
if [[ -s "$ERRORS_FILE" ]]; then
    echo "=========================================="
    echo "ERRORS"
    echo "=========================================="
    cat "$ERRORS_FILE"
    echo ""
fi

# Cleanup
rm -f "$RESULTS_FILE" "$ERRORS_FILE"

# Final status
echo "=========================================="
if [[ "$targets_met" -eq "$targets_total" ]]; then
    echo -e "${GREEN}LOAD TEST PASSED - All targets met!${NC}"
    echo "=========================================="
    exit 0
else
    echo -e "${YELLOW}LOAD TEST COMPLETED - $targets_met/$targets_total targets met${NC}"
    echo "=========================================="
    exit 1
fi
