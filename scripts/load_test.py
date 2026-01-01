#!/usr/bin/env python3
"""
Load Testing Script for RAG Safety Checker API.
Tests system stability under realistic load conditions.
"""

import argparse
import time
import statistics
import concurrent.futures
import requests
import random
import sys

# Test configuration
TICKERS = ["MSFT", "AAPL", "GOOGL", "TSLA", "AMZN"]
ALLOCATIONS = [5, 10, 15, 20, 25]


def make_request(api_url: str, request_id: int) -> dict:
    """Make a single safety check request."""
    ticker = random.choice(TICKERS)
    allocation = random.choice(ALLOCATIONS)
    
    start_time = time.time()
    try:
        response = requests.post(
            f"{api_url}/safety-check",
            json={"ticker": ticker, "allocation_pct": float(allocation)},
            timeout=30
        )
        elapsed = time.time() - start_time
        
        return {
            "id": request_id,
            "ticker": ticker,
            "allocation": allocation,
            "status_code": response.status_code,
            "elapsed": elapsed,
            "success": response.status_code == 200,
            "error": None
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "id": request_id,
            "ticker": ticker,
            "allocation": allocation,
            "status_code": 0,
            "elapsed": elapsed,
            "success": False,
            "error": str(e)
        }


def run_sequential_test(api_url: str, num_requests: int) -> list:
    """Run sequential requests."""
    results = []
    for i in range(num_requests):
        result = make_request(api_url, i + 1)
        results.append(result)
        if (i + 1) % 10 == 0:
            print(f"  Sequential: {i + 1}/{num_requests} complete")
    return results


def run_concurrent_test(api_url: str, num_requests: int, concurrency: int) -> list:
    """Run concurrent requests."""
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(make_request, api_url, i + 1)
            for i in range(num_requests)
        ]
        
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
            completed += 1
            if completed % 10 == 0:
                print(f"  Concurrent: {completed}/{num_requests} complete")
    
    return results


def check_health(api_url: str) -> bool:
    """Check if API is healthy."""
    try:
        response = requests.get(f"{api_url}/health", timeout=10)
        return response.status_code == 200 and "healthy" in response.text
    except:
        return False


def get_cache_stats(api_url: str) -> dict:
    """Get cache statistics."""
    try:
        response = requests.get(f"{api_url}/cache-stats", timeout=10)
        return response.json()
    except:
        return {}


