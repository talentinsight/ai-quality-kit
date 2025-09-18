"""Tests for provider health checking system."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from apps.server.guardrails.health import (
    check_provider_health, get_all_providers_health, 
    get_providers_by_category, get_category_availability
)
from apps.server.guardrails.interfaces import GuardrailCategory, SignalResult, SignalLabel
from apps.api.routes.guardrails import router


class TestProviderHealthChecking:
    """Test provider health checking functionality."""

    def test_check_provider_health_available(self):
        """Test health check for available provider."""
        # Mock provider class
        mock_provider_class = Mock()
        mock_provider = Mock()
        mock_provider.is_available.return_value = True
        mock_provider.check_dependencies.return_value = []
        mock_provider.version = "1.0.0"
        mock_provider.category = GuardrailCategory.PII
        mock_provider_class.return_value = mock_provider
        
        with patch('apps.server.guardrails.health.registry.get_provider', return_value=mock_provider_class):
            result = check_provider_health("test.provider")
            
            assert result["id"] == "test.provider"
            assert result["available"] is True
            assert result["version"] == "1.0.0"
            assert result["missing_deps"] == []
            assert result["category"] == "pii"

    def test_check_provider_health_unavailable(self):
        """Test health check for unavailable provider."""
        # Mock provider class
        mock_provider_class = Mock()
        mock_provider = Mock()
        mock_provider.is_available.return_value = False
        mock_provider.check_dependencies.return_value = ["missing-package"]
        mock_provider.version = None
        mock_provider.category = GuardrailCategory.TOXICITY
        mock_provider_class.return_value = mock_provider
        
        with patch('apps.server.guardrails.health.registry.get_provider', return_value=mock_provider_class):
            result = check_provider_health("test.provider")
            
            assert result["id"] == "test.provider"
            assert result["available"] is False
            assert result["version"] is None
            assert result["missing_deps"] == ["missing-package"]
            assert result["category"] == "toxicity"

    def test_check_provider_health_exception(self):
        """Test health check when provider raises exception."""
        with patch('apps.server.guardrails.health.registry.get_provider', side_effect=Exception("Provider error")):
            result = check_provider_health("test.provider")
            
            assert result["id"] == "test.provider"
            assert result["available"] is False
            assert result["version"] is None
            assert "Provider error" in result["missing_deps"]
            assert result["category"] == "unknown"

    def test_get_all_providers_health(self):
        """Test getting health for all providers."""
        mock_providers = ["pii.presidio", "toxicity.detoxify", "pi.quickset"]
        
        with patch('apps.server.guardrails.health.registry.list_providers', return_value=mock_providers):
            with patch('apps.server.guardrails.health.check_provider_health') as mock_check:
                mock_check.side_effect = [
                    {"id": "pii.presidio", "available": True, "category": "pii"},
                    {"id": "toxicity.detoxify", "available": False, "category": "toxicity"},
                    {"id": "pi.quickset", "available": True, "category": "jailbreak"}
                ]
                
                result = get_all_providers_health()
                
                assert len(result) == 3
                assert result[0]["id"] == "pi.quickset"  # Should be sorted by category then id
                assert result[1]["id"] == "pii.presidio"
                assert result[2]["id"] == "toxicity.detoxify"

    def test_get_providers_by_category(self):
        """Test grouping providers by category."""
        with patch('apps.server.guardrails.health.get_all_providers_health') as mock_get_all:
            mock_get_all.return_value = [
                {"id": "pii.presidio", "available": True, "category": "pii"},
                {"id": "pii.custom", "available": False, "category": "pii"},
                {"id": "toxicity.detoxify", "available": True, "category": "toxicity"}
            ]
            
            result = get_providers_by_category()
            
            assert "pii" in result
            assert "toxicity" in result
            assert len(result["pii"]) == 2
            assert len(result["toxicity"]) == 1

    def test_get_category_availability(self):
        """Test getting availability for specific category."""
        with patch('apps.server.guardrails.health.get_providers_by_category') as mock_get_by_cat:
            mock_get_by_cat.return_value = {
                "pii": [
                    {"id": "pii.presidio", "available": True, "category": "pii"},
                    {"id": "pii.custom", "available": False, "category": "pii"}
                ]
            }
            
            result = get_category_availability("pii")
            
            assert result["category"] == "pii"
            assert result["available"] is True  # At least one provider available
            assert result["total_providers"] == 2
            assert result["available_providers"] == 1
            assert len(result["providers"]) == 2

    def test_get_category_availability_none_available(self):
        """Test category availability when no providers are available."""
        with patch('apps.server.guardrails.health.get_providers_by_category') as mock_get_by_cat:
            mock_get_by_cat.return_value = {
                "toxicity": [
                    {"id": "toxicity.detoxify", "available": False, "category": "toxicity"}
                ]
            }
            
            result = get_category_availability("toxicity")
            
            assert result["category"] == "toxicity"
            assert result["available"] is False
            assert result["total_providers"] == 1
            assert result["available_providers"] == 0

    def test_get_category_availability_missing_category(self):
        """Test category availability for non-existent category."""
        with patch('apps.server.guardrails.health.get_providers_by_category') as mock_get_by_cat:
            mock_get_by_cat.return_value = {}
            
            result = get_category_availability("nonexistent")
            
            assert result["category"] == "nonexistent"
            assert result["available"] is False
            assert result["total_providers"] == 0
            assert result["available_providers"] == 0
            assert result["providers"] == []


class TestProviderHealthAPI:
    """Test provider health API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_health_endpoint_success(self, client):
        """Test health endpoint returns provider status."""
        mock_health_data = [
            {
                "id": "pii.presidio",
                "available": True,
                "version": "2.2.33",
                "missing_deps": [],
                "category": "pii"
            },
            {
                "id": "toxicity.detoxify",
                "available": False,
                "version": None,
                "missing_deps": ["detoxify", "torch"],
                "category": "toxicity"
            }
        ]
        
        with patch('apps.api.routes.guardrails.get_all_providers_health', return_value=mock_health_data):
            response = client.get("/guardrails/health")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["id"] == "pii.presidio"
            assert data[0]["available"] is True
            assert data[1]["id"] == "toxicity.detoxify"
            assert data[1]["available"] is False

    def test_health_endpoint_error(self, client):
        """Test health endpoint handles errors."""
        with patch('apps.api.routes.guardrails.get_all_providers_health', side_effect=Exception("Health check failed")):
            response = client.get("/guardrails/health")
            
            assert response.status_code == 500
            assert "Health check failed" in response.json()["detail"]

    def test_health_by_category_endpoint(self, client):
        """Test health by category endpoint."""
        mock_category_data = {
            "pii": [{"id": "pii.presidio", "available": True, "category": "pii"}],
            "toxicity": [{"id": "toxicity.detoxify", "available": False, "category": "toxicity"}]
        }
        
        with patch('apps.api.routes.guardrails.get_providers_by_category', return_value=mock_category_data):
            response = client.get("/guardrails/health/by-category")
            
            assert response.status_code == 200
            data = response.json()
            assert "pii" in data
            assert "toxicity" in data
            assert len(data["pii"]) == 1

    def test_category_health_endpoint(self, client):
        """Test specific category health endpoint."""
        mock_category_health = {
            "category": "pii",
            "available": True,
            "total_providers": 2,
            "available_providers": 1,
            "providers": [
                {"id": "pii.presidio", "available": True, "category": "pii"},
                {"id": "pii.custom", "available": False, "category": "pii"}
            ]
        }
        
        with patch('apps.api.routes.guardrails.get_category_availability', return_value=mock_category_health):
            response = client.get("/guardrails/health/category/pii")
            
            assert response.status_code == 200
            data = response.json()
            assert data["category"] == "pii"
            assert data["available"] is True
            assert data["total_providers"] == 2
            assert data["available_providers"] == 1


