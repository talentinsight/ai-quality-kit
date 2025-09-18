"""Tests for Schema, Latency, and Cost gates in Guardrails."""

import pytest
import json
import time
from unittest.mock import Mock, AsyncMock, patch

from apps.server.guardrails.providers.schema_guard import SchemaGuardProvider
from apps.server.guardrails.providers.performance_metrics import PerformanceMetricsProvider, RateCostLimitsProvider
from apps.server.guardrails.interfaces import SignalResult, SignalLabel, GuardrailCategory
from apps.server.guardrails.aggregator import GuardrailsAggregator, DEFAULT_THRESHOLDS


class TestSchemaGuard:
    """Test Schema Guard provider functionality."""

    @pytest.fixture
    def schema_provider(self):
        """Create schema guard provider."""
        return SchemaGuardProvider()

    @pytest.mark.asyncio
    async def test_schema_guard_valid_json(self, schema_provider):
        """Test schema guard with valid JSON output."""
        output_text = '{"name": "test_function", "parameters": {"arg1": "value1"}}'
        
        result = await schema_provider.check("test input", output_text, threshold=1.0)
        
        assert result.id == "schema.guard"
        assert result.category == GuardrailCategory.SCHEMA
        assert result.label == SignalLabel.CLEAN
        assert result.details["json_found"] is True
        assert "name" in result.details["json_keys"]

    @pytest.mark.asyncio
    async def test_schema_guard_no_json_strict(self, schema_provider):
        """Test schema guard with no JSON when strict validation required."""
        output_text = "This is just plain text with no JSON"
        
        result = await schema_provider.check("test input", output_text, threshold=1.0)
        
        assert result.id == "schema.guard"
        assert result.label == SignalLabel.VIOLATION
        assert result.score == 1.0
        assert result.details["no_json_found"] is True
        assert result.details["expected_json"] is True

    @pytest.mark.asyncio
    async def test_schema_guard_no_json_lenient(self, schema_provider):
        """Test schema guard with no JSON when lenient validation."""
        output_text = "This is just plain text with no JSON"
        
        result = await schema_provider.check("test input", output_text, threshold=0.5)
        
        assert result.id == "schema.guard"
        assert result.label == SignalLabel.HIT
        assert result.score == 0.3
        assert result.details["no_json_found"] is True
        assert result.details["expected_json"] is False

    @pytest.mark.asyncio
    async def test_schema_guard_with_schema_valid(self, schema_provider):
        """Test schema guard with valid schema validation."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "parameters": {"type": "object"}
            },
            "required": ["name"]
        }
        
        output_text = '{"name": "test_function", "parameters": {"arg1": "value1"}}'
        
        result = await schema_provider.check("test input", output_text, schema=schema, threshold=1.0)
        
        assert result.label == SignalLabel.CLEAN
        assert result.score == 0.0
        assert result.details["validation"]["valid"] is True

    @pytest.mark.asyncio
    async def test_schema_guard_with_schema_invalid(self, schema_provider):
        """Test schema guard with invalid schema validation."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "parameters": {"type": "object"}
            },
            "required": ["name", "required_field"]
        }
        
        output_text = '{"name": "test_function", "parameters": {"arg1": "value1"}}'
        
        result = await schema_provider.check("test input", output_text, schema=schema, threshold=1.0)
        
        assert result.label == SignalLabel.VIOLATION
        assert result.score == 1.0
        assert result.details["validation"]["valid"] is False

    @pytest.mark.asyncio
    async def test_schema_guard_json_extraction(self, schema_provider):
        """Test JSON extraction from various formats."""
        # JSON in code block
        output_text = '```json\n{"name": "test"}\n```'
        result = await schema_provider.check("test input", output_text, threshold=0.5)
        assert result.details["json_found"] is True
        
        # JSON in plain code block
        output_text = '```\n{"name": "test"}\n```'
        result = await schema_provider.check("test input", output_text, threshold=0.5)
        assert result.details["json_found"] is True
        
        # Direct JSON
        output_text = '{"name": "test"}'
        result = await schema_provider.check("test input", output_text, threshold=0.5)
        assert result.details["json_found"] is True

    def test_schema_guard_dependencies(self, schema_provider):
        """Test schema guard dependency checking."""
        deps = schema_provider.check_dependencies()
        # Should check for jsonschema
        assert isinstance(deps, list)

    def test_schema_guard_version(self, schema_provider):
        """Test schema guard version reporting."""
        version = schema_provider.version
        assert version is not None


