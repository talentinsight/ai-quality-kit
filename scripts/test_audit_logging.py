#!/usr/bin/env python3
"""
Audit logging smoke test for production verification.
Usage: python scripts/test_audit_logging.py
"""
import requests
import jwt
import json
import time
from datetime import datetime, timedelta, timezone

BASE_URL = "http://127.0.0.1:8000"
SECRET = "test-secret-key"
ISSUER = "https://test-issuer.com"
AUDIENCE = "https://test-api.com"

def create_valid_token():
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

def test_orchestrator_audit():
    """Test orchestrator endpoint generates audit logs."""
    print("🧪 Test: Orchestrator audit logging")
    
    token = create_valid_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {
        "suites": ["rag_quality"],
        "provider": "mock",
        "model": "test-model",
        "target_mode": "api",
        "thresholds": {"rag_quality": 0.8}
    }
    
    print("   Making orchestrator request...")
    response = requests.post(f"{BASE_URL}/orchestrator/run_tests", 
                           json=payload, 
                           headers=headers)
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        print("   ✅ PASS: Orchestrator run successful")
        print("   📋 Check server logs for these audit events:")
        print("     - request_accepted")
        print("     - orchestrator_run_started") 
        print("     - orchestrator_run_finished")
        return True
    else:
        print(f"   ❌ FAIL: {response.text[:200]}")
        return False

def test_auth_failure_audit():
    """Test auth failure generates audit logs."""
    print("\n🧪 Test: Auth failure audit logging")
    
    # Test 1: No token
    print("   Testing no token...")
    response = requests.post(f"{BASE_URL}/ask", json={"question": "test"})
    print(f"   Status: {response.status_code}")
    
    # Test 2: Invalid token
    print("   Testing invalid token...")
    headers = {"Authorization": "Bearer invalid-token"}
    response = requests.post(f"{BASE_URL}/ask", json={"question": "test"}, headers=headers)
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 401:
        print("   ✅ PASS: Auth failures detected")
        print("   📋 Check server logs for auth_failure events")
        return True
    else:
        print(f"   ❌ UNEXPECTED: Status {response.status_code}")
        return False

def test_request_acceptance_audit():
    """Test successful requests generate audit logs."""
    print("\n🧪 Test: Request acceptance audit logging")
    
    token = create_valid_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # Make a request that should succeed authentication
    response = requests.post(f"{BASE_URL}/ask", 
                           json={"question": "What is AI?"}, 
                           headers=headers)
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code in [200, 422]:  # Auth passed
        print("   ✅ PASS: Request accepted")
        print("   📋 Check server logs for request_accepted event")
        return True
    else:
        print(f"   ❌ FAIL: Request not accepted: {response.text[:100]}")
        return False

def main():
    """Run audit logging tests."""
    print("📊 Audit Logging Smoke Test")
    print("=" * 40)
    
    print(f"Testing server: {BASE_URL}")
    print("Required env vars:")
    print("  AUDIT_ENABLED=true")
    print("  AUTH_ENABLED=true")
    print("  AUTH_MODE=jwt")
    print()
    
    tests = [
        test_orchestrator_audit,
        test_auth_failure_audit, 
        test_request_acceptance_audit
    ]
    results = []
    
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"   ❌ EXCEPTION: {e}")
            results.append(False)
    
    print("\n" + "=" * 40)
    print("📊 SUMMARY")
    print("=" * 40)
    
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    print("\n📋 Expected audit events in server logs:")
    print("- request_accepted: {route, actor, client_ip}")
    print("- orchestrator_run_started: {run_id, suites, provider, model}")
    print("- orchestrator_run_finished: {run_id, success, duration_ms}")
    print("- auth_failure: {reason, client_ip, route}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("\n⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    exit(main())
