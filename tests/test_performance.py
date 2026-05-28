#!/usr/bin/env python3
"""Performance test script for EverFlow."""

import asyncio
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor

# Test the performance improvements
def test_dashboard_refresh():
    """Test dashboard refresh performance."""
    print("Testing dashboard refresh performance...")

    # Simulate dashboard refresh calls
    base_url = "http://localhost:8000"
    endpoints = [
        "/dashboard/summary",
        "/dashboard/keys",
        "/dashboard/logs?limit=50",
        "/dashboard/chart/rpm",
        "/dashboard/config"
    ]

    start_time = time.time()

    # Simulate concurrent dashboard requests
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for endpoint in endpoints:
            futures.append(executor.submit(
                lambda e: requests.get(f"{base_url}{e}", timeout=5).status_code,
                endpoint
            ))

        results = [f.result() for f in futures]

    end_time = time.time()

    print(f"Dashboard refresh completed in {end_time - start_time:.3f} seconds")
    print(f"Results: {results}")
    return end_time - start_time

def test_proxy_throughput():
    """Test proxy request throughput."""
    print("\nTesting proxy request throughput...")

    # Simulate concurrent proxy requests
    url = "http://localhost:8000/v1/messages"
    payload = {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 100
    }

    start_time = time.time()

    # Make multiple concurrent requests
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for i in range(20):  # 20 test requests
            futures.append(executor.submit(
                lambda: requests.post(url, json=payload, timeout=10).status_code
            ))

        results = [f.result() for f in futures]

    end_time = time.time()

    print(f"20 proxy requests completed in {end_time - start_time:.3f} seconds")
    print(f"Average: {(end_time - start_time) / 20:.3f} seconds per request")
    print(f"Results: {results}")
    return end_time - start_time

if __name__ == "__main__":
    print("EverFlow Performance Test")
    print("=" * 40)

    try:
        # Test dashboard performance
        dashboard_time = test_dashboard_refresh()

        # Test proxy performance
        proxy_time = test_proxy_throughput()

        print(f"\nPerformance Summary:")
        print(f"- Dashboard refresh: {dashboard_time:.3f}s")
        print(f"- Proxy throughput: {proxy_time:.3f}s for 20 requests")
        print(f"- Avg proxy latency: {proxy_time / 20:.3f}s per request")

    except Exception as e:
        print(f"Error during performance test: {e}")
        print("Make sure EverFlow is running on localhost:8000")