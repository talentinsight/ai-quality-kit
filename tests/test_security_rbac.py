"""Tests for security and RBAC functionality."""

import pytest
import os
import jwt
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, mock_open
from fastapi.testclient import TestClient


@pytest.fixture
def mock_env_auth_enabled():
    """Mock environment with auth enabled."""
    with patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_TOKENS": "admin:SECRET_ADMIN,user:SECRET_USER",
        "RBAC_ALLOWED_ROUTES": "/ask:user|admin,/orchestrator/*:user|admin"
    }):
        yield


@pytest.fixture
def mock_env_auth_disabled():
    """Mock environment with auth disabled."""
    with patch.dict(os.environ, {
        "AUTH_ENABLED": "false"
    }):
        yield


def test_auth_disabled_allows_access(mock_env_auth_disabled):
    """Test that when auth is disabled, all requests are allowed."""
    from apps.security.auth import get_principal, require_user_or_admin
    
    # get_principal should return None when auth disabled
    principal = get_principal(None)
    assert principal is None
    
    # require_user_or_admin should return None when auth disabled
    role_checker = require_user_or_admin()
    result = role_checker(None)
    assert result is None


def test_auth_enabled_requires_token(mock_env_auth_enabled):
    """Test that when auth is enabled, valid token is required."""
    from apps.security.auth import get_principal
    from fastapi import HTTPException
    
    # No credentials should raise 401
    with pytest.raises(HTTPException) as exc_info:
        get_principal(None)
    assert exc_info.value.status_code == 401
    
    # Invalid token should raise 401
    mock_credentials = MagicMock()
    mock_credentials.credentials = "INVALID_TOKEN"
    
    with pytest.raises(HTTPException) as exc_info:
        get_principal(mock_credentials)
    assert exc_info.value.status_code == 401


def test_auth_enabled_valid_token(mock_env_auth_enabled):
    """Test that valid tokens are accepted."""
    from apps.security.auth import get_principal
    
    # Valid admin token
    mock_credentials = MagicMock()
    mock_credentials.credentials = "SECRET_ADMIN"
    
    principal = get_principal(mock_credentials)
    assert principal is not None
    assert principal.role == "admin"
    assert len(principal.token_hash_prefix) == 8
    
    # Valid user token
    mock_credentials.credentials = "SECRET_USER"
    principal = get_principal(mock_credentials)
    assert principal is not None
    assert principal.role == "user"


def test_role_checking(mock_env_auth_enabled):
    """Test role-based access control."""
    from apps.security.auth import require_role, Principal
    from fastapi import HTTPException
    
    # Create mock principals
    admin_principal = Principal(role="admin", token_hash_prefix="12345678")
    user_principal = Principal(role="user", token_hash_prefix="87654321")
    
    # Admin role checker
    admin_checker = require_role("admin")
    
    # Admin should pass
    result = admin_checker(admin_principal)
    assert result == admin_principal
    
    # User should fail for admin-only endpoint
    with pytest.raises(HTTPException) as exc_info:
        admin_checker(user_principal)
    assert exc_info.value.status_code == 403
    
    # User or admin checker
    user_admin_checker = require_role("user", "admin")
    
    # Both should pass
    assert user_admin_checker(admin_principal) == admin_principal
    assert user_admin_checker(user_principal) == user_principal


def test_route_access_checking(mock_env_auth_enabled):
    """Test route-based access control."""
    from apps.security.auth import check_route_access, Principal
    
    admin_principal = Principal(role="admin", token_hash_prefix="12345678")
    user_principal = Principal(role="user", token_hash_prefix="87654321")
    
    # Both should have access to /ask
    assert check_route_access("/ask", admin_principal) is True
    assert check_route_access("/ask", user_principal) is True
    
    # Both should have access to orchestrator routes (wildcard match)
    assert check_route_access("/orchestrator/run_tests", admin_principal) is True
    assert check_route_access("/orchestrator/run_tests", user_principal) is True
    
    # Unknown route should deny access
    assert check_route_access("/unknown", admin_principal) is False
    assert check_route_access("/unknown", user_principal) is False


