"""End-to-end integration tests for guardrails preflight."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI


@pytest.mark.integration
def test_guardrails_preflight_e2e():
    """Test complete guardrails preflight flow end-to-end."""
    try:
        # Import required modules
        from apps.api.routes.guardrails import router
        from apps.server.guardrails.interfaces import (
            PreflightRequest, TargetConfig, GuardrailsConfig, GuardrailRule,
            GuardrailCategory, GuardrailMode
        )
        
        # Create test app
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        # Create test request
        request_data = {
            "llmType": "plain",
            "target": {
                "mode": "api",
                "provider": "openai",
                "endpoint": "https://api.openai.com/v1",
                "headers": {"Authorization": "Bearer test-key"},
                "model": "gpt-3.5-turbo",
                "timeoutMs": 30000
            },
            "guardrails": {
                "mode": "advisory",
                "thresholds": {"pii": 0.0, "toxicity": 0.3},
                "rules": [
                    {
                        "id": "pii-check",
                        "category": "pii",
                        "enabled": True,
                        "threshold": 0.0,
                        "mode": "advisory",
                        "applicability": "agnostic"
                    }
                ]
            }
        }
        
        # Mock authentication
        with patch('apps.security.auth.require_user_or_admin') as mock_auth:
            mock_auth.return_value = Mock(user_id="test-user")
            
            # Mock providers to avoid external dependencies
            with patch('apps.server.guardrails.providers.pii_presidio.PresidioPIIProvider') as mock_pii:
                mock_pii.return_value.check = AsyncMock(return_value=Mock(
                    id="pii.presidio",
                    category=GuardrailCategory.PII,
                    score=0.0,
                    label=Mock(value="clean"),
                    confidence=1.0,
                    details={"total_hits": 0}
                ))
                
                # Mock SUT adapter to avoid external API calls
                with patch('apps.server.sut.create_sut_adapter') as mock_sut:
                    mock_adapter = Mock()
                    mock_adapter.ask = AsyncMock(return_value="Hello, how can I help you?")
                    mock_sut.return_value = mock_adapter
                    
                    # Make request
                    response = client.post("/guardrails/preflight", json=request_data)
                    
                    # Verify response
                    assert response.status_code == 200
                    data = response.json()
                    
                    # Check response structure
                    assert "pass" in data
                    assert "reasons" in data
                    assert "signals" in data
                    assert "metrics" in data
                    
                    # Check that it's a boolean pass/fail
                    assert isinstance(data["pass"], bool)
                    
                    # Check that reasons is a list of strings
                    assert isinstance(data["reasons"], list)
                    
                    # Check that signals is a list
                    assert isinstance(data["signals"], list)
                    
                    # Check that metrics contains expected fields
                    assert "tests" in data["metrics"]
                    
                    print("✅ E2E guardrails preflight test passed")
                    return True
    
    except ImportError as e:
        pytest.skip(f"Guardrails modules not available: {e}")
    except Exception as e:
        pytest.fail(f"E2E test failed: {e}")


@pytest.mark.integration
def test_guardrails_preflight_hard_gate_failure():
    """Test guardrails preflight fails in hard gate mode with violations."""
    try:
        from apps.api.routes.guardrails import router
        from apps.server.guardrails.interfaces import GuardrailCategory
        
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        request_data = {
            "llmType": "plain",
            "target": {
                "mode": "api",
                "provider": "openai",
                "endpoint": "https://api.openai.com/v1",
                "headers": {"Authorization": "Bearer test-key"},
                "model": "gpt-3.5-turbo"
            },
            "guardrails": {
                "mode": "hard_gate",  # Hard gate mode
                "thresholds": {"pii": 0.0},  # Very strict threshold
                "rules": [
                    {
                        "id": "pii-check",
                        "category": "pii",
                        "enabled": True,
                        "threshold": 0.0,
                        "mode": "hard_gate",
                        "applicability": "agnostic"
                    }
                ]
            }
        }
        
        with patch('apps.security.auth.require_user_or_admin') as mock_auth:
            mock_auth.return_value = Mock(user_id="test-user")
            
            # Mock PII provider to return a violation
            with patch('apps.server.guardrails.providers.pii_presidio.PresidioPIIProvider') as mock_pii:
                mock_pii.return_value.check = AsyncMock(return_value=Mock(
                    id="pii.presidio",
                    category=GuardrailCategory.PII,
                    score=0.8,  # High PII score
                    label=Mock(value="hit"),
                    confidence=0.9,
                    details={"total_hits": 2, "entity_types": ["EMAIL", "PHONE"]}
                ))
                
                with patch('apps.server.sut.create_sut_adapter'):
                    response = client.post("/guardrails/preflight", json=request_data)
                    
                    assert response.status_code == 200
                    data = response.json()
                    
                    # Should fail due to hard gate mode and PII violation
                    assert data["pass"] is False
                    assert any("pii" in reason.lower() for reason in data["reasons"])
                    
                    print("✅ Hard gate failure test passed")
                    return True
    
    except ImportError as e:
        pytest.skip(f"Guardrails modules not available: {e}")
    except Exception as e:
        pytest.fail(f"Hard gate test failed: {e}")


@pytest.mark.integration
def test_guardrails_preflight_provider_unavailable():
    """Test guardrails preflight handles unavailable providers gracefully."""
    try:
        from apps.api.routes.guardrails import router
        from apps.server.guardrails.interfaces import GuardrailCategory
        
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        request_data = {
            "llmType": "plain",
            "target": {
                "mode": "api",
                "provider": "openai",
                "endpoint": "https://api.openai.com/v1",
                "headers": {"Authorization": "Bearer test-key"}
            },
            "guardrails": {
                "mode": "advisory",
                "thresholds": {"pii": 0.0, "toxicity": 0.3},
                "rules": [
                    {
                        "id": "pii-check",
                        "category": "pii",
                        "enabled": True,
                        "mode": "advisory",
                        "applicability": "agnostic"
                    },
                    {
                        "id": "toxicity-check",
                        "category": "toxicity",
                        "enabled": True,
                        "mode": "advisory",
                        "applicability": "agnostic"
                    }
                ]
            }
        }
        
        with patch('apps.security.auth.require_user_or_admin') as mock_auth:
            mock_auth.return_value = Mock(user_id="test-user")
            
            # Mock providers to return unavailable status
            with patch('apps.server.guardrails.providers.pii_presidio.PresidioPIIProvider') as mock_pii, \
                 patch('apps.server.guardrails.providers.toxicity_detoxify.DetoxifyToxicityProvider') as mock_tox:
                
                mock_pii.return_value.check = AsyncMock(return_value=Mock(
                    id="pii.presidio",
                    category=GuardrailCategory.PII,
                    score=0.0,
                    label=Mock(value="unavailable"),
                    confidence=0.0,
                    details={"missing_dep": True}
                ))
                
                mock_tox.return_value.check = AsyncMock(return_value=Mock(
                    id="toxicity.detoxify",
                    category=GuardrailCategory.TOXICITY,
                    score=0.0,
                    label=Mock(value="unavailable"),
                    confidence=0.0,
                    details={"missing_dep": True}
                ))
                
                with patch('apps.server.sut.create_sut_adapter'):
                    response = client.post("/guardrails/preflight", json=request_data)
                    
                    assert response.status_code == 200
                    data = response.json()
                    
                    # Should still return 200 even with unavailable providers
                    assert "pass" in data
                    assert "signals" in data
                    assert data["metrics"]["providers_unavailable"] > 0
                    
                    print("✅ Provider unavailable test passed")
                    return True
    
    except ImportError as e:
        pytest.skip(f"Guardrails modules not available: {e}")
    except Exception as e:
        pytest.fail(f"Provider unavailable test failed: {e}")


if __name__ == "__main__":
    # Manual test runner
    print("Running guardrails E2E tests...")
    
    try:
        test_guardrails_preflight_e2e()
        test_guardrails_preflight_hard_gate_failure()
        test_guardrails_preflight_provider_unavailable()
        print("✅ All E2E tests passed!")
    except Exception as e:
        print(f"❌ E2E tests failed: {e}")
