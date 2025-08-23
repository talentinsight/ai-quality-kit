#!/usr/bin/env python3
"""
Demonstration of percentile latency metrics in AI Quality Kit.

This script shows how to:
1. Enable percentile tracking
2. Make API requests and observe percentile headers
3. Verify different endpoints track separately
"""

import os
import time
import requests
from typing import Dict, Optional

# Configuration
API_BASE_URL = "http://localhost:8000"


def print_headers(response: requests.Response, label: str):
    """Print relevant performance headers from response."""
    print(f"\n{label}:")
    print(f"  Status: {response.status_code}")
    
    # Always present headers
    print(f"  X-Perf-Phase: {response.headers.get('X-Perf-Phase', 'N/A')}")
    print(f"  X-Latency-MS: {response.headers.get('X-Latency-MS', 'N/A')}")
    
    # Percentile headers (when enabled)
    p50 = response.headers.get('X-P50-MS')
    p95 = response.headers.get('X-P95-MS')
    
    if p50 and p95:
        print(f"  X-P50-MS: {p50}")
        print(f"  X-P95-MS: {p95}")
        print(f"  Percentile ratio (p95/p50): {float(p95)/float(p50):.2f}")
    else:
        print("  Percentile headers: Not present (disabled or insufficient data)")


def make_ask_request(query: str) -> requests.Response:
    """Make a request to the /ask endpoint."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/ask",
            json={"query": query, "provider": "mock"},
            timeout=10
        )
        return response
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        raise


def make_testdata_request(qaset_data: str) -> requests.Response:
    """Make a request to the /testdata/paste endpoint."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/testdata/paste",
            json={"qaset": qaset_data},
            timeout=10
        )
        return response
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        raise


def demo_percentiles_disabled():
    """Demonstrate behavior when percentiles are disabled."""
    print("=== Demo 1: Percentiles Disabled (Default) ===")
    print("Making requests with PERF_PERCENTILES_ENABLED=false...")
    
    for i in range(3):
        response = make_ask_request(f"Test query {i+1}")
        print_headers(response, f"Request {i+1}")
        time.sleep(0.1)  # Small delay


def demo_percentiles_enabled():
    """Demonstrate behavior when percentiles are enabled."""
    print("\n=== Demo 2: Percentiles Enabled ===")
    print("NOTE: To see this demo, restart the server with:")
    print("PERF_PERCENTILES_ENABLED=true PERF_WINDOW=10 uvicorn apps.rag_service.main:app")
    print("\nMaking requests to accumulate percentile data...")
    
    for i in range(5):
        response = make_ask_request(f"Percentile test query {i+1}")
        print_headers(response, f"Request {i+1}")
        time.sleep(0.2)  # Small delay between requests


def demo_separate_endpoint_tracking():
    """Demonstrate that different endpoints track percentiles separately."""
    print("\n=== Demo 3: Separate Endpoint Tracking ===")
    print("Making requests to different endpoints to show separate tracking...")
    
    # Make requests to /ask endpoint
    print("\n--- /ask endpoint requests ---")
    for i in range(3):
        response = make_ask_request(f"Ask endpoint query {i+1}")
        print_headers(response, f"/ask Request {i+1}")
        time.sleep(0.1)
    
    # Make requests to /testdata endpoint
    print("\n--- /testdata endpoint requests ---")
    for i in range(3):
        qaset = f'{{"qid": "test{i+1}", "question": "What is {i+1}+{i+1}?", "expected_answer": "{(i+1)*2}"}}'
        try:
            response = make_testdata_request(qaset)
            print_headers(response, f"/testdata Request {i+1}")
        except Exception as e:
            print(f"/testdata Request {i+1}: Failed ({e})")
        time.sleep(0.1)


def demo_percentile_behavior():
    """Demonstrate percentile calculation behavior."""
    print("\n=== Demo 4: Percentile Calculation Behavior ===")
    print("Making requests with artificial delays to show percentile evolution...")
    
    delays = [0.0, 0.1, 0.05, 0.15, 0.08, 0.2, 0.12]
    
    for i, delay in enumerate(delays):
        time.sleep(delay)  # Artificial delay to vary response times
        response = make_ask_request(f"Delay test query {i+1}")
        print_headers(response, f"Request {i+1} (with {delay*1000:.0f}ms artificial delay)")


def check_server_status():
    """Check if the server is running and what configuration it has."""
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=5)
        print(f"✅ Server is running at {API_BASE_URL}")
        return True
    except requests.exceptions.RequestException:
        print(f"❌ Server is not running at {API_BASE_URL}")
        print("Please start the server with: uvicorn apps.rag_service.main:app --reload")
        return False


def main():
    """Run the percentile demonstration."""
    print("=== AI Quality Kit Percentile Latency Metrics Demo ===\n")
    
    # Check server status
    if not check_server_status():
        return
    
    print("\nThis demo shows percentile latency metrics in HTTP response headers.")
    print("The system tracks p50 and p95 latencies per endpoint when enabled.\n")
    
    # Demo 1: Default behavior (disabled)
    demo_percentiles_disabled()
    
    # Demo 2: Enabled behavior
    demo_percentiles_enabled()
    
    # Demo 3: Separate tracking
    demo_separate_endpoint_tracking()
    
    # Demo 4: Percentile behavior
    demo_percentile_behavior()
    
    print("\n=== Demo Complete ===")
    print("\nKey Observations:")
    print("1. X-Perf-Phase and X-Latency-MS are always present")
    print("2. X-P50-MS and X-P95-MS appear only when PERF_PERCENTILES_ENABLED=true")
    print("3. Percentiles require at least 2 data points to calculate")
    print("4. Different endpoints (/ask, /testdata/*) track percentiles separately")
    print("5. p50 ≤ p95 is always maintained (monotonic property)")
    print("6. Sliding window keeps most recent N latency measurements")
    
    print("\nConfiguration:")
    print("- PERF_PERCENTILES_ENABLED: Enable/disable percentile tracking")
    print("- PERF_WINDOW: Number of recent latencies to keep per endpoint (default: 500)")


if __name__ == "__main__":
    main()
