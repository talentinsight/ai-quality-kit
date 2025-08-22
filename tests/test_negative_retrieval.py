"""
Negative retrieval tests for AI Quality Kit.

These tests verify that the system behaves correctly under bad or adversarial conditions,
such as out-of-scope questions, conflicting context, and ambiguous queries.
"""

import json
import os
import pytest
import requests
from typing import Dict, Any
from apps.testing.neg_utils import expect_idk, contains_any, NEG_MISLEADING_SNIPPET

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


@pytest.mark.skipif(
    not check_api_availability(),
    reason="API not available or missing required dependencies"
)
class TestNegativeRetrieval:
    """Test negative retrieval scenarios."""
    
    def test_out_of_scope_returns_idk_or_low_faithfulness(self):
        """Test that out-of-scope questions return 'I don't know' or low faithfulness."""
        queries = load_negative_dataset()
        
        # Filter out-of-scope queries
        out_of_scope_queries = [
            q for q in queries 
            if "out-of-scope" in q.get("note", "")
        ]
        
        if not out_of_scope_queries:
            pytest.skip("No out-of-scope queries found in dataset")
        
        force_idk = os.getenv("NEGATIVE_FORCE_IDK", "true").lower() == "true"
        
        for query_data in out_of_scope_queries:
            query = query_data["query"]
            note = query_data["note"]
            
            # Make API call
            response = requests.post(
                f"{API_BASE_URL}/ask",
                json={"query": query},
                timeout=30
            )
            
            # Assert response structure
            assert response.status_code == 200, f"Query: {query}, Note: {note}"
            
            data = response.json()
            assert "answer" in data, f"Missing 'answer' field for query: {query}"
            assert "context" in data, f"Missing 'context' field for query: {query}"
            
            answer = data["answer"]
            
            if force_idk:
                # If NEGATIVE_FORCE_IDK is true, expect "I don't know" response
                assert expect_idk(answer), (
                    f"Expected 'I don't know' response for out-of-scope query: {query}. "
                    f"Got: {answer[:100]}..."
                )
            else:
                # Otherwise, allow low faithfulness path
                # This could be implemented with live evaluation metrics
                assert isinstance(answer, str), f"Answer should be string for query: {query}"
                assert len(answer) > 0, f"Answer should not be empty for query: {query}"
    
    def test_conflicting_context_avoids_hallucination(self):
        """Test that conflicting context doesn't cause hallucination."""
        # Use a query that might pull misleading context
        misleading_query = f"{NEG_MISLEADING_SNIPPET} What is the total?"
        
        response = requests.post(
            f"{API_BASE_URL}/ask",
            json={"query": misleading_query},
            timeout=30
        )
        
        assert response.status_code == 200, "API should respond to misleading query"
        
        data = response.json()
        answer = data["answer"]
        
        # The model should NOT parrot the misleading number
        # It should either say "I don't know" or provide a cautious answer
        assert not contains_any(answer, ["999999"]), (
            f"Model should not parrot misleading context. "
            f"Answer: {answer[:100]}..."
        )
        
        # Check if the answer indicates uncertainty or refusal
        is_safe = (
            expect_idk(answer) or 
            "cannot determine" in answer.lower() or
            "not clear" in answer.lower() or
            "insufficient" in answer.lower()
        )
        
        assert is_safe, (
            f"Model should indicate uncertainty or refusal for conflicting context. "
            f"Answer: {answer[:100]}..."
        )
    
    def test_ambiguous_question_handling(self):
        """Test that ambiguous questions are handled appropriately."""
        queries = load_negative_dataset()
        
        # Filter ambiguous queries
        ambiguous_queries = [
            q for q in queries 
            if "ambiguous" in q.get("note", "")
        ]
        
        if not ambiguous_queries:
            pytest.skip("No ambiguous queries found in dataset")
        
        for query_data in ambiguous_queries:
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
            
            # Ambiguous questions should either:
            # 1. Ask for clarification
            # 2. Indicate insufficient information
            # 3. Provide a general, cautious response
            
            is_appropriate = (
                expect_idk(answer) or
                "clarification" in answer.lower() or
                "more specific" in answer.lower() or
                "insufficient" in answer.lower() or
                "general" in answer.lower()
            )
            
            assert is_appropriate, (
                f"Ambiguous question should be handled appropriately. "
                f"Query: {query}, Answer: {answer[:100]}..."
            )
    
    def test_empty_or_invalid_queries(self):
        """Test handling of empty or invalid queries."""
        # Test empty query
        response = requests.post(
            f"{API_BASE_URL}/ask",
            json={"query": ""},
            timeout=30
        )
        
        # Should handle gracefully (current system returns 200 with "I don't know")
        assert response.status_code == 200, (
            f"Empty query should be handled gracefully. Status: {response.status_code}"
        )
        
        # Test missing query field
        response = requests.post(
            f"{API_BASE_URL}/ask",
            json={},
            timeout=30
        )
        
        assert response.status_code in [400, 422], (
            f"Missing query field should return error. Status: {response.status_code}"
        )
        
        # Test very long query
        long_query = "What is AI? " * 1000  # Very long query
        response = requests.post(
            f"{API_BASE_URL}/ask",
            json={"query": long_query},
            timeout=30
        )
        
        # Should handle gracefully (either process or return error)
        assert response.status_code in [200, 400, 413], (
            f"Long query should be handled gracefully. Status: {response.status_code}"
        )
