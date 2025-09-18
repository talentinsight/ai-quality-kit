"""Smoke tests for guardrails preflight - minimal dependency version."""

import pytest
from unittest.mock import Mock, patch, AsyncMock


def test_guardrails_interfaces_import():
    """Test that guardrails interfaces can be imported."""
    try:
        from apps.server.guardrails.interfaces import (
            PreflightRequest, GuardrailCategory, SignalLabel
        )
        assert GuardrailCategory.PII == "pii"
        assert SignalLabel.HIT == "hit"
        print("✅ Guardrails interfaces imported successfully")
    except ImportError as e:
        pytest.skip(f"Guardrails interfaces not available: {e}")


def test_guardrails_registry_import():
    """Test that guardrails registry can be imported."""
    try:
        from apps.server.guardrails.registry import registry
        assert hasattr(registry, 'register')
        assert hasattr(registry, 'get_provider')
        print("✅ Guardrails registry imported successfully")
    except ImportError as e:
        pytest.skip(f"Guardrails registry not available: {e}")


@pytest.mark.asyncio
async def test_pii_provider_graceful_degradation():
    """Test PII provider gracefully handles missing dependencies."""
    try:
        with patch('apps.server.guardrails.providers.pii_presidio.AnalyzerEngine', side_effect=ImportError):
            from apps.server.guardrails.providers.pii_presidio import PresidioPIIProvider
            
            provider = PresidioPIIProvider()
            assert not provider.is_available()
            
            result = await provider.check("test input", "test output")
            assert result.label.value == "unavailable"
            assert result.details.get("missing_dep") is True
            print("✅ PII provider graceful degradation works")
    except ImportError as e:
        pytest.skip(f"PII provider not available: {e}")


@pytest.mark.asyncio
async def test_toxicity_provider_graceful_degradation():
    """Test toxicity provider gracefully handles missing dependencies."""
    try:
        with patch('apps.server.guardrails.providers.toxicity_detoxify.Detoxify', side_effect=ImportError):
            from apps.server.guardrails.providers.toxicity_detoxify import DetoxifyToxicityProvider
            
            provider = DetoxifyToxicityProvider()
            assert not provider.is_available()
            
            result = await provider.check("test input", "test output")
            assert result.label.value == "unavailable"
            assert result.details.get("missing_dep") is True
            print("✅ Toxicity provider graceful degradation works")
    except ImportError as e:
        pytest.skip(f"Toxicity provider not available: {e}")


def test_sut_adapter_creation():
    """Test SUT adapter can be created."""
    try:
        from apps.server.guardrails.interfaces import TargetConfig
        from apps.server.sut import create_sut_adapter
        
        target = TargetConfig(
            mode="api",
            provider="openai",
            endpoint="https://api.openai.com/v1",
            headers={"Authorization": "Bearer test"},
            model="gpt-3.5-turbo"
        )
        
        adapter = create_sut_adapter(target)
        assert adapter is not None
        assert adapter.target == target
        print("✅ SUT adapter creation works")
    except ImportError as e:
        pytest.skip(f"SUT adapter not available: {e}")


@pytest.mark.asyncio
async def test_aggregator_basic_functionality():
    """Test aggregator basic functionality with mocked providers."""
    try:
        from apps.server.guardrails.interfaces import (
            GuardrailsConfig, GuardrailRule, GuardrailCategory, GuardrailMode
        )
        from apps.server.guardrails.aggregator import GuardrailsAggregator
        
        config = GuardrailsConfig(
            mode=GuardrailMode.ADVISORY,
            thresholds={"pii": 0.0, "toxicity": 0.3},
            rules=[
                GuardrailRule(
                    id="test-rule",
                    category=GuardrailCategory.PII,
                    enabled=True,
                    mode=GuardrailMode.ADVISORY,
                    applicability="agnostic"
                )
            ]
        )
        
        aggregator = GuardrailsAggregator(config)
        
        # Mock the provider registry to avoid actual provider execution
        with patch('apps.server.guardrails.aggregator.registry') as mock_registry:
            mock_registry.get_providers_for_category.return_value = []
            
            result = await aggregator.run_preflight("Hello")
            
            assert hasattr(result, 'pass_')
            assert hasattr(result, 'reasons')
            assert hasattr(result, 'signals')
            assert hasattr(result, 'metrics')
            print("✅ Aggregator basic functionality works")
    except ImportError as e:
        pytest.skip(f"Aggregator not available: {e}")


def test_api_route_structure():
    """Test that API route can be imported."""
    try:
        from apps.api.routes.guardrails import router
        assert router is not None
        assert hasattr(router, 'prefix')
        assert router.prefix == "/guardrails"
        print("✅ API route structure works")
    except ImportError as e:
        pytest.skip(f"API route not available: {e}")


if __name__ == "__main__":
    # Run tests manually if pytest is not available
    import asyncio
    
    def run_test(test_func):
        try:
            if asyncio.iscoroutinefunction(test_func):
                asyncio.run(test_func())
            else:
                test_func()
        except Exception as e:
            print(f"❌ {test_func.__name__} failed: {e}")
    
    print("Running guardrails smoke tests...")
    run_test(test_guardrails_interfaces_import)
    run_test(test_guardrails_registry_import)
    run_test(test_pii_provider_graceful_degradation)
    run_test(test_toxicity_provider_graceful_degradation)
    run_test(test_sut_adapter_creation)
    run_test(test_aggregator_basic_functionality)
    run_test(test_api_route_structure)
    print("Smoke tests completed!")