@pytest.mark.asyncio
async def test_orchestrator_endpoint_auth():
    """Test that orchestrator endpoints require authentication when enabled."""
    # This would require setting up a full test client with the app
    # For now, we'll test the auth dependency directly
    from apps.security.auth import require_user_or_admin
    from fastapi import HTTPException
    
    with patch.dict(os.environ, {"AUTH_ENABLED": "true", "AUTH_TOKENS": "user:SECRET_USER"}):
        role_checker = require_user_or_admin()
        
        # No principal should raise 401
        with pytest.raises(HTTPException) as exc_info:
            role_checker(None)
        assert exc_info.value.status_code == 401


def test_token_hash_prefix():
    """Test that token hash prefixes are generated correctly."""
    from apps.security.auth import _get_token_hash_prefix
    
    token = "SECRET_ADMIN"
    hash_prefix = _get_token_hash_prefix(token)
    
    assert len(hash_prefix) == 8
    assert hash_prefix.isalnum()
    
    # Same token should produce same hash
    assert _get_token_hash_prefix(token) == hash_prefix
    
    # Different token should produce different hash
    different_hash = _get_token_hash_prefix("SECRET_USER")
    assert different_hash != hash_prefix


def test_auth_token_parsing():
    """Test parsing of AUTH_TOKENS environment variable."""
    from apps.security.auth import _parse_auth_tokens
    
    with patch.dict(os.environ, {"AUTH_TOKENS": "admin:SECRET_ADMIN,user:SECRET_USER,viewer:SECRET_VIEWER"}):
        token_map = _parse_auth_tokens()
        
        assert len(token_map) == 3
        assert token_map["SECRET_ADMIN"] == "admin"
        assert token_map["SECRET_USER"] == "user"
        assert token_map["SECRET_VIEWER"] == "viewer"
    
    # Test empty/missing tokens
    with patch.dict(os.environ, {"AUTH_TOKENS": ""}):
        token_map = _parse_auth_tokens()
        assert len(token_map) == 0


def test_rbac_routes_parsing():
    """Test parsing of RBAC_ALLOWED_ROUTES environment variable."""
    from apps.security.auth import _parse_rbac_routes
    
    with patch.dict(os.environ, {
        "RBAC_ALLOWED_ROUTES": "/ask:user|admin,/orchestrator/*:admin,/reports/*:user|admin"
    }):
        route_map = _parse_rbac_routes()
        
        assert len(route_map) == 3
        assert route_map["/ask"] == {"user", "admin"}
        assert route_map["/orchestrator/*"] == {"admin"}
        assert route_map["/reports/*"] == {"user", "admin"}
    
    # Test empty routes
    with patch.dict(os.environ, {"RBAC_ALLOWED_ROUTES": ""}):
        route_map = _parse_rbac_routes()
        assert len(route_map) == 0


# JWT Authentication Tests

@pytest.fixture
def jwt_secret():
    """JWT secret for testing."""
    return "test-secret-key-for-jwt-testing"


@pytest.fixture
def mock_env_jwt_hs256(jwt_secret):
    """Mock environment with JWT HS256 authentication."""
    with patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_MODE": "jwt",
        "JWT_SECRET": jwt_secret,
        "JWT_ISSUER": "test-issuer",
        "JWT_AUDIENCE": "test-audience"
    }):
        yield


@pytest.fixture
def mock_env_jwt_rs256():
    """Mock environment with JWT RS256 authentication."""
    with patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_MODE": "jwt",
        "JWT_JWKS_URL": "https://example.com/.well-known/jwks.json",
        "JWT_ISSUER": "test-issuer",
        "JWT_AUDIENCE": "test-audience"
    }):
        yield


