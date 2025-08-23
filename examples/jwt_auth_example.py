#!/usr/bin/env python3
"""
Example demonstrating JWT authentication with AI Quality Kit.

This script shows how to:
1. Generate a JWT token
2. Make API calls with JWT authentication
3. Handle different authentication scenarios
"""

import jwt
import requests
import json
from datetime import datetime, timedelta, timezone

# Configuration
API_BASE_URL = "http://localhost:8000"
JWT_SECRET = "your-secret-key-256-bits-minimum"  # Use a strong secret in production
JWT_ISSUER = "ai-quality-kit-example"
JWT_AUDIENCE = "api-client"


def generate_jwt_token(user_id: str, roles: list, expires_in_hours: int = 1) -> str:
    """Generate a JWT token with the specified roles."""
    payload = {
        "sub": user_id,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "exp": datetime.now(timezone.utc) + timedelta(hours=expires_in_hours),
        "iat": datetime.now(timezone.utc),
        "roles": roles
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return token


def make_api_request(endpoint: str, token: str, method: str = "GET", data: dict | None = None) -> dict:
    """Make an API request with JWT authentication."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    url = f"{API_BASE_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error {response.status_code}: {response.text}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
        raise


def main():
    """Demonstrate JWT authentication scenarios."""
    
    print("=== AI Quality Kit JWT Authentication Demo ===\n")
    
    # Scenario 1: Admin user with full access
    print("1. Admin User Authentication")
    admin_token = generate_jwt_token("admin-user", ["admin"])
    print(f"Generated admin token: {admin_token[:50]}...")
    
    try:
        # Test orchestrator endpoint (requires admin role)
        response = make_api_request(
            "/orchestrator/run_tests",
            admin_token,
            "POST",
            {
                "target_mode": "api",
                "suites": ["rag_quality"],
                "options": {
                    "provider": "mock",
                    "model": "mock-1"
                }
            }
        )
        print(f"✅ Admin access successful: Run ID {response.get('run_id', 'N/A')}")
    except Exception as e:
        print(f"❌ Admin access failed: {e}")
    
    print()
    
    # Scenario 2: Regular user with limited access
    print("2. Regular User Authentication")
    user_token = generate_jwt_token("regular-user", ["user"])
    print(f"Generated user token: {user_token[:50]}...")
    
    try:
        # Test ask endpoint (requires user or admin role)
        response = make_api_request(
            "/ask",
            user_token,
            "POST",
            {
                "query": "What is AI Quality Kit?",
                "provider": "mock"
            }
        )
        print(f"✅ User access successful: {response.get('answer', 'No answer')[:100]}...")
    except Exception as e:
        print(f"❌ User access failed: {e}")
    
    print()
    
    # Scenario 3: Viewer with read-only access
    print("3. Viewer Authentication (Read-only)")
    viewer_token = generate_jwt_token("viewer-user", ["viewer"])
    print(f"Generated viewer token: {viewer_token[:50]}...")
    
    try:
        # This should fail - viewer trying to access admin endpoint
        response = make_api_request(
            "/orchestrator/run_tests",
            viewer_token,
            "POST",
            {
                "target_mode": "api",
                "suites": ["rag_quality"],
                "options": {"provider": "mock"}
            }
        )
        print(f"❌ Viewer should not have access to orchestrator")
    except Exception as e:
        print(f"✅ Viewer access correctly denied: {e}")
    
    print()
    
    # Scenario 4: Expired token
    print("4. Expired Token Test")
    expired_token = generate_jwt_token("test-user", ["user"], expires_in_hours=-1)  # Already expired
    print(f"Generated expired token: {expired_token[:50]}...")
    
    try:
        response = make_api_request("/ask", expired_token, "POST", {"query": "test"})
        print(f"❌ Expired token should not work")
    except Exception as e:
        print(f"✅ Expired token correctly rejected: {e}")
    
    print()
    
    # Scenario 5: Test data upload (if available)
    print("5. Test Data Upload (User with testdata access)")
    try:
        response = make_api_request(
            "/testdata/paste",
            user_token,
            "POST",
            {
                "qaset": '{"qid": "test1", "question": "What is 2+2?", "expected_answer": "4"}'
            }
        )
        print(f"✅ Test data upload successful: {response.get('testdata_id', 'N/A')}")
    except Exception as e:
        print(f"❌ Test data upload failed: {e}")
    
    print("\n=== Demo Complete ===")
    print("\nTo enable JWT authentication on the server:")
    print("1. Set AUTH_ENABLED=true")
    print("2. Set AUTH_MODE=jwt")
    print("3. Set JWT_SECRET='your-secret-key-256-bits-minimum'")
    print("4. Configure RBAC_ALLOWED_ROUTES as needed")


if __name__ == "__main__":
    main()
