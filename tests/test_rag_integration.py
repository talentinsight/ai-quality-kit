"""Integration tests for RAG Reliability & Robustness suite."""

import pytest
import json
from fastapi.testclient import TestClient
from apps.orchestrator.router import router
from fastapi import FastAPI


@pytest.fixture
def client():
    """Create test client."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestRagIntegration:
    """Integration tests for RAG suite functionality."""
    
    def test_plan_endpoint_basic(self, client):
        """Test the plan endpoint with basic configuration."""
        payload = {
            "target_mode": "api",
            "api_base_url": "http://localhost:8000",
            "suites": ["rag_reliability_robustness"],
            "provider": "mock",
            "model": "mock-1",
            "options": {
                "rag_reliability_robustness": {
                    "faithfulness_eval": {"enabled": True},
                    "context_recall": {"enabled": True},
                    "ground_truth_eval": {"enabled": False},
                    "prompt_robustness": {"enabled": False}
                }
            }
        }
        
        response = client.post("/orchestrator/run_tests?dry_run=true", json=payload)
        
        assert response.status_code == 200
        plan = response.json()
        
        # Verify plan structure
        assert "suite" in plan
        assert "sub_suites" in plan
        assert "total_planned" in plan
        assert "skips" in plan
        assert "alias_used" in plan
        
        assert plan["suite"] == "rag_reliability_robustness"
        assert "faithfulness_eval" in plan["sub_suites"]
        assert "context_recall" in plan["sub_suites"]
        assert "ground_truth_eval" in plan["sub_suites"]
        assert "prompt_robustness" in plan["sub_suites"]
    
    def test_plan_endpoint_all_enabled(self, client):
        """Test the plan endpoint with all sub-suites enabled."""
        payload = {
            "target_mode": "api",
            "api_base_url": "http://localhost:8000",
            "suites": ["rag_reliability_robustness"],
            "provider": "mock",
            "model": "mock-1",
            "options": {
                "rag_reliability_robustness": {
                    "faithfulness_eval": {"enabled": True},
                    "context_recall": {"enabled": True},
                    "ground_truth_eval": {"enabled": True},
                    "prompt_robustness": {"enabled": True, "prompt_source": "built_in", "include_prompts": True}
                }
            }
        }
        
        response = client.post("/orchestrator/run_tests?dry_run=true", json=payload)
        
        assert response.status_code == 200
        plan = response.json()
        
        # All sub-suites should be enabled
        for sub_suite_name, sub_suite in plan["sub_suites"].items():
            assert sub_suite["enabled"] is True
            assert "planned_items" in sub_suite
        
        # Total should be sum of all planned items
        expected_total = sum(
            sub_suite["planned_items"] 
            for sub_suite in plan["sub_suites"].values()
        )
        assert plan["total_planned"] == expected_total
    
    def test_plan_endpoint_legacy_alias(self, client):
        """Test the plan endpoint with legacy rag_quality alias."""
        payload = {
            "target_mode": "api",
            "api_base_url": "http://localhost:8000",
            "suites": ["rag_quality"],  # Legacy alias
            "provider": "mock",
            "model": "mock-1"
        }
        
        response = client.post("/orchestrator/run_tests?dry_run=true", json=payload)
        
        assert response.status_code == 200
        plan = response.json()
        
        # Should indicate alias was used
        assert plan["alias_used"] is True
        assert plan["suite"] == "rag_reliability_robustness"
    
    def test_plan_endpoint_no_suite_selected(self, client):
        """Test the plan endpoint when RAG suite is not selected."""
        payload = {
            "target_mode": "api",
            "api_base_url": "http://localhost:8000",
            "suites": ["red_team"],  # Different suite
            "provider": "mock",
            "model": "mock-1"
        }
        
        response = client.post("/orchestrator/run_tests?dry_run=true", json=payload)
        
        assert response.status_code == 200
        plan = response.json()
        
        # Should indicate suite not selected
        assert plan["total_planned"] == 0
        assert len(plan["skips"]) > 0
        assert any("suite not selected" in skip["reason"] for skip in plan["skips"])


if __name__ == "__main__":
    pytest.main([__file__])
