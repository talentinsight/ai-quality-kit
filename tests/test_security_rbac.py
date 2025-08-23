"""Tests for security and RBAC functionality."""

import pytest
import os
from unittest.mock import patch, MagicMock
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