class TestPerformanceMetrics:
    """Test Performance Metrics provider functionality."""

    @pytest.fixture
    def perf_provider(self):
        """Create performance metrics provider."""
        return PerformanceMetricsProvider()

    @pytest.mark.asyncio
    async def test_latency_gate_within_threshold(self, perf_provider):
        """Test latency gate when within threshold."""
        metrics = {
            "latency_ms": 1000,
            "p95_latency_ms": 1500,
            "cost_per_test": 0.005,
            "latency_p95_ms": 3000,  # Threshold
            "cost_per_test": 0.01    # Threshold
        }
        
        result = await perf_provider.check("test input", "test output", metrics=metrics)
        
        assert result.id == "performance.metrics"
        assert result.category == GuardrailCategory.LATENCY
        assert result.label == SignalLabel.CLEAN
        assert result.score == 0.0
        assert result.details["violations"]["latency"] is False
        assert result.details["violations"]["cost"] is False

    @pytest.mark.asyncio
    async def test_latency_gate_exceeds_threshold(self, perf_provider):
        """Test latency gate when exceeding threshold."""
        metrics = {
            "latency_ms": 5000,
            "p95_latency_ms": 5000,
            "cost_per_test": 0.005,
            "latency_p95_ms": 3000,  # Threshold
            "cost_per_test": 0.01    # Threshold
        }
        
        result = await perf_provider.check("test input", "test output", metrics=metrics)
        
        assert result.label == SignalLabel.VIOLATION
        assert result.score == 1.0
        assert result.details["violations"]["latency"] is True
        assert result.details["violations"]["cost"] is False
        assert "latency_p95_exceeded" in result.details["violation_details"]

    @pytest.mark.asyncio
    async def test_cost_gate_exceeds_threshold(self, perf_provider):
        """Test cost gate when exceeding threshold."""
        metrics = {
            "latency_ms": 1000,
            "p95_latency_ms": 1500,
            "cost_per_test": 0.05,   # Exceeds threshold
            "latency_p95_ms": 3000,  # Threshold
            "cost_per_test_threshold": 0.01    # Threshold
        }
        
        result = await perf_provider.check("test input", "test output", metrics=metrics)
        
        assert result.label == SignalLabel.VIOLATION
        assert result.score == 1.0
        assert result.details["violations"]["latency"] is False
        assert result.details["violations"]["cost"] is True
        assert "cost_per_test_exceeded" in result.details["violation_details"]

    @pytest.mark.asyncio
    async def test_both_gates_exceed_threshold(self, perf_provider):
        """Test when both latency and cost exceed thresholds."""
        metrics = {
            "latency_ms": 5000,
            "p95_latency_ms": 5000,
            "cost_per_test": 0.05,
            "latency_p95_ms": 3000,
            "cost_per_test_threshold": 0.01
        }
        
        result = await perf_provider.check("test input", "test output", metrics=metrics)
        
        assert result.label == SignalLabel.VIOLATION
        assert result.score == 1.0
        assert result.details["violations"]["latency"] is True
        assert result.details["violations"]["cost"] is True
        assert len(result.details["violation_details"]) == 2

    @pytest.mark.asyncio
    async def test_performance_no_metrics(self, perf_provider):
        """Test performance provider with no metrics."""
        result = await perf_provider.check("test input", "test output", metrics=None)
        
        assert result.label == SignalLabel.CLEAN
        assert result.details["no_metrics"] is True

    def test_performance_dependencies(self, perf_provider):
        """Test performance provider dependencies."""
        deps = perf_provider.check_dependencies()
        assert deps == []  # No external dependencies

    def test_performance_version(self, perf_provider):
        """Test performance provider version."""
        version = perf_provider.version
        assert version == "1.0.0"


class TestRateCostLimits:
    """Test Rate and Cost Limits provider."""

    @pytest.fixture
    def rate_provider(self):
        """Create rate cost limits provider."""
        return RateCostLimitsProvider()

    @pytest.mark.asyncio
    async def test_rate_limits_within_threshold(self, rate_provider):
        """Test rate limits when within thresholds."""
        metrics = {
            "requests_per_minute": 30,
            "cost_per_minute": 5.0,
            "tokens_per_minute": 50000,
            "rps_limit": 60,
            "cost_limit_per_minute": 10.0,
            "token_limit_per_minute": 100000
        }
        
        result = await rate_provider.check("test input", "test output", metrics=metrics)
        
        assert result.label == SignalLabel.CLEAN
        assert result.score < 0.7

    @pytest.mark.asyncio
    async def test_rate_limits_exceed_threshold(self, rate_provider):
        """Test rate limits when exceeding thresholds."""
        metrics = {
            "requests_per_minute": 70,  # Exceeds 60 RPM limit
            "cost_per_minute": 5.0,
            "tokens_per_minute": 50000,
            "rps_limit": 60,
            "cost_limit_per_minute": 10.0,
            "token_limit_per_minute": 100000
        }
        
        result = await rate_provider.check("test input", "test output", metrics=metrics)
        
        assert result.score > 0.9
        assert result.label == SignalLabel.VIOLATION


