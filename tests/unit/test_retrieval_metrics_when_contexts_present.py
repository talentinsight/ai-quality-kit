"""Unit tests for retrieval metrics when contexts are present."""

import pytest
from apps.orchestrator.retrieval_metrics import (
    extract_contexts_from_response,
    compute_recall_at_k,
    compute_mrr_at_k,
    compute_ndcg_at_k,
    compute_retrieval_metrics,
    evaluate_retrieval_for_case
)


class TestContextExtraction:
    """Test context extraction from responses."""
    
    def test_extract_contexts_simple_path(self):
        """Test extraction with simple JSONPath."""
        response = {
            "contexts": ["Context 1", "Context 2", "Context 3"]
        }
        
        contexts = extract_contexts_from_response(response, "$.contexts")
        
        assert contexts == ["Context 1", "Context 2", "Context 3"]
    
    def test_extract_contexts_nested_path(self):
        """Test extraction with nested JSONPath."""
        response = {
            "data": {
                "retrieved": ["Retrieved 1", "Retrieved 2"]
            }
        }
        
        contexts = extract_contexts_from_response(response, "$.data.retrieved")
        
        assert contexts == ["Retrieved 1", "Retrieved 2"]
    
    def test_extract_contexts_missing_path(self):
        """Test extraction with missing JSONPath."""
        response = {
            "other_field": ["Some data"]
        }
        
        contexts = extract_contexts_from_response(response, "$.contexts")
        
        assert contexts == []
    
    def test_extract_contexts_invalid_jsonpath(self):
        """Test extraction with invalid JSONPath."""
        response = {
            "contexts": ["Context 1"]
        }
        
        contexts = extract_contexts_from_response(response, "$.invalid[syntax")
        
        assert contexts == []
    
    def test_extract_contexts_non_list_result(self):
        """Test extraction when JSONPath returns non-list."""
        response = {
            "context": "Single context string"
        }
        
        contexts = extract_contexts_from_response(response, "$.context")
        
        assert contexts == []


class TestRecallAtK:
    """Test Recall@K metric computation."""
    
    def test_recall_at_k_perfect_match(self):
        """Test recall with perfect match."""
        retrieved = ["Context A", "Context B", "Context C"]
        relevant = ["Context A", "Context B"]
        
        recall = compute_recall_at_k(retrieved, relevant, k=3)
        
        assert recall == 1.0  # Both relevant contexts found
    
    def test_recall_at_k_partial_match(self):
        """Test recall with partial match."""
        retrieved = ["Context A", "Context X", "Context Y"]
        relevant = ["Context A", "Context B"]
        
        recall = compute_recall_at_k(retrieved, relevant, k=3)
        
        assert recall == 0.5  # Only 1 of 2 relevant contexts found
    
    def test_recall_at_k_no_match(self):
        """Test recall with no match."""
        retrieved = ["Context X", "Context Y", "Context Z"]
        relevant = ["Context A", "Context B"]
        
        recall = compute_recall_at_k(retrieved, relevant, k=3)
        
        assert recall == 0.0
    
    def test_recall_at_k_with_k_limit(self):
        """Test recall with k limit."""
        retrieved = ["Context X", "Context A", "Context B"]  # Relevant at positions 2,3
        relevant = ["Context A", "Context B"]
        
        recall_k1 = compute_recall_at_k(retrieved, relevant, k=1)
        recall_k2 = compute_recall_at_k(retrieved, relevant, k=2)
        recall_k3 = compute_recall_at_k(retrieved, relevant, k=3)
        
        assert recall_k1 == 0.0  # No relevant in top-1
        assert recall_k2 == 0.5  # 1 relevant in top-2
        assert recall_k3 == 1.0  # Both relevant in top-3
    
    def test_recall_at_k_empty_inputs(self):
        """Test recall with empty inputs."""
        assert compute_recall_at_k([], ["Context A"], k=3) == 0.0
        assert compute_recall_at_k(["Context A"], [], k=3) == 0.0
        assert compute_recall_at_k([], [], k=3) == 0.0


class TestMRRAtK:
    """Test Mean Reciprocal Rank@K metric computation."""
    
    def test_mrr_at_k_first_position(self):
        """Test MRR when relevant context is at first position."""
        retrieved = ["Context A", "Context X", "Context Y"]
        relevant = ["Context A"]
        
        mrr = compute_mrr_at_k(retrieved, relevant, k=3)
        
        assert mrr == 1.0  # 1/1
    
    def test_mrr_at_k_second_position(self):
        """Test MRR when relevant context is at second position."""
        retrieved = ["Context X", "Context A", "Context Y"]
        relevant = ["Context A"]
        
        mrr = compute_mrr_at_k(retrieved, relevant, k=3)
        
        assert mrr == 0.5  # 1/2
    
    def test_mrr_at_k_third_position(self):
        """Test MRR when relevant context is at third position."""
        retrieved = ["Context X", "Context Y", "Context A"]
        relevant = ["Context A"]
        
        mrr = compute_mrr_at_k(retrieved, relevant, k=3)
        
        assert mrr == pytest.approx(0.333, abs=0.01)  # 1/3
    
    def test_mrr_at_k_no_match(self):
        """Test MRR with no match."""
        retrieved = ["Context X", "Context Y", "Context Z"]
        relevant = ["Context A"]
        
        mrr = compute_mrr_at_k(retrieved, relevant, k=3)
        
        assert mrr == 0.0
    
    def test_mrr_at_k_with_k_limit(self):
        """Test MRR with k limit."""
        retrieved = ["Context X", "Context Y", "Context A"]  # Relevant at position 3
        relevant = ["Context A"]
        
        mrr_k2 = compute_mrr_at_k(retrieved, relevant, k=2)
        mrr_k3 = compute_mrr_at_k(retrieved, relevant, k=3)
        
        assert mrr_k2 == 0.0  # Relevant not in top-2
        assert mrr_k3 == pytest.approx(0.333, abs=0.01)  # Relevant at position 3


