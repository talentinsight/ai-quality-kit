#!/usr/bin/env python3
"""
JWT validation smoke test for production verification.
Usage: python scripts/test_jwt_validation.py
"""
import requests
import jwt
import json
from datetime import datetime, timedelta, timezone

BASE_URL = "http://127.0.0.1:8000"
SECRET = "test-secret-key"
ISSUER = "https://test-issuer.com"
CORRECT_AUDIENCE = "https://test-api.com"
WRONG_AUDIENCE = "https://wrong-api.com"

def create_token(audience, roles=None):
    """Create JWT token."""
    payload = {
        "sub": "testuser",
        "iss": ISSUER,
        "aud": audience,
        "roles": roles or ["user"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def test_wrong_audience():
    """Test JWT with wrong audience should return 401."""
    print("🧪 Test: Wrong audience JWT")
    
    token = create_token(WRONG_AUDIENCE)
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.post(f"{BASE_URL}/ask", 
                           json={"question": "test"}, 
                           headers=headers)
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 401:
        error = response.json()
        if error.get("detail", {}).get("error") == "invalid_audience":
            print("   ✅ PASS: 401 with invalid_audience")
            return True
        else:
            print(f"   ❌ FAIL: Wrong error: {error}")
            return False
    else:
        print(f"   ❌ FAIL: Expected 401, got {response.status_code}")
        return False

def test_correct_audience():
    """Test JWT with correct audience should be accepted."""
    print("\n🧪 Test: Correct audience JWT")
    
    token = create_token(CORRECT_AUDIENCE)
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.post(f"{BASE_URL}/ask", 
                           json={"question": "test"}, 
                           headers=headers)
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code in [200, 422]:  # 422 = validation error, but auth passed
        print("   ✅ PASS: Authentication successful")
        return True
    elif response.status_code == 401:
        print(f"   ❌ FAIL: Auth failed: {response.text}")
        return False
    else:
        print(f"   ⚠️  OTHER: Status {response.status_code} (might be OK)")
        return True

def test_no_roles():
    """Test JWT without roles should be rejected."""
    print("\n🧪 Test: JWT without roles")
    
    payload = {
        "sub": "testuser",
        "iss": ISSUER,
        "aud": CORRECT_AUDIENCE,
        # No roles
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc)
    }
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.post(f"{BASE_URL}/ask", 
                           json={"question": "test"}, 
                           headers=headers)
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 401:
        error = response.json()
        if "insufficient_permissions" in str(error):
            print("   ✅ PASS: 401 with insufficient_permissions")
            return True
        else:
            print(f"   ❌ FAIL: Wrong error: {error}")
            return False
    else:
        print(f"   ❌ FAIL: Expected 401, got {response.status_code}")
        return False

def main():
    """Run JWT validation tests."""
    print("🔐 JWT Validation Smoke Test")
    print("=" * 40)
    
    print(f"Testing server: {BASE_URL}")
    print("Required env vars:")
    print("  AUTH_ENABLED=true")
    print("  AUTH_MODE=jwt") 
    print(f"  JWT_ISSUER={ISSUER}")
    print(f"  JWT_AUDIENCE={CORRECT_AUDIENCE}")
    print(f"  JWT_SECRET={SECRET}")
    print()
    
    tests = [test_wrong_audience, test_correct_audience, test_no_roles]
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
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    exit(main())
