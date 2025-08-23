"""
Integration tests for JWT validation and audit logging.
"""
import pytest
import os
import jwt
from unittest.mock import patch
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone

from apps.security.auth import _validate_jwt_token
from apps.audit.logger import audit


class TestJWTValidation:
    """Test enhanced JWT validation."""
    
    @patch.dict('os.environ', {
        'JWT_SECRET': 'test-secret-key',
        'JWT_ISSUER': 'https://test-issuer.com',
        'JWT_AUDIENCE': 'https://test-api.com'
    })
    def test_valid_jwt_accepted(self):
        """Test that valid JWT is accepted."""
        payload = {
            "sub": "user123",
            "iss": "https://test-issuer.com",
            "aud": "https://test-api.com",
            "roles": ["user"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "nbf": datetime.now(timezone.utc)
        }
        
        token = jwt.encode(payload, "test-secret-key", algorithm="HS256")
        principal = _validate_jwt_token(token)
        
        assert principal.role == "user"
        assert "iss" in principal.claims
        assert "aud" in principal.claims
    
    @patch.dict('os.environ', {
        'JWT_SECRET': 'test-secret-key',
        'JWT_ISSUER': 'https://test-issuer.com',
        'JWT_AUDIENCE': 'https://test-api.com'
    })
    def test_wrong_audience_rejected(self):
        """Test that JWT with wrong audience is rejected."""
        payload = {
            "sub": "user123",
            "iss": "https://test-issuer.com",
            "aud": "https://wrong-api.com",  # Wrong audience
            "roles": ["user"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc)
        }
        
        token = jwt.encode(payload, "test-secret-key", algorithm="HS256")
        
        with pytest.raises(HTTPException) as exc_info:
            _validate_jwt_token(token)
        
        assert exc_info.value.status_code == 401
        error_detail = exc_info.value.detail
        assert isinstance(error_detail, dict)
        assert error_detail.get("error") == "invalid_audience"
    
    @patch.dict('os.environ', {
        'JWT_SECRET': 'test-secret-key',
        'JWT_ISSUER': 'https://test-issuer.com',
        'JWT_AUDIENCE': 'https://test-api.com'
    })
    def test_no_roles_rejected(self):
        """Test that JWT without roles is rejected."""
        payload = {
            "sub": "user123",
            "iss": "https://test-issuer.com",
            "aud": "https://test-api.com",
            # No roles field
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc)
        }
        
        token = jwt.encode(payload, "test-secret-key", algorithm="HS256")
        
        with pytest.raises(HTTPException) as exc_info:
            _validate_jwt_token(token)
        
        assert exc_info.value.status_code == 401
        error_detail = exc_info.value.detail
        assert isinstance(error_detail, dict)
        assert error_detail.get("error") == "insufficient_permissions"


class TestAuditLogging:
    """Test core audit logging functionality."""
    
    def test_audit_function_callable(self):
        """Test that audit function can be called without error."""
        # This test just ensures the audit function works
        try:
            audit("test_event", user_id="test_user", action="test_action")
            # If we get here without exception, audit logging works
            assert True
        except Exception as e:
            pytest.fail(f"Audit logging failed: {e}")
    
    def test_audit_with_sensitive_data(self):
        """Test that audit function handles sensitive data."""
        try:
            audit("data_processing", 
                  user_id="user123",
                  answer="This might be sensitive",  # Should be redacted
                  operation="classify")
            assert True
        except Exception as e:
            pytest.fail(f"Audit logging with sensitive data failed: {e}")


class TestEnvironmentConfiguration:
    """Test environment variable configuration."""
    
    def test_missing_issuer_rejected(self):
        """Test that missing JWT_ISSUER is rejected."""
        with patch.dict('os.environ', {
            'AUTH_MODE': 'jwt',
            'JWT_SECRET': 'test-secret-key',
            # JWT_ISSUER missing
            'JWT_AUDIENCE': 'https://test-api.com'
        }):
            token = jwt.encode({"sub": "test"}, "test-secret-key", algorithm="HS256")
            
            with pytest.raises(HTTPException) as exc_info:
                _validate_jwt_token(token)
            
            assert exc_info.value.status_code == 401
            error_detail = exc_info.value.detail
            assert isinstance(error_detail, dict)
            assert error_detail.get("error") == "invalid_token"
            assert error_detail.get("message") == "Token validation failed"
    
    def test_missing_audience_rejected(self):
        """Test that missing JWT_AUDIENCE is rejected."""
        with patch.dict('os.environ', {
            'AUTH_MODE': 'jwt',
            'JWT_SECRET': 'test-secret-key',
            'JWT_ISSUER': 'https://test-issuer.com',
            # JWT_AUDIENCE missing
        }):
            token = jwt.encode({"sub": "test"}, "test-secret-key", algorithm="HS256")
            
            with pytest.raises(HTTPException) as exc_info:
                _validate_jwt_token(token)
            
            assert exc_info.value.status_code == 401
            error_detail = exc_info.value.detail
            assert isinstance(error_detail, dict)
            assert error_detail.get("error") == "invalid_token"
            assert error_detail.get("message") == "Token validation failed"