@pytest.fixture
def valid_jwt_token(jwt_secret):
    """Create a valid JWT token for testing."""
    payload = {
        "sub": "test-user",
        "iss": "test-issuer",
        "aud": "test-audience",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "roles": ["user"]
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def admin_jwt_token(jwt_secret):
    """Create a valid JWT token with admin role."""
    payload = {
        "sub": "test-admin",
        "iss": "test-issuer",
        "aud": "test-audience",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "roles": ["admin"]
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def expired_jwt_token(jwt_secret):
    """Create an expired JWT token."""
    payload = {
        "sub": "test-user",
        "iss": "test-issuer",
        "aud": "test-audience",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "roles": ["user"]
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def jwt_token_wrong_issuer(jwt_secret):
    """Create a JWT token with wrong issuer."""
    payload = {
        "sub": "test-user",
        "iss": "wrong-issuer",
        "aud": "test-audience",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "roles": ["user"]
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def jwt_token_scope_roles(jwt_secret):
    """Create a JWT token with roles in scope field."""
    payload = {
        "sub": "test-user",
        "iss": "test-issuer",
        "aud": "test-audience",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "scope": "user admin"
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


def test_jwt_mode_valid_token(mock_env_jwt_hs256, valid_jwt_token):
    """Test JWT mode with valid token."""
    from apps.security.auth import get_principal
    
    mock_credentials = MagicMock()
    mock_credentials.credentials = valid_jwt_token
    
    principal = get_principal(mock_credentials)
    assert principal is not None
    assert principal.role == "user"
    assert len(principal.token_hash_prefix) == 8
    assert "sub" in principal.claims
    assert principal.claims["sub"] == "test-user"


def test_jwt_mode_admin_token(mock_env_jwt_hs256, admin_jwt_token):
    """Test JWT mode with admin token."""
    from apps.security.auth import get_principal
    
    mock_credentials = MagicMock()
    mock_credentials.credentials = admin_jwt_token
    
    principal = get_principal(mock_credentials)
    assert principal is not None
    assert principal.role == "admin"
    assert principal.claims["roles"] == ["admin"]


def test_jwt_mode_expired_token(mock_env_jwt_hs256, expired_jwt_token):
    """Test JWT mode with expired token."""
    from apps.security.auth import get_principal
    from fastapi import HTTPException
    
    mock_credentials = MagicMock()
    mock_credentials.credentials = expired_jwt_token
    
    with pytest.raises(HTTPException) as exc_info:
        get_principal(mock_credentials)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_jwt_mode_wrong_issuer(mock_env_jwt_hs256, jwt_token_wrong_issuer):
    """Test JWT mode with wrong issuer."""
    from apps.security.auth import get_principal
    from fastapi import HTTPException
    
    mock_credentials = MagicMock()
    mock_credentials.credentials = jwt_token_wrong_issuer
    
    with pytest.raises(HTTPException) as exc_info:
        get_principal(mock_credentials)
    assert exc_info.value.status_code == 401
    assert "issuer" in exc_info.value.detail.lower()


def test_jwt_mode_invalid_token(mock_env_jwt_hs256):
    """Test JWT mode with invalid token."""
    from apps.security.auth import get_principal
    from fastapi import HTTPException
    
    mock_credentials = MagicMock()
    mock_credentials.credentials = "invalid.jwt.token"
    
    with pytest.raises(HTTPException) as exc_info:
        get_principal(mock_credentials)
    assert exc_info.value.status_code == 401
    assert "invalid" in exc_info.value.detail.lower()


def test_jwt_scope_roles(mock_env_jwt_hs256, jwt_token_scope_roles):
    """Test JWT with roles in scope field."""
    from apps.security.auth import get_principal
    
    mock_credentials = MagicMock()
    mock_credentials.credentials = jwt_token_scope_roles
    
    principal = get_principal(mock_credentials)
    assert principal is not None
    assert principal.role == "user"  # First role from scope


def test_jwt_no_roles_defaults_to_user(mock_env_jwt_hs256, jwt_secret):
    """Test JWT without roles defaults to user role."""
    from apps.security.auth import get_principal
    
    # Create token without roles
    payload = {
        "sub": "test-user",
        "iss": "test-issuer",
        "aud": "test-audience",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc)
    }
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    
    mock_credentials = MagicMock()
    mock_credentials.credentials = token
    
    principal = get_principal(mock_credentials)
    assert principal is not None
    assert principal.role == "user"


def test_auth_mode_invalid():
    """Test invalid AUTH_MODE."""
    from apps.security.auth import get_principal
    from fastapi import HTTPException
    
    with patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_MODE": "invalid"
    }):
        mock_credentials = MagicMock()
        mock_credentials.credentials = "some-token"
        
        with pytest.raises(HTTPException) as exc_info:
            get_principal(mock_credentials)
        assert exc_info.value.status_code == 401
        assert "authentication mode" in exc_info.value.detail.lower()


def test_token_mode_still_works():
    """Test that token mode still works unchanged."""
    from apps.security.auth import get_principal
    from fastapi import HTTPException
    
    with patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_MODE": "token",
        "AUTH_TOKENS": "admin:SECRET_ADMIN,user:SECRET_USER"
    }):
        # Valid token
        mock_credentials = MagicMock()
        mock_credentials.credentials = "SECRET_ADMIN"
        
        principal = get_principal(mock_credentials)
        assert principal is not None
        assert principal.role == "admin"
        assert len(principal.token_hash_prefix) == 8
        
        # Invalid token
        mock_credentials.credentials = "INVALID_TOKEN"
        
        with pytest.raises(HTTPException) as exc_info:
            get_principal(mock_credentials)
        assert exc_info.value.status_code == 401


