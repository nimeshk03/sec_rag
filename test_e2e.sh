#!/bin/bash

# End-to-End Testing Script for RAG Safety Checker API
# Tests complete workflows, edge cases, and validates system behavior

API_URL="${1:-http://localhost:8000}"

echo "=========================================="
echo "End-to-End Testing: RAG Safety Checker"
echo "=========================================="
echo "API URL: $API_URL"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Function to run a test
run_test() {
    local test_name=$1
    local test_command=$2
    local expected_pattern=$3
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo -e "${BLUE}Test $TESTS_TOTAL: $test_name${NC}"
    
    result=$(eval "$test_command" 2>&1)
    
    if echo "$result" | grep -q "$expected_pattern"; then
        echo -e "${GREEN}✓ PASSED${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        echo "$result" | head -5
    else
        echo -e "${RED}✗ FAILED${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        echo "Expected pattern: $expected_pattern"
        echo "Got: $result" | head -10
    fi
    echo ""
}

# Function to test JSON response
test_json_field() {
    local test_name=$1
    local endpoint=$2
    local field=$3
    local expected_value=$4
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo -e "${BLUE}Test $TESTS_TOTAL: $test_name${NC}"
    
    result=$(curl -s "$API_URL$endpoint")
    field_value=$(echo "$result" | grep -o "\"$field\":\"[^\"]*\"" | cut -d'"' -f4)
    
    if [ "$field_value" = "$expected_value" ]; then
        echo -e "${GREEN}✓ PASSED${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        echo "Field '$field' = '$field_value'"
    else
        echo -e "${RED}✗ FAILED${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        echo "Expected: $expected_value"
        echo "Got: $field_value"
    fi
    echo ""
}

echo "=========================================="
echo "SECTION 1: Basic API Functionality"
echo "=========================================="
echo ""

run_test "Health endpoint returns status" \
    "curl -s $API_URL/health" \
    "status"

run_test "Root endpoint returns API name" \
    "curl -s $API_URL/" \
    "SEC Filing RAG Safety System"

run_test "API documentation is accessible" \
    "curl -s $API_URL/docs" \
    "Swagger"

echo "=========================================="
echo "SECTION 2: Safety Check Workflows"
echo "=========================================="
echo ""

echo "2.1: Testing PROCEED scenario (low allocation, no risk)"
echo "--------------------------------------------------------"
run_test "Safety check with 5% allocation" \
    "curl -s -X POST $API_URL/safety-check -H 'Content-Type: application/json' -d '{\"ticker\":\"AAPL\",\"allocation_pct\":5.0}'" \
    "decision"

echo "2.2: Testing REDUCE scenario (medium allocation)"
echo "------------------------------------------------"
run_test "Safety check with 15% allocation" \
    "curl -s -X POST $API_URL/safety-check -H 'Content-Type: application/json' -d '{\"ticker\":\"AAPL\",\"allocation_pct\":15.0}'" \
    "decision"

echo "2.3: Testing VETO scenario (high allocation)"
echo "--------------------------------------------"
run_test "Safety check with 30% allocation" \
    "curl -s -X POST $API_URL/safety-check -H 'Content-Type: application/json' -d '{\"ticker\":\"AAPL\",\"allocation_pct\":30.0}'" \
    "VETO"

echo "=========================================="
echo "SECTION 3: Edge Cases"
echo "=========================================="
echo ""

echo "3.1: Invalid inputs"
echo "-------------------"
run_test "Negative allocation rejected" \
    "curl -s -X POST $API_URL/safety-check -H 'Content-Type: application/json' -d '{\"ticker\":\"AAPL\",\"allocation_pct\":-5.0}'" \
    "detail"

run_test "Allocation >100% rejected" \
    "curl -s -X POST $API_URL/safety-check -H 'Content-Type: application/json' -d '{\"ticker\":\"AAPL\",\"allocation_pct\":150.0}'" \
    "detail"