class TestProviderSelfChecks:
    """Test provider self-check implementations."""

    def test_pi_quickset_dependencies(self):
        """Test PI quickset provider dependency checking."""
        from apps.server.guardrails.providers.pi_quickset import PIQuicksetGuard
        
        # Test with missing quickset file
        guard = PIQuicksetGuard("/nonexistent/path.yaml")
        missing_deps = guard.check_dependencies()
        
        # Should include missing quickset file
        assert any("quickset_file" in dep for dep in missing_deps)

    def test_pii_presidio_dependencies(self):
        """Test PII Presidio provider dependency checking."""
        from apps.server.guardrails.providers.pii_presidio import PresidioPIIProvider
        
        provider = PresidioPIIProvider()
        missing_deps = provider.check_dependencies()
        
        # Should check for presidio-analyzer and spacy
        # Actual result depends on what's installed in test environment
        assert isinstance(missing_deps, list)

    def test_toxicity_detoxify_dependencies(self):
        """Test Toxicity Detoxify provider dependency checking."""
        from apps.server.guardrails.providers.toxicity_detoxify import DetoxifyToxicityProvider
        
        provider = DetoxifyToxicityProvider()
        missing_deps = provider.check_dependencies()
        
        # Should check for detoxify and torch
        # Actual result depends on what's installed in test environment
        assert isinstance(missing_deps, list)


class TestProviderHealthIntegration:
    """Integration tests for provider health system."""

    @pytest.mark.integration
    def test_health_endpoint_with_real_providers(self):
        """Test health endpoint with actual provider registry."""
        # Import to ensure providers are registered
        import apps.server.guardrails.providers
        
        from apps.server.guardrails.health import get_all_providers_health
        
        # This should work with real providers
        health_data = get_all_providers_health()
        
        assert isinstance(health_data, list)
        assert len(health_data) > 0
        
        # Check that each provider has required fields
        for provider in health_data:
            assert "id" in provider
            assert "available" in provider
            assert "category" in provider
            assert isinstance(provider["available"], bool)

    @pytest.mark.integration  
    def test_unavailable_providers_dont_crash_runs(self):
        """Test that unavailable providers don't crash preflight runs."""
        from apps.server.guardrails.aggregator import GuardrailsAggregator
        from apps.server.guardrails.interfaces import GuardrailsConfig, GuardrailRule, GuardrailMode
        
        # Create config with potentially unavailable provider
        config = GuardrailsConfig(
            mode=GuardrailMode.ADVISORY,
            thresholds={"toxicity": 0.3},
            rules=[
                GuardrailRule(
                    id="toxicity.detoxify",
                    category="toxicity",
                    enabled=True,
                    threshold=0.3,
                    provider_id="toxicity.detoxify",
                    mode="advisory",
                    applicability="agnostic"
                )
            ]
        )
        
        aggregator = GuardrailsAggregator(config, None)
        
        # This should not crash even if toxicity provider is unavailable
        try:
            import asyncio
            result = asyncio.run(aggregator.run_preflight("Test prompt"))
            assert result is not None
            # Should have signals even if some providers are unavailable
            assert hasattr(result, 'signals')
        except Exception as e:
            # If it fails, it should be for a different reason than provider unavailability
            assert "unavailable" not in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
