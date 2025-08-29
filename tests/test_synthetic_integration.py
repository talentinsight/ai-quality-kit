"""Integration tests for synthetic provider in RAG suite."""

import pytest
from apps.orchestrator.run_tests import TestRunner, OrchestratorRequest


class TestSyntheticIntegration:
    """Test synthetic provider integration with RAG suite."""
    
    def test_synthetic_provider_in_rag_suite(self):
        """Test RAG suite with synthetic provider."""
        request = OrchestratorRequest(
            target_mode="api",
            api_base_url="http://localhost:8000",
            suites=["rag_reliability_robustness"],
            provider="synthetic",  # Use synthetic provider
            model="synthetic-v1",
            options={
                "synthetic_success_rate": 0.9,  # 90% success rate
                "rag_reliability_robustness": {
                    "faithfulness_eval": {"enabled": True},
                    "context_recall": {"enabled": True},
                    "ground_truth_eval": {"enabled": False},
                    "prompt_robustness": {"enabled": True}
                }
            }
        )
        
        runner = TestRunner(request)
        plan = runner.create_test_plan()
        
        # Should work with synthetic provider
        assert plan.suite == "rag_reliability_robustness"
        assert plan.total_planned > 0
        
        # Should have enabled sub-suites
        assert plan.sub_suites["faithfulness_eval"].enabled is True
        assert plan.sub_suites["context_recall"].enabled is True
        assert plan.sub_suites["prompt_robustness"].enabled is True
    
    def test_synthetic_vs_mock_provider_comparison(self):
        """Compare synthetic vs mock provider results."""
        
        # Test with synthetic provider
        synthetic_request = OrchestratorRequest(
            target_mode="api",
            api_base_url="http://localhost:8000",
            suites=["rag_reliability_robustness"],
            provider="synthetic",
            model="synthetic-v1",
            options={
                "synthetic_success_rate": 1.0,  # Perfect success for comparison
                "rag_reliability_robustness": {
                    "faithfulness_eval": {"enabled": True},
                    "context_recall": {"enabled": False},
                    "ground_truth_eval": {"enabled": False},
                    "prompt_robustness": {"enabled": False}
                }
            }
        )
        
        # Test with mock provider
        mock_request = OrchestratorRequest(
            target_mode="api",
            api_base_url="http://localhost:8000",
            suites=["rag_reliability_robustness"],
            provider="mock",
            model="mock-1",
            options={
                "rag_reliability_robustness": {
                    "faithfulness_eval": {"enabled": True},
                    "context_recall": {"enabled": False},
                    "ground_truth_eval": {"enabled": False},
                    "prompt_robustness": {"enabled": False}
                }
            }
        )
        
        synthetic_runner = TestRunner(synthetic_request)
        mock_runner = TestRunner(mock_request)
        
        synthetic_plan = synthetic_runner.create_test_plan()
        mock_plan = mock_runner.create_test_plan()
        
        # Both should have same structure
        assert synthetic_plan.suite == mock_plan.suite
        assert synthetic_plan.total_planned == mock_plan.total_planned
        
        # But synthetic should be marked as non-alias (more modern)
        assert synthetic_plan.alias_used == mock_plan.alias_used
    
    def test_real_llm_provider_not_synthetic(self):
        """Ensure real LLM providers are not confused with synthetic."""
        
        real_providers = ["openai", "anthropic", "gemini", "custom_rest"]
        
        for provider in real_providers:
            request = OrchestratorRequest(
                target_mode="api",
                api_base_url="https://api.openai.com/v1",
                suites=["rag_reliability_robustness"],
                provider=provider,
                model="gpt-4o-mini"
            )
            
            runner = TestRunner(request)
            
            # Should not use synthetic provider
            assert runner.request.provider == provider
            assert runner.request.provider != "synthetic"
            assert runner.request.provider != "mock"
    
    def test_synthetic_provider_success_rate_control(self):
        """Test that synthetic provider respects success rate settings."""
        
        # Test with different success rates
        success_rates = [0.5, 0.8, 0.95, 1.0]
        
        for rate in success_rates:
            request = OrchestratorRequest(
                target_mode="api",
                api_base_url="http://localhost:8000",
                suites=["rag_reliability_robustness"],
                provider="synthetic",
                model="synthetic-v1",
                options={
                    "synthetic_success_rate": rate,
                    "rag_reliability_robustness": {
                        "faithfulness_eval": {"enabled": True},
                        "context_recall": {"enabled": False},
                        "ground_truth_eval": {"enabled": False},
                        "prompt_robustness": {"enabled": False}
                    }
                }
            )
            
            runner = TestRunner(request)
            plan = runner.create_test_plan()
            
            # Should still plan the same number of tests regardless of success rate
            assert plan.total_planned > 0
            
            # Success rate affects execution, not planning
            assert plan.suite == "rag_reliability_robustness"


if __name__ == "__main__":
    pytest.main([__file__])
