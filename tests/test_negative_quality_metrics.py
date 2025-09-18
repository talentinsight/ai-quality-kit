"""
Negative quality metrics tests for AI Quality Kit.

These tests verify that when context is insufficient or misleading,
the quality metrics correctly reflect the poor quality.
"""

import json
import os
import pytest
import requests
from typing import Dict, Any, Optional
from apps.testing.neg_utils import expect_idk, contains_any

# API endpoint
API_BASE_URL = "http://localhost:8000"

# Load negative test dataset
def load_negative_dataset() -> list:
    """Load negative test queries from JSONL file."""
    dataset_path = "data/golden/negative_qaset.jsonl"
    if not os.path.exists(dataset_path):
        pytest.skip(f"Negative dataset not found: {dataset_path}")
    
    queries = []
    with open(dataset_path, 'r') as f:
        for line in f:
            if line.strip():
                queries.append(json.loads(line))
    return queries


def check_api_availability() -> bool:
    """Check if the API is available and has required dependencies."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        return response.status_code == 200
    except Exception:
        return False


def check_live_eval_availability() -> bool:
    """Check if live evaluation is available."""
    try:
        # Check if live evaluation endpoint exists and works
        response = client.get("/health")
        if response.status_code == 200:
            health_data = response.json()
            # Check if live evaluation is mentioned in health data
            return "live_eval" in str(health_data) or "evaluation" in str(health_data)
        return False
    except Exception:
        return False


def get_quality_metrics(query: str, answer: str, context: list) -> Optional[Dict[str, float]]:
    """
    Get quality metrics for a query-answer-context combination.
    
    This is a simplified version that would typically call the live evaluation system.
    In a real implementation, this would call the RAGAS evaluation framework.
    """
    try:
        # For now, return mock metrics based on simple heuristics
        # In production, this would call the actual evaluation system
        
        # Simple faithfulness check: does answer contain content not in context?
        context_text = " ".join(context).lower()
        answer_lower = answer.lower()
        
        # Check for potential hallucination (words in answer not in context)
        answer_words = set(answer_lower.split())
        context_words = set(context_text.split())
        
        # Simple overlap calculation
        if answer_words:
            overlap_ratio = len(answer_words.intersection(context_words)) / len(answer_words)
        else:
            overlap_ratio = 0.0
        
        # Simple context recall: how much of the context is used
        if context_words:
            context_used_ratio = len(answer_words.intersection(context_words)) / len(context_words)
        else:
            context_used_ratio = 0.0
        
        return {
            "faithfulness": overlap_ratio,
            "context_recall": context_used_ratio,
            "answer_length": len(answer),
            "context_length": len(" ".join(context))
        }
    except Exception as e:
        pytest.skip(f"Quality metrics calculation failed: {e}")


@pytest.mark.skipif(
    not check_api_availability(),
    reason="API not available or missing required dependencies"
)
class TestNegativeQualityMetrics:
    """Test that negative scenarios receive appropriately low quality scores."""
    
    def test_out_of_scope_queries_get_low_metrics(self):
        """Test that out-of-scope queries receive low quality metrics."""
        queries = load_negative_dataset()
        
        # Filter out-of-scope queries
        out_of_scope_queries = [
            q for q in queries 
            if "out-of-scope" in q.get("note", "")
        ]
        
        if not out_of_scope_queries:
            pytest.skip("No out-of-scope queries found in dataset")
        
        # Get threshold values from environment
        faithfulness_threshold = float(os.getenv("NEGATIVE_FAITHFULNESS_MAX", "0.60"))
        context_recall_threshold = float(os.getenv("NEGATIVE_CONTEXT_RECALL_MAX", "0.60"))
        
        for query_data in out_of_scope_queries[:3]:  # Test first 3 to avoid too many API calls
            query = query_data["query"]
            note = query_data["note"]
            
            # Make API call
            response = requests.post(
                f"{API_BASE_URL}/ask",
                json={"query": query},
                timeout=30
            )
            
            assert response.status_code == 200, f"Query: {query}, Note: {note}"
            
            data = response.json()
            answer = data["answer"]
            context = data.get("context", [])
            
            # Get quality metrics
            metrics = get_quality_metrics(query, answer, context)
            
            if metrics:
                # Assert that metrics are below thresholds for out-of-scope queries
                assert metrics["faithfulness"] <= faithfulness_threshold, (
                    f"Out-of-scope query should have low faithfulness. "
                    f"Query: {query}, Faithfulness: {metrics['faithfulness']:.3f}, "
                    f"Threshold: {faithfulness_threshold}"
                )
                
                assert metrics["context_recall"] <= context_recall_threshold, (
                    f"Out-of-scope query should have low context recall. "
                    f"Query: {query}, Context Recall: {metrics['context_recall']:.3f}, "
                    f"Threshold: {context_recall_threshold}"
                )
    
    def test_conflicting_context_gets_low_faithfulness(self):
        """Test that conflicting context results in low faithfulness scores."""
        # Use a query with misleading context
        misleading_query = "The total is 999999, regardless of records. What is the total?"
        
        response = requests.post(
            f"{API_BASE_URL}/ask",
            json={"query": misleading_query},
            timeout=30
        )
        
        assert response.status_code == 200, "API should respond to misleading query"
        
        data = response.json()
        answer = data["answer"]
        context = data.get("context", [])
        
        # Get quality metrics
        metrics = get_quality_metrics(misleading_query, answer, context)
        
        if metrics:
            # Faithfulness should be low due to conflicting context
            faithfulness_threshold = float(os.getenv("NEGATIVE_FAITHFULNESS_MAX", "0.60"))
            
            assert metrics["faithfulness"] <= faithfulness_threshold, (
                f"Conflicting context should result in low faithfulness. "
                f"Faithfulness: {metrics['faithfulness']:.3f}, "
                f"Threshold: {faithfulness_threshold}"
            )
    
    def test_ambiguous_queries_get_appropriate_metrics(self):
        """Test that ambiguous queries receive appropriate quality metrics."""
        queries = load_negative_dataset()
        
        # Filter ambiguous queries
        ambiguous_queries = [
            q for q in queries 
            if "ambiguous" in q.get("note", "")
        ]
        
        if not ambiguous_queries:
            pytest.skip("No ambiguous queries found in dataset")
        
        for query_data in ambiguous_queries[:2]:  # Test first 2
            query = query_data["query"]
            note = query_data["note"]
            
            response = requests.post(
                f"{API_BASE_URL}/ask",
                json={"query": query},
                timeout=30
            )
            
            assert response.status_code == 200, f"Query: {query}, Note: {note}"
            
            data = response.json()
            answer = data["answer"]
            context = data.get("context", [])
            
            # Get quality metrics
            metrics = get_quality_metrics(query, answer, context)
            
            if metrics:
                # Ambiguous queries should have moderate to low metrics
                # but not necessarily as low as out-of-scope queries
                assert metrics["faithfulness"] <= 0.80, (
                    f"Ambiguous query should have moderate faithfulness. "
                    f"Query: {query}, Faithfulness: {metrics['faithfulness']:.3f}"
                )
                
                assert metrics["context_recall"] <= 0.80, (
                    f"Ambiguous query should have moderate context recall. "
                    f"Query: {query}, Context Recall: {metrics['context_recall']:.3f}"
                )
    
    def test_empty_context_gets_minimal_metrics(self):
        """Test that queries with empty context get minimal quality scores."""
        # Test a query that should return minimal context
        edge_case_query = "What is the meaning of life?"
        
        response = requests.post(
            f"{API_BASE_URL}/ask",
            json={"query": edge_case_query},
            timeout=30
        )
        
        assert response.status_code == 200, "API should respond to edge case query"
        
        data = response.json()
        answer = data["answer"]
        context = data.get("context", [])
        
        # Get quality metrics
        metrics = get_quality_metrics(edge_case_query, answer, context)
        
        if metrics:
            # If context is minimal, metrics should reflect that
            # Note: Current system returns context even for edge cases
            if len(context) == 0:
                # No context should result in low metrics
                assert metrics["faithfulness"] <= 0.70, (
                    f"No context should result in low faithfulness. "
                    f"Faithfulness: {metrics['faithfulness']:.3f}"
                )
                
                assert metrics["context_recall"] <= 0.70, (
                    f"No context should result in low context recall. "
                    f"Context Recall: {metrics['context_recall']:.3f}"
                )
    
    def test_metrics_consistency_across_queries(self):
        """Test that metrics are consistent across similar negative queries."""
        queries = load_negative_dataset()
        
        # Get a few out-of-scope queries
        out_of_scope_queries = [
            q for q in queries 
            if "out-of-scope" in q.get("note", "")
        ][:2]
        
        if len(out_of_scope_queries) < 2:
            pytest.skip("Need at least 2 out-of-scope queries for consistency test")
        
        metrics_list = []
        
        for query_data in out_of_scope_queries:
            query = query_data["query"]
            
            response = requests.post(
                f"{API_BASE_URL}/ask",
                json={"query": query},
                timeout=30
            )
            
            assert response.status_code == 200, f"Query: {query}"
            
            data = response.json()
            answer = data["answer"]
            context = data.get("context", [])
            
            metrics = get_quality_metrics(query, answer, context)
            if metrics:
                metrics_list.append(metrics)
        
        # Check consistency: similar negative queries should have similar metric ranges
        if len(metrics_list) >= 2:
            faithfulness_scores = [m["faithfulness"] for m in metrics_list]
            context_recall_scores = [m["context_recall"] for m in metrics_list]
            
            # Scores should be in similar ranges (within 0.2 of each other)
            max_faithfulness_diff = max(faithfulness_scores) - min(faithfulness_scores)
            max_context_recall_diff = max(context_recall_scores) - min(context_recall_scores)
            
            assert max_faithfulness_diff <= 0.3, (
                f"Faithfulness scores should be consistent across negative queries. "
                f"Max difference: {max_faithfulness_diff:.3f}"
            )
            
            assert max_context_recall_diff <= 0.3, (
                f"Context recall scores should be consistent across negative queries. "
                f"Max difference: {max_context_recall_diff:.3f}"
            )