def calculate_percentile(data: list, percentile: float) -> float:
    """Calculate percentile of a list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    index = int(len(sorted_data) * percentile)
    return sorted_data[min(index, len(sorted_data) - 1)]


def main():
    parser = argparse.ArgumentParser(description="Load test the RAG Safety Checker API")
    parser.add_argument("--url", default="http://localhost:8000", help="API URL")
    parser.add_argument("--requests", type=int, default=100, help="Total requests")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent users")
    args = parser.parse_args()
    
    print("=" * 50)
    print("Load Testing: RAG Safety Checker")
    print("=" * 50)
    print(f"API URL: {args.url}")
    print(f"Total Requests: {args.requests}")
    print(f"Concurrent Users: {args.concurrency}")
    print("=" * 50)
    print()
    
    # Phase 1: Warm-up
    print("PHASE 1: Warm-up (5 requests)")
    print("-" * 30)
    for i in range(5):
        make_request(args.url, i)
        print(f"  Warm-up {i + 1}/5 complete")
    print()
    
    # Phase 2: Sequential test
    print("PHASE 2: Sequential Load Test")
    print("-" * 30)
    seq_count = args.requests // 2
    seq_start = time.time()
    seq_results = run_sequential_test(args.url, seq_count)
    seq_duration = time.time() - seq_start
    print(f"  Duration: {seq_duration:.2f}s")
    print()
    
    # Phase 3: Concurrent test
    print("PHASE 3: Concurrent Load Test")
    print("-" * 30)
    conc_count = args.requests // 2
    conc_start = time.time()
    conc_results = run_concurrent_test(args.url, conc_count, args.concurrency)
    conc_duration = time.time() - conc_start
    print(f"  Duration: {conc_duration:.2f}s")
    print()
    
    # Phase 4: Burst test
    print("PHASE 4: Stress Test (Burst)")
    print("-" * 30)
    burst_start = time.time()
    burst_results = run_concurrent_test(args.url, args.concurrency, args.concurrency)
    burst_duration = time.time() - burst_start
    print(f"  Burst of {args.concurrency} simultaneous requests: {burst_duration:.2f}s")
    print()
    
    # Combine all results
    all_results = seq_results + conc_results + burst_results
    
    # Phase 5: Health check
    print("PHASE 5: Health Check After Load")
    print("-" * 30)
    health_ok = check_health(args.url)
    print(f"  Health Status: {'HEALTHY' if health_ok else 'UNHEALTHY'}")
    print()
    
    # Phase 6: Cache stats
    print("PHASE 6: Cache Statistics")
    print("-" * 30)
    cache_stats = get_cache_stats(args.url)
    for key, value in cache_stats.items():
        print(f"  {key}: {value}")
    print()
    
    # Calculate statistics
    successful = [r for r in all_results if r["success"]]
    failed = [r for r in all_results if not r["success"]]
    response_times = [r["elapsed"] for r in all_results]
    
    total = len(all_results)
    success_count = len(successful)
    fail_count = len(failed)
    success_rate = (success_count / total * 100) if total > 0 else 0
    
    avg_time = statistics.mean(response_times) if response_times else 0
    min_time = min(response_times) if response_times else 0
    max_time = max(response_times) if response_times else 0
    p50 = calculate_percentile(response_times, 0.50)
    p95 = calculate_percentile(response_times, 0.95)
    p99 = calculate_percentile(response_times, 0.99)
    
    total_duration = seq_duration + conc_duration
    throughput = total / total_duration if total_duration > 0 else 0
    
    # Print results
    print("=" * 50)
    print("LOAD TEST RESULTS")
    print("=" * 50)
    print()
    print("Summary:")
    print("-" * 30)
    print(f"Total Requests: {total}")
    print(f"Successful: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Success Rate: {success_rate:.2f}%")
    print()
    print("Response Times:")
    print("-" * 30)
    print(f"Average: {avg_time:.3f}s")
    print(f"Min: {min_time:.3f}s")
    print(f"Max: {max_time:.3f}s")
    print(f"P50 (Median): {p50:.3f}s")
    print(f"P95: {p95:.3f}s")
    print(f"P99: {p99:.3f}s")
    print()
    print("Throughput:")
    print("-" * 30)
    print(f"Sequential Duration: {seq_duration:.2f}s")
    print(f"Concurrent Duration: {conc_duration:.2f}s")
    print(f"Burst Duration: {burst_duration:.2f}s")
    print(f"Requests/Second: {throughput:.2f}")
    print()
    
    # Performance targets
    print("=" * 50)
    print("PERFORMANCE TARGETS")
    print("=" * 50)
    print()
    
    targets_met = 0
    targets_total = 5
    
    # Target 1: Success rate >= 99%
    if success_rate >= 99:
        print(f"[PASS] Success Rate >= 99% ({success_rate:.2f}%)")
        targets_met += 1
    else:
        print(f"[FAIL] Success Rate >= 99% ({success_rate:.2f}%)")
    
    # Target 2: Average response time < 5s
    if avg_time < 5:
        print(f"[PASS] Average Response Time < 5s ({avg_time:.3f}s)")
        targets_met += 1
    else:
        print(f"[FAIL] Average Response Time < 5s ({avg_time:.3f}s)")
    
    # Target 3: P95 < 10s
    if p95 < 10:
        print(f"[PASS] P95 Response Time < 10s ({p95:.3f}s)")
        targets_met += 1
    else:
        print(f"[FAIL] P95 Response Time < 10s ({p95:.3f}s)")
    
    # Target 4: No errors
    if fail_count == 0:
        print("[PASS] Zero Errors")
        targets_met += 1
    else:
        print(f"[FAIL] Zero Errors ({fail_count} errors)")
    
    # Target 5: Health check passes
    if health_ok:
        print("[PASS] System Healthy After Load")
        targets_met += 1
    else:
        print("[FAIL] System Healthy After Load")
    
    print()
    print(f"Targets Met: {targets_met}/{targets_total}")
    print()
    
    # Show errors if any
    if failed:
        print("=" * 50)
        print("ERRORS")
        print("=" * 50)
        for r in failed[:10]:  # Show first 10 errors
            print(f"  Request {r['id']}: {r['error']}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more errors")
        print()
    
    # Final status
    print("=" * 50)
    if targets_met == targets_total:
        print("LOAD TEST PASSED - All targets met!")
        print("=" * 50)
        return 0
    else:
        print(f"LOAD TEST COMPLETED - {targets_met}/{targets_total} targets met")
        print("=" * 50)
        return 1


if __name__ == "__main__":
    sys.exit(main())
