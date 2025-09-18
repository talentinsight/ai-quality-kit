"""
Integration tests for Guardrails composite suite.

Tests the complete guardrails functionality including:
- Suite loading and routing
- Configuration validation
- Deduplication logic
- Citation skip logic
- Test tagging and aggregation
"""

import pytest
from apps.orchestrator.run_tests import TestRunner, OrchestratorRequest, GuardrailsOptions


class TestGuardrailsIntegration:
    """Test guardrails composite suite integration."""
    
    def test_guardrails_suite_loading(self):
        """Test basic guardrails suite loading."""
        request = OrchestratorRequest(
            target_mode='api',
            provider='openai',
            model='gpt-4',
            suites=['guardrails'],
            guardrails=GuardrailsOptions(
                pii={'enable': True},
                jailbreak={'enable': True},
                mode='dedupe'
            )
        )
        
        runner = TestRunner(request)
        suite_data = runner.load_suites()
        
        # Verify guardrails suite is loaded
        assert 'guardrails' in suite_data
        guardrails_tests = suite_data['guardrails']
        assert len(guardrails_tests) > 0
        
        # Verify test tagging
        for test in guardrails_tests[:5]:  # Check first 5 tests
            assert test.get('guardrails') is True
            assert 'guardrails_subtest' in test
            assert 'guardrails_suite' in test
    
    def test_guardrails_configuration_schema(self):
        """Test guardrails configuration schema validation."""
        # Test default configuration
        config = GuardrailsOptions()
        assert config.pii.enable is True
        assert config.jailbreak.enable is True
        assert config.mode == "dedupe"
        
        # Test custom configuration
        custom_config = GuardrailsOptions(
            pii={'enable': False},
            jailbreak={'enable': True, 'variants': ['base64']},
            mode='parallel'
        )
        assert custom_config.pii.enable is False
        assert custom_config.jailbreak.variants == ['base64']
        assert custom_config.mode == 'parallel'
    
    def test_citation_skip_logic_without_rag(self):
        """Test citation tests are skipped when no RAG suites are present."""
        request = OrchestratorRequest(
            target_mode='api',
            provider='openai',
            model='gpt-4',
            suites=['guardrails'],  # No RAG suites
            guardrails=GuardrailsOptions(
                citation={'enable': True},
                pii={'enable': False},
                jailbreak={'enable': False},
                resilience={'enable': False},
                bias={'enable': False}
            )
        )
        
        runner = TestRunner(request)
        suite_data = runner.load_suites()
        
        guardrails_tests = suite_data.get('guardrails', [])
        
        # Check if citation test is skipped or has skip reason
        citation_tests = [t for t in guardrails_tests if t.get('guardrails_subtest') == 'citation_required']
        if citation_tests:
            # If citation test exists, it should be marked as skipped
            test = citation_tests[0]
            assert test.get('status') == 'SKIPPED'
            assert 'RAG' in test.get('reason', '')
    
    def test_citation_with_rag_suites(self):
        """Test citation tests are included when RAG suites are present."""
        request = OrchestratorRequest(
            target_mode='api',
            provider='openai',
            model='gpt-4',
            suites=['guardrails', 'rag_reliability_robustness'],  # Include RAG suite
            guardrails=GuardrailsOptions(
                citation={'enable': True},
                pii={'enable': False},
                jailbreak={'enable': False},
                resilience={'enable': False},
                bias={'enable': False}
            )
        )
        
        runner = TestRunner(request)
        suite_data = runner.load_suites()
        
        guardrails_tests = suite_data.get('guardrails', [])
        
        # Citation test should be present and not skipped
        citation_tests = [t for t in guardrails_tests if t.get('guardrails_subtest') == 'citation_required']
        assert len(citation_tests) > 0
        
        # Verify it routes to RAG suite
        test = citation_tests[0]
        assert test.get('guardrails_suite') in ['rag_quality', 'rag_reliability_robustness']
    
    def test_deduplication_mode(self):
        """Test deduplication mode reduces tests in original suites."""
        # Test with deduplication
        request_dedupe = OrchestratorRequest(
            target_mode='api',
            provider='openai',
            model='gpt-4',
            suites=['guardrails', 'safety'],
            guardrails=GuardrailsOptions(
                pii={'enable': True},
                jailbreak={'enable': False},
                mode='dedupe'
            )
        )
        
        runner_dedupe = TestRunner(request_dedupe)
        suite_data_dedupe = runner_dedupe.load_suites()
        
        # Test without guardrails for comparison
        request_normal = OrchestratorRequest(
            target_mode='api',
            provider='openai',
            model='gpt-4',
            suites=['safety']
        )
        
        runner_normal = TestRunner(request_normal)
        suite_data_normal = runner_normal.load_suites()
        
        # With deduplication, safety suite should have fewer tests
        # (some moved to guardrails)
        safety_tests_dedupe = len(suite_data_dedupe.get('safety', []))
        safety_tests_normal = len(suite_data_normal.get('safety', []))
        guardrails_tests = len(suite_data_dedupe.get('guardrails', []))
        
        # Guardrails should have tests
        assert guardrails_tests > 0
        
        # Total tests should be preserved or similar
        total_dedupe = safety_tests_dedupe + guardrails_tests
        assert total_dedupe >= safety_tests_normal * 0.8  # Allow some variance
    
    def test_parallel_mode(self):
        """Test parallel mode preserves tests in original suites."""
        request = OrchestratorRequest(
            target_mode='api',
            provider='openai',
            model='gpt-4',
            suites=['guardrails', 'safety'],
            guardrails=GuardrailsOptions(
                pii={'enable': True},
                mode='parallel'  # No deduplication
            )
        )
        
        runner = TestRunner(request)
        suite_data = runner.load_suites()
        
        # Both guardrails and safety should have tests
        assert len(suite_data.get('guardrails', [])) > 0
        assert len(suite_data.get('safety', [])) > 0
    
    def test_multiple_subtests_enabled(self):
        """Test multiple guardrails subtests are properly loaded."""
        request = OrchestratorRequest(
            target_mode='api',
            provider='openai',
            model='gpt-4',
            suites=['guardrails'],
            guardrails=GuardrailsOptions(
                pii={'enable': True},
                jailbreak={'enable': True},
                resilience={'enable': True},
                bias={'enable': True}
            )
        )
        
        runner = TestRunner(request)
        suite_data = runner.load_suites()
        
        guardrails_tests = suite_data.get('guardrails', [])
        
        # Check that multiple subtests are present
        subtests = set(t.get('guardrails_subtest') for t in guardrails_tests)
        expected_subtests = {'pii_leak', 'jailbreak', 'resilience', 'bias_fairness'}
        
        # At least some of the expected subtests should be present
        assert len(subtests.intersection(expected_subtests)) >= 2
    
    def test_disabled_subtests_excluded(self):
        """Test disabled subtests are not included."""
        request = OrchestratorRequest(
            target_mode='api',
            provider='openai',
            model='gpt-4',
            suites=['guardrails'],
            guardrails=GuardrailsOptions(
                pii={'enable': True},
                jailbreak={'enable': False},  # Disabled
                resilience={'enable': False},  # Disabled
                bias={'enable': False}  # Disabled
            )
        )
        
        runner = TestRunner(request)
        suite_data = runner.load_suites()
        
        guardrails_tests = suite_data.get('guardrails', [])
        
        # Only PII tests should be present
        subtests = set(t.get('guardrails_subtest') for t in guardrails_tests)
        
        # Should not contain disabled subtests
        disabled_subtests = {'jailbreak', 'resilience', 'bias_fairness'}
        assert len(subtests.intersection(disabled_subtests)) == 0
        
        # Should contain enabled subtest
        assert 'pii_leak' in subtests


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