class TestNDCGAtK:
    """Test Normalized Discounted Cumulative Gain@K metric computation."""
    
    def test_ndcg_at_k_perfect_order(self):
        """Test NDCG with perfect ordering."""
        retrieved = ["Context A", "Context B", "Context X"]
        relevant = ["Context A", "Context B"]
        
        ndcg = compute_ndcg_at_k(retrieved, relevant, k=3)
        
        # Perfect ordering should give high NDCG
        assert ndcg > 0.9
    
    def test_ndcg_at_k_reverse_order(self):
        """Test NDCG with reverse ordering."""
        retrieved = ["Context X", "Context B", "Context A"]
        relevant = ["Context A", "Context B"]
        
        ndcg = compute_ndcg_at_k(retrieved, relevant, k=3)
        
        # Reverse ordering should give lower NDCG than perfect
        assert 0.0 < ndcg < 0.9
    
    def test_ndcg_at_k_no_relevant(self):
        """Test NDCG with no relevant contexts."""
        retrieved = ["Context X", "Context Y", "Context Z"]
        relevant = ["Context A", "Context B"]
        
        ndcg = compute_ndcg_at_k(retrieved, relevant, k=3)
        
        assert ndcg == 0.0
    
    def test_ndcg_at_k_single_relevant(self):
        """Test NDCG with single relevant context."""
        retrieved = ["Context A", "Context X", "Context Y"]
        relevant = ["Context A"]
        
        ndcg = compute_ndcg_at_k(retrieved, relevant, k=3)
        
        assert ndcg == 1.0  # Perfect for single relevant item


class TestRetrievalMetricsIntegration:
    """Test integrated retrieval metrics computation."""
    
    def test_compute_retrieval_metrics_complete(self):
        """Test complete retrieval metrics computation."""
        retrieved = ["Context A", "Context X", "Context B"]
        relevant = ["Context A", "Context B"]
        
        metrics = compute_retrieval_metrics(retrieved, relevant, k=3)
        
        assert "recall_at_k" in metrics
        assert "mrr_at_k" in metrics
        assert "ndcg_at_k" in metrics
        assert "retrieved_count" in metrics
        assert "k_value" in metrics
        
        assert metrics["retrieved_count"] == 3
        assert metrics["k_value"] == 3
        assert metrics["recall_at_k"] == 1.0  # Both relevant found
        assert metrics["mrr_at_k"] == 1.0  # First relevant at position 1
    
    def test_evaluate_retrieval_for_case_success(self):
        """Test case-level retrieval evaluation."""
        response_data = {
            "contexts": ["Retrieved A", "Retrieved B", "Retrieved C"]
        }
        expected_contexts = ["Retrieved A", "Retrieved B"]
        retrieval_config = {
            "contexts_jsonpath": "$.contexts",
            "top_k": 3
        }
        
        metrics, status = evaluate_retrieval_for_case(
            response_data, expected_contexts, retrieval_config
        )
        
        assert status == "computed"
        assert "recall_at_k" in metrics
        assert "mrr_at_k" in metrics
        assert "ndcg_at_k" in metrics
        assert metrics["retrieved_count"] == 3
    
    def test_evaluate_retrieval_for_case_no_jsonpath(self):
        """Test case evaluation without JSONPath."""
        response_data = {"contexts": ["Context A"]}
        expected_contexts = ["Context A"]
        retrieval_config = {}
        
        metrics, status = evaluate_retrieval_for_case(
            response_data, expected_contexts, retrieval_config
        )
        
        assert status == "N/A (no JSONPath configured)"
        assert metrics == {}
    
    def test_evaluate_retrieval_for_case_no_contexts_surfaced(self):
        """Test case evaluation when no contexts are surfaced."""
        response_data = {"other_field": "data"}
        expected_contexts = ["Context A"]
        retrieval_config = {"contexts_jsonpath": "$.contexts"}
        
        metrics, status = evaluate_retrieval_for_case(
            response_data, expected_contexts, retrieval_config
        )
        
        assert status == "N/A (no contexts surfaced)"
        assert metrics == {}