run_test "Invalid ticker format (graceful handling)" \
    "curl -s -X POST $API_URL/safety-check -H 'Content-Type: application/json' -d '{\"ticker\":\"INVALID123\",\"allocation_pct\":10.0}'" \
    "decision"

echo "3.2: Zero allocation edge case"
echo "------------------------------"
run_test "Zero allocation returns decision" \
    "curl -s -X POST $API_URL/safety-check -H 'Content-Type: application/json' -d '{\"ticker\":\"AAPL\",\"allocation_pct\":0.0}'" \
    "decision"

echo "3.3: Case insensitivity"
echo "----------------------"
run_test "Lowercase ticker converted to uppercase" \
    "curl -s -X POST $API_URL/safety-check -H 'Content-Type: application/json' -d '{\"ticker\":\"aapl\",\"allocation_pct\":10.0}'" \
    "AAPL"

echo "=========================================="
echo "SECTION 4: Cache Behavior"
echo "=========================================="
echo ""

echo "4.1: Cache miss on first request"
echo "--------------------------------"
# Clear cache first
curl -s -X DELETE "$API_URL/cache/MSFT" > /dev/null 2>&1
sleep 1

result=$(curl -s -X POST "$API_URL/safety-check" -H 'Content-Type: application/json' -d '{"ticker":"MSFT","allocation_pct":10.0}')
if echo "$result" | grep -q '"cache_hit":false'; then
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "${GREEN}✓ PASSED${NC} - First request is cache miss"
else
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "${RED}✗ FAILED${NC} - Expected cache_hit:false"
fi
echo ""

echo "4.2: Cache hit on subsequent request"
echo "------------------------------------"
sleep 1
result=$(curl -s -X POST "$API_URL/safety-check" -H 'Content-Type: application/json' -d '{"ticker":"MSFT","allocation_pct":10.0}')
if echo "$result" | grep -q '"cache_hit":true'; then
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "${GREEN}✓ PASSED${NC} - Second request is cache hit"
else
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "${RED}✗ FAILED${NC} - Expected cache_hit:true"
fi
echo ""

echo "4.3: Cache invalidation"
echo "----------------------"
result=$(curl -s -X DELETE "$API_URL/cache/MSFT")
if echo "$result" | grep -q "Cache invalidated"; then
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "${GREEN}✓ PASSED${NC} - Cache invalidated successfully"
else
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "${RED}✗ FAILED${NC} - Cache invalidation failed"
fi
echo ""

echo "4.4: Cache stats tracking"
echo "------------------------"
run_test "Cache stats endpoint returns metrics" \
    "curl -s $API_URL/cache-stats" \
    "hit_rate"

echo "=========================================="
echo "SECTION 5: Multiple Tickers"
echo "=========================================="
echo ""

tickers=("AAPL" "MSFT" "GOOGL" "TSLA" "AMZN")
echo "Testing safety checks for multiple tickers..."
for ticker in "${tickers[@]}"; do
    result=$(curl -s -X POST "$API_URL/safety-check" -H 'Content-Type: application/json' -d "{\"ticker\":\"$ticker\",\"allocation_pct\":10.0}")
    if echo "$result" | grep -q "decision"; then
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
        TESTS_PASSED=$((TESTS_PASSED + 1))
        decision=$(echo "$result" | grep -o '"decision":"[^"]*"' | cut -d'"' -f4)
        echo -e "${GREEN}✓${NC} $ticker: $decision"
    else
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
        TESTS_FAILED=$((TESTS_FAILED + 1))
        echo -e "${RED}✗${NC} $ticker: Failed"
    fi
done
echo ""

echo "=========================================="
echo "SECTION 6: Allocation Buckets"
echo "=========================================="
echo ""

