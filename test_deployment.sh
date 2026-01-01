#!/bin/bash

# Test script to verify API endpoints before deployment

API_URL="${1:-http://localhost:8000}"

echo "Testing API at: $API_URL"
echo "================================"

# Test 1: Health endpoint
echo -e "\n1. Testing /health endpoint..."
HEALTH=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$API_URL/health")
echo "$HEALTH"

# Test 2: Root endpoint
echo -e "\n2. Testing / (root) endpoint..."
ROOT=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$API_URL/")
echo "$ROOT"

# Test 3: Safety check endpoint
echo -e "\n3. Testing /safety-check endpoint..."
SAFETY=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$API_URL/safety-check" \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "allocation_pct": 10.0}')
echo "$SAFETY"

# Test 4: Cache stats endpoint
echo -e "\n4. Testing /cache-stats endpoint..."
CACHE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$API_URL/cache-stats")
echo "$CACHE"

echo -e "\n================================"
echo "API testing complete!"