class TestGuardrailsAggregatorIntegration:
    """Test integration of schema, latency, and cost gates with aggregator."""

    @pytest.mark.asyncio
    async def test_aggregator_performance_metrics_generation(self):
        """Test that aggregator generates performance metrics."""
        from apps.server.guardrails.interfaces import GuardrailsConfig, GuardrailMode
        
        config = GuardrailsConfig(
            mode=GuardrailMode.ADVISORY,
            thresholds={"latency_p95_ms": 3000, "cost_per_test": 0.01},
            rules=[]
        )
        
        aggregator = GuardrailsAggregator(config, None)
        
        # Test performance metrics generation
        metrics = aggregator._get_performance_metrics("test input", "test output")
        
        assert "latency_ms" in metrics
        assert "p95_latency_ms" in metrics
        assert "cost_per_test" in metrics
        assert "token_count" in metrics
        assert metrics["latency_p95_ms"] == 3000  # Threshold
        assert metrics["cost_per_test_threshold"] == 0.01  # Threshold

    def test_default_thresholds_updated(self):
        """Test that default thresholds include new gates."""
        assert DEFAULT_THRESHOLDS["schema"] == 1.0
        assert DEFAULT_THRESHOLDS["latency_p95_ms"] == 3000
        assert DEFAULT_THRESHOLDS["cost_per_test"] == 0.01

    @pytest.mark.asyncio
    async def test_schema_provider_in_aggregator(self):
        """Test schema provider integration with aggregator."""
        from apps.server.guardrails.interfaces import GuardrailsConfig, GuardrailRule, GuardrailMode
        
        config = GuardrailsConfig(
            mode=GuardrailMode.ADVISORY,
            thresholds={"schema": 1.0},
            rules=[
                GuardrailRule(
                    id="schema.guard",
                    category="schema",
                    enabled=True,
                    threshold=1.0,
                    provider_id="schema.guard",
                    mode="advisory",
                    applicability="requiresTools"
                )
            ]
        )
        
        # Mock SUT adapter
        mock_sut = Mock()
        mock_sut.ask = AsyncMock(return_value='{"name": "test"}')
        
        aggregator = GuardrailsAggregator(config, mock_sut)
        
        # Mock the schema provider
        with patch('apps.server.guardrails.registry.registry.get_provider') as mock_get_provider:
            mock_provider_class = Mock()
            mock_provider = Mock()
            mock_provider.check = AsyncMock(return_value=SignalResult(
                id="schema.guard",
                category=GuardrailCategory.SCHEMA,
                score=0.0,
                label=SignalLabel.CLEAN,
                confidence=0.9,
                details={"json_found": True, "threshold": 1.0}
            ))
            mock_provider_class.return_value = mock_provider
            mock_get_provider.return_value = mock_provider_class
            
            result = await aggregator.run_preflight("Test JSON output")
            
            assert result.pass_ is True
            # Verify schema provider was called with correct threshold
            mock_provider.check.assert_called_once()
            call_args = mock_provider.check.call_args
            assert call_args.kwargs.get('threshold') == 1.0


class TestDeduplicationIntegration:
    """Test that schema, latency, and cost signals are included in fingerprints."""

    def test_schema_signal_fingerprint(self):
        """Test that schema signals get proper fingerprints for deduplication."""
        from apps.orchestrator.deduplication import CrossSuiteDeduplicationService
        
        dedup_service = CrossSuiteDeduplicationService("test_run")
        
        # Create a mock schema signal
        signal = SignalResult(
            id="schema.guard",
            category=GuardrailCategory.SCHEMA,
            score=0.0,
            label=SignalLabel.CLEAN,
            confidence=0.9,
            details={"json_found": True, "threshold": 1.0}
        )
        
        # Store the signal
        dedup_service.store_preflight_signal(signal, "gpt-4", "test_hash")
        
        # Verify it can be retrieved
        retrieved = dedup_service.check_signal_reusable(
            provider_id="schema.guard",
            metric_id="schema",
            stage="preflight",
            model="gpt-4",
            rules_hash="test_hash"
        )
        
        assert retrieved is not None
        assert retrieved.id == "schema.guard"

    def test_performance_signal_fingerprint(self):
        """Test that performance signals get proper fingerprints for deduplication."""
        from apps.orchestrator.deduplication import CrossSuiteDeduplicationService
        
        dedup_service = CrossSuiteDeduplicationService("test_run")
        
        # Create a mock performance signal
        signal = SignalResult(
            id="performance.metrics",
            category=GuardrailCategory.LATENCY,
            score=0.0,
            label=SignalLabel.CLEAN,
            confidence=0.9,
            details={"latency_ms": 1000, "cost_per_test": 0.005}
        )
        
        # Store the signal
        dedup_service.store_preflight_signal(signal, "gpt-4", "test_hash")
        
        # Verify it can be retrieved
        retrieved = dedup_service.check_signal_reusable(
            provider_id="performance.metrics",
            metric_id="latency",
            stage="preflight",
            model="gpt-4",
            rules_hash="test_hash"
        )
        
        assert retrieved is not None
        assert retrieved.id == "performance.metrics"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