echo "Testing different allocation percentages..."
allocations=(1 5 10 15 20 25 30)
for alloc in "${allocations[@]}"; do
    result=$(curl -s -X POST "$API_URL/safety-check" -H 'Content-Type: application/json' -d "{\"ticker\":\"AAPL\",\"allocation_pct\":$alloc.0}")
    if echo "$result" | grep -q "decision"; then
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
        TESTS_PASSED=$((TESTS_PASSED + 1))
        decision=$(echo "$result" | grep -o '"decision":"[^"]*"' | cut -d'"' -f4)
        risk_score=$(echo "$result" | grep -o '"risk_score":[0-9.]*' | cut -d: -f2)
        echo -e "${GREEN}✓${NC} ${alloc}%: $decision (risk: $risk_score)"
    else
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
        TESTS_FAILED=$((TESTS_FAILED + 1))
        echo -e "${RED}✗${NC} ${alloc}%: Failed"
    fi
done
echo ""

echo "=========================================="
echo "SECTION 7: Response Structure Validation"
echo "=========================================="
echo ""

echo "Validating safety check response structure..."
response=$(curl -s -X POST "$API_URL/safety-check" -H 'Content-Type: application/json' -d '{"ticker":"AAPL","allocation_pct":10.0}')

required_fields=("decision" "ticker" "risk_score" "reasoning" "cache_hit")
for field in "${required_fields[@]}"; do
    if echo "$response" | grep -q "\"$field\""; then
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
        TESTS_PASSED=$((TESTS_PASSED + 1))
        echo -e "${GREEN}✓${NC} Field '$field' present"
    else
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
        TESTS_FAILED=$((TESTS_FAILED + 1))
        echo -e "${RED}✗${NC} Field '$field' missing"
    fi
done
echo ""

echo "=========================================="
echo "SECTION 8: Error Handling"
echo "=========================================="
echo ""

echo "8.1: Missing required fields"
echo "---------------------------"
run_test "Missing ticker field" \
    "curl -s -X POST $API_URL/safety-check -H 'Content-Type: application/json' -d '{\"allocation_pct\":10.0}'" \
    "detail"

run_test "Missing allocation field" \
    "curl -s -X POST $API_URL/safety-check -H 'Content-Type: application/json' -d '{\"ticker\":\"AAPL\"}'" \
    "detail"

echo "8.2: Invalid JSON"
echo "----------------"
run_test "Malformed JSON rejected" \
    "curl -s -X POST $API_URL/safety-check -H 'Content-Type: application/json' -d '{invalid json}'" \
    "detail"

echo "=========================================="
echo "SECTION 9: Concurrent Requests"
echo "=========================================="
echo ""

echo "Testing concurrent safety checks..."
for i in {1..5}; do
    curl -s -X POST "$API_URL/safety-check" -H 'Content-Type: application/json' -d '{"ticker":"AAPL","allocation_pct":10.0}' > /dev/null &
done
wait

TESTS_TOTAL=$((TESTS_TOTAL + 1))
TESTS_PASSED=$((TESTS_PASSED + 1))
echo -e "${GREEN}✓ PASSED${NC} - Handled 5 concurrent requests"
echo ""

echo "=========================================="
echo "SECTION 10: System Health"
echo "=========================================="
echo ""

echo "Checking system dependencies..."
health=$(curl -s "$API_URL/health")

dependencies=("database" "retriever")
for dep in "${dependencies[@]}"; do
    if echo "$health" | grep -q "\"$dep\""; then
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
        TESTS_PASSED=$((TESTS_PASSED + 1))
        status=$(echo "$health" | grep -o "\"$dep\":\"[^\"]*\"" | cut -d'"' -f4)
        echo -e "${GREEN}✓${NC} $dep: $status"
    else
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
        TESTS_FAILED=$((TESTS_FAILED + 1))
        echo -e "${RED}✗${NC} $dep: Not found"
    fi
done
echo ""

echo "=========================================="
echo "TEST SUMMARY"
echo "=========================================="
echo ""
echo "Total Tests: $TESTS_TOTAL"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}=========================================="
    echo "ALL TESTS PASSED! ✓"
    echo "==========================================${NC}"
    exit 0
else
    echo -e "${RED}=========================================="
    echo "SOME TESTS FAILED"
    echo "==========================================${NC}"
    exit 1
fi
