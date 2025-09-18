"""Tests for guardrails enforcement modes and blocking behavior."""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from apps.orchestrator.run_tests import TestRunner, OrchestratorRequest, OrchestratorResult
from apps.server.guardrails.interfaces import (
    GuardrailsConfig, GuardrailRule, GuardrailMode, GuardrailCategory, 
    SignalResult, SignalLabel, PreflightResponse
)


class TestGuardrailsEnforcement:
    """Test guardrails enforcement modes and blocking behavior."""

    @pytest.fixture
    def base_request(self):
        """Base orchestrator request with guardrails enabled."""
        return OrchestratorRequest(
            target_mode="api",
            suites=["safety", "red_team"],
            provider="openai",
            model="gpt-4",
            api_base_url="https://api.openai.com/v1",
            api_bearer_token="test-token",
            respect_guardrails=True,
            guardrails_config={
                "enabled": True,
                "mode": "advisory",  # Will be overridden in tests
                "thresholds": {
                    "pii": 0.0,
                    "jailbreak": 0.15,
                    "toxicity": 0.3
                },
                "rules": [
                    {
                        "id": "pii.presidio",
                        "category": "pii",
                        "enabled": True,
                        "threshold": 0.0,
                        "provider_id": "pii.presidio",
                        "mode": "blocking",
                        "applicability": ["input", "output"]
                    },
                    {
                        "id": "jailbreak.guard",
                        "category": "jailbreak", 
                        "enabled": True,
                        "threshold": 0.15,
                        "provider_id": "jailbreak.guard",
                        "mode": "blocking",
                        "applicability": ["input", "output"]
                    },
                    {
                        "id": "toxicity.perspective",
                        "category": "toxicity",
                        "enabled": True,
                        "threshold": 0.3,
                        "provider_id": "toxicity.perspective",
                        "mode": "blocking",
                        "applicability": ["input", "output"]
                    }
                ]
            }
        )

    @pytest.fixture
    def failing_preflight_result(self):
        """Preflight result with failures in multiple categories."""
        return {
            "pass": False,
            "reasons": [
                "PII detected in test prompt",
                "Jailbreak attempt detected",
                "Toxicity threshold exceeded"
            ],
            "signals": [
                SignalResult(
                    id="pii.presidio",
                    category=GuardrailCategory.PII,
                    score=0.8,
                    label=SignalLabel.HIT,
                    confidence=0.9,
                    details={"entities": ["email", "phone"]}
                ),
                SignalResult(
                    id="jailbreak.guard",
                    category=GuardrailCategory.JAILBREAK,
                    score=0.7,
                    label=SignalLabel.HIT,
                    confidence=0.85,
                    details={"attack_type": "role_play"}
                ),
                SignalResult(
                    id="toxicity.perspective",
                    category=GuardrailCategory.TOXICITY,
                    score=0.6,
                    label=SignalLabel.HIT,
                    confidence=0.8,
                    details={"toxicity_score": 0.6}
                )
            ],
            "metrics": {
                "tests": 3,
                "duration_ms": 1500,
                "providers_run": 3,
                "providers_unavailable": 0,
                "cached_results": 0
            }
        }

    @pytest.fixture
    def passing_preflight_result(self):
        """Preflight result with all checks passing."""
        return {
            "pass": True,
            "reasons": [],
            "signals": [
                SignalResult(
                    id="pii.presidio",
                    category=GuardrailCategory.PII,
                    score=0.0,
                    label=SignalLabel.CLEAN,
                    confidence=0.95,
                    details={}
                ),
                SignalResult(
                    id="jailbreak.guard",
                    category=GuardrailCategory.JAILBREAK,
                    score=0.05,
                    label=SignalLabel.CLEAN,
                    confidence=0.9,
                    details={}
                ),
                SignalResult(
                    id="toxicity.perspective",
                    category=GuardrailCategory.TOXICITY,
                    score=0.1,
                    label=SignalLabel.CLEAN,
                    confidence=0.85,
                    details={}
                )
            ],
            "metrics": {
                "tests": 3,
                "duration_ms": 1200,
                "providers_run": 3,
                "providers_unavailable": 0,
                "cached_results": 0
            }
        }

    @pytest.fixture
    def mixed_preflight_result(self):
        """Preflight result with critical and non-critical failures."""
        return {
            "pass": False,
            "reasons": [
                "PII detected in test prompt",
                "Toxicity threshold exceeded"
            ],
            "signals": [
                # Critical failure
                SignalResult(
                    id="pii.presidio",
                    category=GuardrailCategory.PII,
                    score=0.8,
                    label=SignalLabel.HIT,
                    confidence=0.9,
                    details={"entities": ["email"]}
                ),
                # Non-critical failure
                SignalResult(
                    id="toxicity.perspective",
                    category=GuardrailCategory.TOXICITY,
                    score=0.6,
                    label=SignalLabel.HIT,
                    confidence=0.8,
                    details={"toxicity_score": 0.6}
                ),
                # Passing check
                SignalResult(
                    id="jailbreak.guard",
                    category=GuardrailCategory.JAILBREAK,
                    score=0.05,
                    label=SignalLabel.CLEAN,
                    confidence=0.9,
                    details={}
                )
            ],
            "metrics": {
                "tests": 3,
                "duration_ms": 1300,
                "providers_run": 3,
                "providers_unavailable": 0,
                "cached_results": 0
            }
        }

    @pytest.mark.asyncio
    async def test_hard_gate_mode_blocks_all_on_failure(self, base_request, failing_preflight_result):
        """Test that hard_gate mode blocks all tests when any guardrail fails."""
        # Set hard_gate mode
        base_request.guardrails_config["mode"] = "hard_gate"
        
        runner = TestRunner(base_request)
        
        # Mock the preflight call
        with patch.object(runner, '_run_guardrails_preflight', new_callable=AsyncMock) as mock_preflight:
            mock_preflight.return_value = failing_preflight_result
            
            # Mock suite loading to avoid actual test execution
            with patch.object(runner, 'load_suites') as mock_load_suites:
                mock_load_suites.return_value = {"safety": [], "red_team": []}
                
                result = await runner.run_all_tests()
                
                # Verify blocking behavior
                assert result.summary["status"] == "blocked_by_guardrails"
                assert result.summary["blocked"] is True
                assert result.summary["total_tests"] == 0
                assert result.counts["blocked"] == 2  # Both suites blocked
                
                # Verify blocking details
                blocking_info = result.summary["guardrails_blocking"]
                assert blocking_info["blocked"] is True
                assert blocking_info["mode"] == "hard_gate"
                assert set(blocking_info["blocking_categories"]) == {"pii", "jailbreak", "toxicity"}
                assert len(blocking_info["blocking_reasons"]) == 3

    @pytest.mark.asyncio
    async def test_mixed_mode_blocks_only_critical_categories(self, base_request, mixed_preflight_result):
        """Test that mixed mode blocks only when critical categories fail."""
        # Set mixed mode
        base_request.guardrails_config["mode"] = "mixed"
        
        runner = TestRunner(base_request)
        
        # Mock the preflight call
        with patch.object(runner, '_run_guardrails_preflight', new_callable=AsyncMock) as mock_preflight:
            mock_preflight.return_value = mixed_preflight_result
            
            # Mock suite loading
            with patch.object(runner, 'load_suites') as mock_load_suites:
                mock_load_suites.return_value = {"safety": [], "red_team": []}
                
                result = await runner.run_all_tests()
                
                # Verify blocking behavior (PII is critical)
                assert result.summary["status"] == "blocked_by_guardrails"
                assert result.summary["blocked"] is True
                
                # Verify blocking details
                blocking_info = result.summary["guardrails_blocking"]
                assert blocking_info["blocked"] is True
                assert blocking_info["mode"] == "mixed"
                assert blocking_info["blocking_categories"] == ["pii"]  # Only critical category
                assert blocking_info["advisory_categories"] == ["toxicity"]  # Non-critical category

    @pytest.mark.asyncio
    async def test_mixed_mode_continues_with_non_critical_failures(self, base_request):
        """Test that mixed mode continues when only non-critical categories fail."""
        # Set mixed mode
        base_request.guardrails_config["mode"] = "mixed"
        
        # Create preflight result with only non-critical failures
        non_critical_result = {
            "pass": False,
            "reasons": ["Toxicity threshold exceeded"],
            "signals": [
                SignalResult(
                    id="toxicity.perspective",
                    category=GuardrailCategory.TOXICITY,
                    score=0.6,
                    label=SignalLabel.HIT,
                    confidence=0.8,
                    details={"toxicity_score": 0.6}
                ),
                SignalResult(
                    id="pii.presidio",
                    category=GuardrailCategory.PII,
                    score=0.0,
                    label=SignalLabel.CLEAN,
                    confidence=0.95,
                    details={}
                )
            ],
            "metrics": {"tests": 2, "duration_ms": 1000}
        }
        
        runner = TestRunner(base_request)
        
        # Mock the preflight call
        with patch.object(runner, '_run_guardrails_preflight', new_callable=AsyncMock) as mock_preflight:
            mock_preflight.return_value = non_critical_result
            
            # Mock suite loading and execution
            with patch.object(runner, 'load_suites') as mock_load_suites, \
                 patch.object(runner, 'run_case', new_callable=AsyncMock) as mock_run_case:
                
                mock_load_suites.return_value = {"safety": [{"test_id": "test1"}]}
                # Create a proper mock with all required fields
                from apps.orchestrator.run_tests import DetailedRow
                mock_row = DetailedRow(
                    run_id="test_run",
                    suite="safety",
                    test_id="test1",
                    query="test query",
                    expected_answer="test expected",
                    actual_answer="test actual",
                    context=[],
                    provider="test_provider",
                    model="test_model",
                    latency_ms=100,
                    source="test",
                    perf_phase="test",
                    status="pass",
                    faithfulness=None,
                    context_recall=None,
                    safety_score=None,
                    attack_success=None,
                    reused_from_preflight=None,
                    reused_signals=None,
                    reused_categories=None,
                    timestamp="2024-01-01T00:00:00Z"
                )
                mock_run_case.return_value = mock_row
                
                result = await runner.run_all_tests()
                
                # Verify tests continue (not blocked)
                assert result.summary.get("status") != "blocked_by_guardrails"
                assert result.summary.get("blocked") is not True
                assert result.summary["execution"]["total_tests"] > 0  # Tests were executed

    @pytest.mark.asyncio
    async def test_advisory_mode_never_blocks(self, base_request, failing_preflight_result):
        """Test that advisory mode never blocks, only provides warnings."""
        # Set advisory mode
        base_request.guardrails_config["mode"] = "advisory"
        
        runner = TestRunner(base_request)
        
        # Mock the preflight call
        with patch.object(runner, '_run_guardrails_preflight', new_callable=AsyncMock) as mock_preflight:
            mock_preflight.return_value = failing_preflight_result
            
            # Mock suite loading and execution
            with patch.object(runner, 'load_suites') as mock_load_suites, \
                 patch.object(runner, 'run_case', new_callable=AsyncMock) as mock_run_case:
                
                mock_load_suites.return_value = {"safety": [{"test_id": "test1"}]}
                # Create a proper mock with all required fields
                from apps.orchestrator.run_tests import DetailedRow
                mock_row = DetailedRow(
                    run_id="test_run",
                    suite="safety",
                    test_id="test1",
                    query="test query",
                    expected_answer="test expected",
                    actual_answer="test actual",
                    context=[],
                    provider="test_provider",
                    model="test_model",
                    latency_ms=100,
                    source="test",
                    perf_phase="test",
                    status="pass",
                    faithfulness=None,
                    context_recall=None,
                    safety_score=None,
                    attack_success=None,
                    reused_from_preflight=None,
                    reused_signals=None,
                    reused_categories=None,
                    timestamp="2024-01-01T00:00:00Z"
                )
                mock_run_case.return_value = mock_row
                
                result = await runner.run_all_tests()
                
                # Verify tests continue (not blocked)
                assert result.summary.get("status") != "blocked_by_guardrails"
                assert result.summary.get("blocked") is not True
                assert result.summary["execution"]["total_tests"] > 0  # Tests were executed

    @pytest.mark.asyncio
    async def test_passing_preflight_never_blocks(self, base_request, passing_preflight_result):
        """Test that passing preflight checks never block regardless of mode."""
        for mode in ["hard_gate", "mixed", "advisory"]:
            base_request.guardrails_config["mode"] = mode
            
            runner = TestRunner(base_request)
            
            # Mock the preflight call
            with patch.object(runner, '_run_guardrails_preflight', new_callable=AsyncMock) as mock_preflight:
                mock_preflight.return_value = passing_preflight_result
                
                # Mock suite loading and execution
                with patch.object(runner, 'load_suites') as mock_load_suites, \
                     patch.object(runner, 'run_case', new_callable=AsyncMock) as mock_run_case:
                    
                    mock_load_suites.return_value = {"safety": [{"test_id": "test1"}]}
                    # Create a proper mock with all required fields
                    from apps.orchestrator.run_tests import DetailedRow
                    mock_row = DetailedRow(
                        run_id="test_run",
                        suite="safety",
                        test_id="test1",
                        query="test query",
                        expected_answer="test expected",
                        actual_answer="test actual",
                        context=[],
                        provider="test_provider",
                        model="test_model",
                        latency_ms=100,
                        source="test",
                        perf_phase="test",
                        status="pass",
                        faithfulness=None,
                        context_recall=None,
                        safety_score=None,
                        attack_success=None,
                        reused_from_preflight=None,
                        reused_signals=None,
                        reused_categories=None,
                        timestamp="2024-01-01T00:00:00Z"
                    )
                    mock_run_case.return_value = mock_row
                    
                    result = await runner.run_all_tests()
                    
                    # Verify tests continue (not blocked)
                    assert result.summary.get("status") != "blocked_by_guardrails"
                    assert result.summary.get("blocked") is not True
                    assert result.summary["execution"]["total_tests"] > 0  # Tests were executed

    def test_evaluate_guardrails_blocking_hard_gate(self, base_request, failing_preflight_result):
        """Test blocking evaluation logic for hard_gate mode."""
        base_request.guardrails_config["mode"] = "hard_gate"
        runner = TestRunner(base_request)
        
        blocking_result = runner._evaluate_guardrails_blocking(failing_preflight_result)
        
        assert blocking_result["blocked"] is True
        assert blocking_result["mode"] == "hard_gate"
        assert set(blocking_result["blocking_categories"]) == {"pii", "jailbreak", "toxicity"}
        assert len(blocking_result["blocking_reasons"]) == 3
        assert blocking_result["advisory_categories"] == []

    def test_evaluate_guardrails_blocking_mixed_critical(self, base_request, mixed_preflight_result):
        """Test blocking evaluation logic for mixed mode with critical failures."""
        base_request.guardrails_config["mode"] = "mixed"
        runner = TestRunner(base_request)
        
        blocking_result = runner._evaluate_guardrails_blocking(mixed_preflight_result)
        
        assert blocking_result["blocked"] is True
        assert blocking_result["mode"] == "mixed"
        assert blocking_result["blocking_categories"] == ["pii"]  # Critical category
        assert blocking_result["advisory_categories"] == ["toxicity"]  # Non-critical category
        assert len(blocking_result["blocking_reasons"]) == 1

    def test_evaluate_guardrails_blocking_advisory(self, base_request, failing_preflight_result):
        """Test blocking evaluation logic for advisory mode."""
        base_request.guardrails_config["mode"] = "advisory"
        runner = TestRunner(base_request)
        
        blocking_result = runner._evaluate_guardrails_blocking(failing_preflight_result)
        
        assert blocking_result["blocked"] is False
        assert blocking_result["mode"] == "advisory"
        assert blocking_result["blocking_categories"] == []
        assert set(blocking_result["advisory_categories"]) == {"pii", "jailbreak", "toxicity"}

    def test_create_blocked_result_structure(self, base_request, failing_preflight_result):
        """Test that blocked result has correct structure and payload parity."""
        base_request.guardrails_config["mode"] = "hard_gate"
        runner = TestRunner(base_request)
        
        blocking_result = runner._evaluate_guardrails_blocking(failing_preflight_result)
        result = runner._create_blocked_result(failing_preflight_result, blocking_result)
        
        # Verify result structure
        assert isinstance(result, OrchestratorResult)
        assert result.summary["status"] == "blocked_by_guardrails"
        assert result.summary["blocked"] is True
        assert result.summary["run_id"] == runner.run_id
        assert result.summary["total_tests"] == 0
        assert result.summary["passed"] == 0
        assert result.summary["failed"] == 0
        
        # Verify counts
        assert result.counts["total"] == 0
        assert result.counts["passed"] == 0
        assert result.counts["failed"] == 0
        assert result.counts["blocked"] == len(base_request.suites)
        
        # Verify artifacts contain blocking information
        assert "guardrails_blocking" in result.artifacts
        assert "preflight_result" in result.artifacts
        
        # Verify blocking info is preserved
        blocking_info = result.summary["guardrails_blocking"]
        assert blocking_info["blocked"] is True
        assert blocking_info["mode"] == "hard_gate"

    def test_idempotence_multiple_calls(self, base_request, failing_preflight_result):
        """Test that multiple calls to blocking evaluation are idempotent."""
        base_request.guardrails_config["mode"] = "mixed"
        runner = TestRunner(base_request)
        
        # Call multiple times
        result1 = runner._evaluate_guardrails_blocking(failing_preflight_result)
        result2 = runner._evaluate_guardrails_blocking(failing_preflight_result)
        result3 = runner._evaluate_guardrails_blocking(failing_preflight_result)
        
        # Results should be identical
        assert result1 == result2 == result3
        
        # Verify deterministic behavior
        assert result1["blocked"] == result2["blocked"] == result3["blocked"]
        assert result1["blocking_categories"] == result2["blocking_categories"] == result3["blocking_categories"]

    def test_critical_categories_definition(self):
        """Test that critical categories are correctly defined."""
        from apps.server.guardrails.aggregator import CRITICAL_CATEGORIES
        from apps.server.guardrails.interfaces import GuardrailCategory
        
        expected_critical = {
            GuardrailCategory.PII,
            GuardrailCategory.JAILBREAK,
            GuardrailCategory.SELF_HARM,
            GuardrailCategory.ADULT
        }
        
        assert CRITICAL_CATEGORIES == expected_critical

    @pytest.mark.asyncio
    async def test_guardrails_disabled_no_blocking(self, base_request):
        """Test that disabled guardrails never block."""
        # Disable guardrails
        base_request.guardrails_config["enabled"] = False
        
        runner = TestRunner(base_request)
        
        # Mock suite loading and execution
        with patch.object(runner, 'load_suites') as mock_load_suites, \
             patch.object(runner, 'run_case', new_callable=AsyncMock) as mock_run_case:
            
            mock_load_suites.return_value = {"safety": [{"test_id": "test1"}]}
            # Create a proper mock with all required fields
            from apps.orchestrator.run_tests import DetailedRow
            mock_row = DetailedRow(
                run_id="test_run",
                suite="safety",
                test_id="test1",
                query="test query",
                expected_answer="test expected",
                actual_answer="test actual",
                context=[],
                provider="test_provider",
                model="test_model",
                latency_ms=100,
                source="test",
                perf_phase="test",
                status="pass",
                faithfulness=None,
                context_recall=None,
                safety_score=None,
                attack_success=None,
                reused_from_preflight=None,
                reused_signals=None,
                reused_categories=None,
                timestamp="2024-01-01T00:00:00Z"
            )
            mock_run_case.return_value = mock_row
            
            result = await runner.run_all_tests()
            
            # Verify tests continue (not blocked)
            assert result.summary.get("status") != "blocked_by_guardrails"
            assert result.summary.get("blocked") is not True
            assert result.summary["execution"]["total_tests"] > 0  # Tests were executed

    @pytest.mark.asyncio
    async def test_respect_guardrails_false_no_blocking(self, base_request, failing_preflight_result):
        """Test that respect_guardrails=False bypasses blocking."""
        # Disable guardrails respect
        base_request.respect_guardrails = False
        base_request.guardrails_config["mode"] = "hard_gate"
        
        runner = TestRunner(base_request)
        
        # Mock suite loading and execution
        with patch.object(runner, 'load_suites') as mock_load_suites, \
             patch.object(runner, 'run_case', new_callable=AsyncMock) as mock_run_case:
            
            mock_load_suites.return_value = {"safety": [{"test_id": "test1"}]}
            # Create a proper mock with all required fields
            from apps.orchestrator.run_tests import DetailedRow
            mock_row = DetailedRow(
                run_id="test_run",
                suite="safety",
                test_id="test1",
                query="test query",
                expected_answer="test expected",
                actual_answer="test actual",
                context=[],
                provider="test_provider",
                model="test_model",
                latency_ms=100,
                source="test",
                perf_phase="test",
                status="pass",
                faithfulness=None,
                context_recall=None,
                safety_score=None,
                attack_success=None,
                reused_from_preflight=None,
                reused_signals=None,
                reused_categories=None,
                timestamp="2024-01-01T00:00:00Z"
            )
            mock_run_case.return_value = mock_row
            
            result = await runner.run_all_tests()
            
            # Verify tests continue (not blocked)
            assert result.summary.get("status") != "blocked_by_guardrails"
            assert result.summary.get("blocked") is not True
            assert result.summary["execution"]["total_tests"] > 0  # Tests were executed
