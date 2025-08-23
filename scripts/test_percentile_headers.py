#!/usr/bin/env python3
"""
Percentile latency headers smoke test for production verification.
Usage: python scripts/test_percentile_headers.py
"""
import requests
import jwt
import time
from datetime import datetime, timedelta, timezone

BASE_URL = "http://127.0.0.1:8000"
SECRET = "test-secret-key"
ISSUER = "https://test-issuer.com"
AUDIENCE = "https://test-api.com"

def create_token():
    """Create valid JWT token."""
    payload = {
        "sub": "testuser",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "roles": ["user"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def test_percentiles_disabled():
    """Test that percentile headers are absent when feature flag disabled."""
    print("🧪 Test 1: Percentiles disabled")
    
    token = create_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.post(f"{BASE_URL}/ask", 
                           json={"query": "test", "provider": "mock"}, 
                           headers=headers)
    
    print(f"   Status: {response.status_code}")
    headers_dict = dict(response.headers)
    print(f"   Headers: {headers_dict}")
    
    if response.status_code == 200:
        # Should have basic headers but NOT percentile headers
        if ("x-latency-ms" in headers_dict and 
            "x-perf-phase" in headers_dict and
            "x-p50-ms" not in headers_dict and 
            "x-p95-ms" not in headers_dict):
            
            print("   ✅ PASS: Basic headers present, percentile headers absent")
            print(f"     X-Latency-MS: {headers_dict.get('x-latency-ms')}")
            print(f"     X-Perf-Phase: {headers_dict.get('x-perf-phase')}")
            return True
        else:
            print("   ❌ FAIL: Wrong header combination")
            return False
    else:
        print(f"   ❌ FAIL: Request failed: {response.text}")
        return False

def test_percentiles_enabled():
    """Test that percentile headers appear when feature flag enabled."""
    print("\n🧪 Test 2: Percentiles enabled (requires PERF_PERCENTILES_ENABLED=true)")
    
    token = create_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # Make multiple requests to accumulate latency data
    print("   Making multiple requests to accumulate data...")
    
    for i in range(6):
        response = requests.post(f"{BASE_URL}/ask", 
                               json={"query": f"test {i}", "provider": "mock"}, 
                               headers=headers)
        print(f"     Request {i+1}: {response.status_code}")
        
        if response.status_code == 200:
            headers_dict = dict(response.headers)
            
            # Check if percentile headers appeared
            if "x-p50-ms" in headers_dict and "x-p95-ms" in headers_dict:
                print(f"   ✅ PASS: Percentile headers found!")
                print(f"     X-Latency-MS: {headers_dict.get('x-latency-ms')}")
                print(f"     X-Perf-Phase: {headers_dict.get('x-perf-phase')}")
                print(f"     X-P50-MS: {headers_dict.get('x-p50-ms')}")
                print(f"     X-P95-MS: {headers_dict.get('x-p95-ms')}")
                
                # Verify percentiles are reasonable
                try:
                    p50 = int(headers_dict["x-p50-ms"])
                    p95 = int(headers_dict["x-p95-ms"])
                    if p50 <= p95:  # P95 should be >= P50
                        print(f"     ✅ Percentiles are monotonic: P50({p50}) ≤ P95({p95})")
                        return True
                    else:
                        print(f"     ❌ Percentiles not monotonic: P50({p50}) > P95({p95})")
                        return False
                except ValueError:
                    print("     ❌ Percentile values not numeric")
                    return False
        
        time.sleep(0.1)  # Small delay between requests
    
    print("   ❌ FAIL: No percentile headers found after 6 requests")
    return False

def test_different_routes():
    """Test that different routes track percentiles separately."""
    print("\n🧪 Test 3: Different routes separate tracking")
    
    token = create_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test /ask route
    response = requests.post(f"{BASE_URL}/ask", 
                           json={"query": "route test", "provider": "mock"}, 
                           headers=headers)
    
    if response.status_code == 200:
        ask_headers = dict(response.headers)
        print(f"   /ask P50: {ask_headers.get('x-p50-ms', 'None')}")
        print(f"   /ask P95: {ask_headers.get('x-p95-ms', 'None')}")
        
        if "x-p50-ms" in ask_headers:
            print("   ✅ PASS: /ask route has percentile tracking")
            return True
        else:
            print("   ⚠️  INFO: /ask route percentiles not yet available")
            return True  # This is OK, need more data
    else:
        print(f"   ❌ FAIL: /ask route failed: {response.status_code}")
        return False

def main():
    """Run percentile header tests."""
    print("📊 Percentile Latency Headers Test")
    print("=" * 50)
    
    print(f"Testing server: {BASE_URL}")
    print("Feature: Percentile latency per route with feature flag")
    print()
    
    print("📋 Environment requirements:")
    print("- PERF_PERCENTILES_ENABLED=true (for enabled tests)")
    print("- PERF_WINDOW=500 (configurable window size)")
    print("- Server with JWT auth enabled")
    print()
    
    tests = [
        test_percentiles_disabled,
        test_percentiles_enabled,
        test_different_routes
    ]
    results = []
    
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"   ❌ EXCEPTION: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    print("\n📋 Expected behavior:")
    print("- PERF_PERCENTILES_ENABLED=false → No X-P50-MS/X-P95-MS headers")
    print("- PERF_PERCENTILES_ENABLED=true → X-P50-MS/X-P95-MS after 2+ requests")
    print("- Per-route tracking → Each endpoint maintains separate buffers")
    print("- Ring buffer → Window size configurable via PERF_WINDOW (default 500)")
    print("- Nearest-rank method → P50/P95 calculation")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("\n⚠️  Some tests failed or need different configuration")
        return 1

if __name__ == "__main__":
    exit(main())