def test_jwt_extract_roles_from_claims():
    """Test role extraction from JWT claims."""
    from apps.security.auth import _extract_roles_from_jwt
    
    # Test with roles array
    claims = {"roles": ["admin", "user"]}
    roles = _extract_roles_from_jwt(claims)
    assert roles == ["admin", "user"]
    
    # Test with scope string
    claims = {"scope": "admin user viewer"}
    roles = _extract_roles_from_jwt(claims)
    assert roles == ["admin", "user", "viewer"]
    
    # Test with no roles
    claims = {"sub": "test"}
    roles = _extract_roles_from_jwt(claims)
    assert roles == []
    
    # Test with invalid roles format
    claims = {"roles": "not-an-array"}
    roles = _extract_roles_from_jwt(claims)
    assert roles == []


@patch('requests.get')
def test_jwt_rs256_with_jwks(mock_get, mock_env_jwt_rs256):
    """Test JWT RS256 with JWKS URL."""
    from apps.security.auth import _fetch_jwks
    from fastapi import HTTPException
    
    # Mock JWKS response
    mock_jwks = {
        "keys": [
            {
                "kid": "test-key-id",
                "kty": "RSA",
                "use": "sig",
                "n": "fake-modulus",
                "e": "AQAB"
            }
        ]
    }
    mock_response = MagicMock()
    mock_response.json.return_value = mock_jwks
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    # Test JWKS fetching directly
    jwks = _fetch_jwks("https://example.com/.well-known/jwks.json")
    assert jwks == mock_jwks
    mock_get.assert_called_once()


@patch('requests.get')
def test_jwt_jwks_fetch_failure(mock_get, mock_env_jwt_rs256):
    """Test JWT JWKS fetch failure."""
    from apps.security.auth import get_principal
    from fastapi import HTTPException
    
    # Mock failed JWKS response
    mock_get.side_effect = Exception("Network error")
    
    token = jwt.encode({"kid": "test"}, "secret", algorithm="HS256", headers={"kid": "test"})
    
    mock_credentials = MagicMock()
    mock_credentials.credentials = token
    
    with pytest.raises(HTTPException) as exc_info:
        get_principal(mock_credentials)
    assert exc_info.value.status_code == 401


def test_jwt_missing_kid_in_header(mock_env_jwt_rs256):
    """Test JWT missing kid in header for RS256."""
    from apps.security.auth import get_principal
    from fastapi import HTTPException
    
    # Create token without kid
    token = jwt.encode({"sub": "test"}, "secret", algorithm="HS256")
    
    mock_credentials = MagicMock()
    mock_credentials.credentials = token
    
    with pytest.raises(HTTPException) as exc_info:
        get_principal(mock_credentials)
    assert exc_info.value.status_code == 401
    assert "kid" in exc_info.value.detail.lower()


def test_jwt_configuration_functions():
    """Test JWT configuration helper functions."""
    from apps.security.auth import _get_auth_mode, _get_jwt_config
    
    # Test default auth mode
    with patch.dict(os.environ, {}, clear=True):
        assert _get_auth_mode() == "token"
    
    with patch.dict(os.environ, {"AUTH_MODE": "JWT"}):
        assert _get_auth_mode() == "jwt"  # Should be lowercased
    
    # Test JWT config
    with patch.dict(os.environ, {
        "JWT_SECRET": "secret",
        "JWT_JWKS_URL": "https://example.com/jwks",
        "JWT_ISSUER": "issuer",
        "JWT_AUDIENCE": "audience"
    }):
        config = _get_jwt_config()
        assert config["secret"] == "secret"
        assert config["jwks_url"] == "https://example.com/jwks"
        assert config["issuer"] == "issuer"
        assert config["audience"] == "audience"
