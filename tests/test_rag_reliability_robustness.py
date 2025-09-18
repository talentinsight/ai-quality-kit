"""Tests for RAG Reliability & Robustness suite functionality."""

import pytest
from apps.orchestrator.run_tests import TestRunner, OrchestratorRequest


class TestRagReliabilityRobustness:
    """Test RAG Reliability & Robustness suite configuration and planning."""
    
    def test_default_configuration(self):
        """Test that default configuration includes required tests."""
        request = OrchestratorRequest(
            target_mode="api",
            api_base_url="http://localhost:8000",
            suites=["rag_reliability_robustness"],
            provider="mock",
            model="mock-1"
        )
        
        runner = TestRunner(request)
        plan = runner.create_test_plan()
        
        # Should have default configuration
        assert plan.suite == "rag_reliability_robustness"
        assert "faithfulness_eval" in plan.sub_suites
        assert "context_recall" in plan.sub_suites
        assert "ground_truth_eval" in plan.sub_suites
        assert "prompt_robustness" in plan.sub_suites
        
        # Required tests should be enabled by default
        assert plan.sub_suites["faithfulness_eval"].enabled is True
        assert plan.sub_suites["context_recall"].enabled is True
        
        # Optional tests should be disabled by default
        assert plan.sub_suites["ground_truth_eval"].enabled is False
        assert plan.sub_suites["prompt_robustness"].enabled is False
    
    def test_custom_configuration(self):
        """Test that custom configuration is respected."""
        request = OrchestratorRequest(
            target_mode="api",
            api_base_url="http://localhost:8000",
            suites=["rag_reliability_robustness"],
            provider="mock",
            model="mock-1",
            options={
                "rag_reliability_robustness": {
                    "faithfulness_eval": {"enabled": True},
                    "context_recall": {"enabled": True},
                    "ground_truth_eval": {"enabled": True},
                    "prompt_robustness": {"enabled": True, "prompt_source": "built_in", "include_prompts": True}
                }
            }
        )
        
        runner = TestRunner(request)
        plan = runner.create_test_plan()
        
        # All tests should be enabled
        assert plan.sub_suites["faithfulness_eval"].enabled is True
        assert plan.sub_suites["context_recall"].enabled is True
        assert plan.sub_suites["ground_truth_eval"].enabled is True
        assert plan.sub_suites["prompt_robustness"].enabled is True
        
        # Total planned should be sum of all enabled sub-suites
        expected_total = sum(
            sub_suite.planned_items 
            for sub_suite in plan.sub_suites.values() 
            if sub_suite.enabled
        )
        assert plan.total_planned == expected_total
    
    def test_partial_configuration(self):
        """Test that partial configuration works correctly."""
        request = OrchestratorRequest(
            target_mode="api",
            api_base_url="http://localhost:8000",
            suites=["rag_reliability_robustness"],
            provider="mock",
            model="mock-1",
            options={
                "rag_reliability_robustness": {
                    "faithfulness_eval": {"enabled": True},
                    "context_recall": {"enabled": False},
                    "ground_truth_eval": {"enabled": True},
                    "prompt_robustness": {"enabled": False}
                }
            }
        )
        
        runner = TestRunner(request)
        plan = runner.create_test_plan()
        
        # Only faithfulness and ground_truth should be enabled
        assert plan.sub_suites["faithfulness_eval"].enabled is True
        assert plan.sub_suites["context_recall"].enabled is False
        assert plan.sub_suites["ground_truth_eval"].enabled is True
        assert plan.sub_suites["prompt_robustness"].enabled is False
        
        # Total should only include enabled tests
        enabled_count = sum(
            sub_suite.planned_items 
            for sub_suite in plan.sub_suites.values() 
            if sub_suite.enabled
        )
        assert plan.total_planned == enabled_count
    
    def test_legacy_alias_detection(self):
        """Test that legacy rag_quality alias is detected."""
        request = OrchestratorRequest(
            target_mode="api",
            api_base_url="http://localhost:8000",
            suites=["rag_quality"],  # Legacy alias
            provider="mock",
            model="mock-1"
        )
        
        runner = TestRunner(request)
        
        # Load suites to trigger alias processing
        suite_data = runner.load_suites()
        
        # Check that the alias was processed
        assert "rag_quality" in runner.deprecated_suites
        
        # The plan should still work
        plan = runner.create_test_plan()
        assert plan.alias_used is True
        assert plan.suite == "rag_reliability_robustness"
    
    def test_load_rag_reliability_robustness_tests(self):
        """Test that the new test loader works correctly."""
        request = OrchestratorRequest(
            target_mode="api",
            api_base_url="http://localhost:8000",
            suites=["rag_reliability_robustness"],
            provider="mock",
            model="mock-1",
            options={
                "rag_reliability_robustness": {
                    "faithfulness_eval": {"enabled": True},
                    "context_recall": {"enabled": True},
                    "ground_truth_eval": {"enabled": False},
                    "prompt_robustness": {"enabled": False}
                }
            }
        )
        
        runner = TestRunner(request)
        tests = runner._load_rag_reliability_robustness_tests()
        
        # Should have tests with proper metadata
        assert len(tests) > 0
        
        # All tests should have sub_suite metadata
        for test in tests:
            assert "sub_suite" in test
            assert test["sub_suite"] in ["basic_rag", "ground_truth_eval", "prompt_robustness"]
        
        # Should have enabled_evaluations for basic_rag tests
        basic_rag_tests = [t for t in tests if t.get("sub_suite") == "basic_rag"]
        for test in basic_rag_tests:
            assert "enabled_evaluations" in test
            assert "faithfulness" in test["enabled_evaluations"]
            assert "context_recall" in test["enabled_evaluations"]


if __name__ == "__main__":
    pytest.main([__file__])
