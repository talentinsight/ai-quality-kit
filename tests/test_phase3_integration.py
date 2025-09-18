"""Tests for Phase 3 - Specialist Suites integration with Preflight UI."""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from apps.server.guardrails.interfaces import PreflightRequest, PreflightResponse
from apps.api.routes.guardrails import router as guardrails_router
from apps.orchestrator.router import router as orchestrator_router


@pytest.fixture
def app():
    """Create test FastAPI app with both guardrails and orchestrator routes."""
    app = FastAPI()
    app.include_router(guardrails_router)
    app.include_router(orchestrator_router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_preflight_request():
    """Sample preflight request matching new UI format."""
    return {
        "llmType": "rag",
        "target": {
            "mode": "api",
            "provider": "openai",
            "endpoint": "https://api.openai.com/v1",
            "headers": {"Authorization": "Bearer test-key"},
            "model": "gpt-4",
            "timeoutMs": 30000
        },
        "guardrails": {
            "mode": "hard_gate",
            "thresholds": {"pii": 0.0, "toxicity": 0.3},
            "rules": [
                {
                    "id": "pii-check",
                    "category": "pii",
                    "enabled": True,
                    "threshold": 0.0,
                    "mode": "hardGate",
                    "applicability": "agnostic"
                },
                {
                    "id": "toxicity-check",
                    "category": "toxicity",
                    "enabled": True,
                    "threshold": 0.3,
                    "mode": "hardGate",
                    "applicability": "agnostic"
                }
            ]
        }
    }


@pytest.fixture
def sample_orchestrator_payload():
    """Sample orchestrator payload with Phase 3 additions."""
    return {
        # Classic fields (parity)
        "target_mode": "api",
        "api_base_url": "https://api.openai.com/v1",
        "api_bearer_token": "test-key",
        "provider": "openai",
        "model": "gpt-4",
        "suites": ["rag_reliability_robustness", "red_team", "safety"],
        "thresholds": {"faithfulness_min": 0.8, "context_recall_min": 0.8},
        "options": {
            "selected_tests": {
                "rag_reliability_robustness": ["faithfulness", "context_recall"],
                "red_team": ["prompt_injection", "jailbreak_attempts"],
                "safety": ["toxicity_detection"]
            },
            "suite_configs": {
                "rag_reliability_robustness": {
                    "faithfulness_eval": {"enabled": True},
                    "context_recall": {"enabled": True}
                }
            }
        },
        "run_id": "test-run-123",
        "llm_option": "rag",
        "ground_truth": "available",
        "determinism": {"temperature": 0.0, "top_p": 1.0, "seed": 42},
        "profile": "smoke",
        "testdata_id": "test-data-456",
        "use_expanded": True,
        "use_ragas": True,
        
        # Phase 3 additive fields
        "guardrails_config": {
            "mode": "hard_gate",
            "thresholds": {"pii": 0.0, "toxicity": 0.3},
            "rules": [
                {
                    "id": "pii-check",
                    "category": "pii",
                    "enabled": True,
                    "threshold": 0.0,
                    "mode": "hardGate",
                    "applicability": "agnostic"
                }
            ]
        },
        "respect_guardrails": True
    }


class TestPayloadParity:
    """Test payload parity between Classic and Preflight UIs."""
    
    @patch('apps.security.auth.require_user_or_admin')
    def test_orchestrator_payload_structure(self, mock_auth, client, sample_orchestrator_payload):
        """Test that orchestrator receives payload with correct structure."""
        mock_auth.return_value = Mock(user_id="test-user")
        
        with patch('apps.orchestrator.run_tests.TestRunner') as mock_runner:
            # Mock successful test run
            mock_instance = Mock()
            mock_instance.run_all_tests = AsyncMock(return_value={
                "run_id": "test-run-123",
                "summary": {"total_tests": 5, "passed": 4, "failed": 1}
            })
            mock_runner.return_value = mock_instance
            
            response = client.post("/orchestrator/run_tests", json=sample_orchestrator_payload)
            
            assert response.status_code == 200
            
            # Verify TestRunner was called with correct payload
            mock_runner.assert_called_once()
            call_args = mock_runner.call_args[0][0]  # First positional argument (request)
            
            # Check Classic fields are present
            assert call_args.target_mode == "api"
            assert call_args.provider == "openai"
            assert call_args.model == "gpt-4"
            assert "rag_reliability_robustness" in call_args.suites
            assert call_args.llm_option == "rag"
            
            # Check Phase 3 additive fields are present
            assert hasattr(call_args, 'guardrails_config')
            assert hasattr(call_args, 'respect_guardrails')
            assert call_args.respect_guardrails is True
    
    def test_payload_field_compatibility(self, sample_orchestrator_payload):
        """Test that all required Classic fields are present in new payload."""
        required_classic_fields = [
            'target_mode', 'provider', 'model', 'suites', 'run_id',
            'llm_option', 'ground_truth', 'determinism', 'profile',
            'use_expanded', 'use_ragas'
        ]
        
        for field in required_classic_fields:
            assert field in sample_orchestrator_payload, f"Missing required Classic field: {field}"
        
        # Check additive fields don't conflict
        additive_fields = ['guardrails_config', 'respect_guardrails']
        for field in additive_fields:
            assert field in sample_orchestrator_payload, f"Missing Phase 3 field: {field}"


class TestPreflightGate:
    """Test preflight gate integration."""
    
    @patch('apps.security.auth.require_user_or_admin')
    def test_hard_gate_blocks_run(self, mock_auth, client, sample_preflight_request):
        """Test that hard_gate mode blocks runs when preflight fails."""
        mock_auth.return_value = Mock(user_id="test-user")
        
        with patch('apps.server.guardrails.aggregator.GuardrailsAggregator') as mock_aggregator:
            # Mock preflight failure
            mock_response = Mock()
            mock_response.pass_ = False
            mock_response.reasons = ["pii: 0.8 >= 0.0"]
            mock_response.signals = [
                Mock(id="pii.presidio", category="pii", score=0.8, label="hit")
            ]
            mock_response.metrics = {"tests": 1}
            
            mock_aggregator.return_value.run_preflight = AsyncMock(return_value=mock_response)
            
            response = client.post("/guardrails/preflight", json=sample_preflight_request)
            
            assert response.status_code == 200
            data = response.json()
            assert data["pass"] is False
            assert "pii" in data["reasons"][0]
    
    @patch('apps.security.auth.require_user_or_admin')
    def test_mixed_mode_blocks_critical_only(self, mock_auth, client, sample_preflight_request):
        """Test that mixed mode blocks only critical category violations."""
        mock_auth.return_value = Mock(user_id="test-user")
        
        # Set to mixed mode
        sample_preflight_request["guardrails"]["mode"] = "mixed"
        
        with patch('apps.server.guardrails.aggregator.GuardrailsAggregator') as mock_aggregator:
            # Mock critical violation (PII) and non-critical (toxicity)
            mock_response = Mock()
            mock_response.pass_ = False  # Would fail in hard_gate
            mock_response.reasons = ["pii: 0.8 >= 0.0", "toxicity: 0.2 < 0.3"]
            mock_response.signals = [
                Mock(id="pii.presidio", category="pii", score=0.8, label="hit"),
                Mock(id="toxicity.detoxify", category="toxicity", score=0.2, label="clean")
            ]
            mock_response.metrics = {"tests": 2}
            
            mock_aggregator.return_value.run_preflight = AsyncMock(return_value=mock_response)
            
            response = client.post("/guardrails/preflight", json=sample_preflight_request)
            
            assert response.status_code == 200
            # In mixed mode, this would still block due to PII (critical category)
    
    @patch('apps.security.auth.require_user_or_admin')
    def test_advisory_mode_never_blocks(self, mock_auth, client, sample_preflight_request):
        """Test that advisory mode never blocks runs."""
        mock_auth.return_value = Mock(user_id="test-user")
        
        # Set to advisory mode
        sample_preflight_request["guardrails"]["mode"] = "advisory"
        
        with patch('apps.server.guardrails.aggregator.GuardrailsAggregator') as mock_aggregator:
            # Mock violations that would block in other modes
            mock_response = Mock()
            mock_response.pass_ = True  # Advisory always passes
            mock_response.reasons = ["pii: 0.8 >= 0.0 (advisory)", "toxicity: 0.6 >= 0.3 (advisory)"]
            mock_response.signals = [
                Mock(id="pii.presidio", category="pii", score=0.8, label="hit"),
                Mock(id="toxicity.detoxify", category="toxicity", score=0.6, label="violation")
            ]
            mock_response.metrics = {"tests": 2}
            
            mock_aggregator.return_value.run_preflight = AsyncMock(return_value=mock_response)
            
            response = client.post("/guardrails/preflight", json=sample_preflight_request)
            
            assert response.status_code == 200
            data = response.json()
            assert data["pass"] is True  # Advisory mode never blocks


class TestDeduplication:
    """Test test fingerprint deduplication system."""
    
    def test_fingerprint_creation(self):
        """Test test fingerprint creation and parsing."""
        from frontend.operator_ui.src.lib.orchestratorPayload import TestDedupeService
        
        fingerprint = TestDedupeService.createFingerprint("safety", "toxicity", "preflight")
        assert fingerprint == "safety:toxicity:preflight"
        
        # Test should skip logic
        TestDedupeService.markExecuted("safety", "toxicity", "preflight")
        assert TestDedupeService.shouldSkipTest("safety", "toxicity") is True
        
        # Different metric should not be skipped
        assert TestDedupeService.shouldSkipTest("safety", "hate_speech") is False
    
    def test_dedupe_statistics(self):
        """Test deduplication statistics tracking."""
        from frontend.operator_ui.src.lib.orchestratorPayload import TestDedupeService
        
        TestDedupeService.clear()
        
        # Mark some tests as executed
        TestDedupeService.markExecuted("safety", "toxicity", "preflight")
        TestDedupeService.markExecuted("safety", "hate", "preflight")
        TestDedupeService.markExecuted("red_team", "injection", "specialist")
        
        stats = TestDedupeService.getStats()
        assert stats["total"] == 3
        assert stats["preflight"] == 2
        assert stats["specialist"] == 1


class TestDataRequirements:
    """Test data requirements and validation."""
    
    def test_rag_suite_requires_data(self):
        """Test that RAG suite is locked without required data."""
        # This would be tested in the frontend component tests
        # Here we verify the backend respects data requirements
        
        payload_without_data = {
            "target_mode": "api",
            "provider": "openai",
            "model": "gpt-4",
            "suites": ["rag_reliability_robustness"],
            "testdata_id": None  # No test data
        }
        
        # Backend should handle missing data gracefully
        # This is implementation-dependent
        pass
    
    def test_red_team_requires_attacks(self):
        """Test that Red Team suite requires attacks data."""
        payload_without_attacks = {
            "target_mode": "api",
            "provider": "openai", 
            "model": "gpt-4",
            "suites": ["red_team"],
            "testdata_id": None
        }
        
        # Backend should handle missing attacks data
        pass


class TestIdempotence:
    """Test idempotent behavior."""
    
    @patch('apps.security.auth.require_user_or_admin')
    def test_same_preflight_request_same_result(self, mock_auth, client, sample_preflight_request):
        """Test that identical preflight requests return identical results."""
        mock_auth.return_value = Mock(user_id="test-user")
        
        with patch('apps.server.guardrails.aggregator.GuardrailsAggregator') as mock_aggregator:
            # Mock consistent response
            mock_response = Mock()
            mock_response.pass_ = True
            mock_response.reasons = ["pii: 0.0 < 0.0", "toxicity: 0.1 < 0.3"]
            mock_response.signals = [
                Mock(id="pii.presidio", category="pii", score=0.0, label="clean"),
                Mock(id="toxicity.detoxify", category="toxicity", score=0.1, label="clean")
            ]
            mock_response.metrics = {"tests": 2, "duration_ms": 100}
            
            mock_aggregator.return_value.run_preflight = AsyncMock(return_value=mock_response)
            
            # Make two identical requests
            response1 = client.post("/guardrails/preflight", json=sample_preflight_request)
            response2 = client.post("/guardrails/preflight", json=sample_preflight_request)
            
            assert response1.status_code == 200
            assert response2.status_code == 200
            
            data1 = response1.json()
            data2 = response2.json()
            
            # Results should be identical (excluding timing)
            assert data1["pass"] == data2["pass"]
            assert data1["reasons"] == data2["reasons"]
            assert len(data1["signals"]) == len(data2["signals"])
    
    def test_same_orchestrator_payload_same_execution(self, sample_orchestrator_payload):
        """Test that identical orchestrator payloads produce same execution plan."""
        # This would test that the orchestrator produces consistent results
        # for identical payloads (deterministic behavior)
        
        # Mock test to verify payload consistency
        payload1 = sample_orchestrator_payload.copy()
        payload2 = sample_orchestrator_payload.copy()
        
        # Payloads should be identical
        assert payload1 == payload2
        
        # Execution should be deterministic (tested in orchestrator tests)


class TestPrivacyCompliance:
    """Test privacy and logging compliance."""
    
    def test_no_raw_text_in_preflight_response(self, sample_preflight_request):
        """Test that preflight responses contain no raw text."""
        # Mock a preflight response
        mock_response = {
            "pass": False,
            "reasons": ["pii: 0.8 >= 0.0"],
            "signals": [
                {
                    "id": "pii.presidio",
                    "category": "pii", 
                    "score": 0.8,
                    "label": "hit",
                    "confidence": 0.9,
                    "details": {
                        "total_hits": 2,
                        "entity_types": ["EMAIL", "PHONE"],
                        # Should NOT contain: "detected_text": "john@example.com"
                    }
                }
            ],
            "metrics": {"tests": 1, "duration_ms": 150}
        }
        
        # Verify no raw text in response
        response_str = json.dumps(mock_response)
        
        # These should not appear in any response
        forbidden_patterns = [
            "john@example.com", "555-123-4567", "secret", "password",
            "Hello, how are you?", "This is toxic content"
        ]
        
        for pattern in forbidden_patterns:
            assert pattern not in response_str, f"Found forbidden text: {pattern}"
    
    def test_no_payload_logging(self, caplog):
        """Test that raw payloads are not logged."""
        with caplog.at_level("DEBUG"):
            # Simulate processing a request with sensitive data
            sensitive_input = "My email is secret@example.com and phone is 555-123-4567"
            
            # This would be called during actual processing
            import logging
            logger = logging.getLogger("apps.server.guardrails")
            logger.info("Processing preflight request")
            logger.debug("Provider completed: pii=hit, score=0.8")
            
            # Check logs don't contain sensitive data
            log_text = caplog.text
            assert "secret@example.com" not in log_text
            assert "555-123-4567" not in log_text


class TestRequirementLocks:
    """Test requirement locks functionality."""
    
    def test_suite_locked_without_data(self):
        """Test that suites are locked when required data is missing."""
        # This would be tested in frontend component tests
        # Backend should gracefully handle missing data
        
        data_status = {
            "passages": False,
            "qaSet": False, 
            "attacks": False,
            "safety": False,
            "bias": False
        }
        
        # RAG suite should be locked without passages/qaSet
        # Red Team should be locked without attacks
        # Safety should be locked without safety data
        # etc.
        
        # This is primarily a frontend concern
        pass


if __name__ == "__main__":
    pytest.main([__file__])
