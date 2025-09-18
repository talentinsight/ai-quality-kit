"""Unit tests for retrieval metrics when contexts are absent (N/A cases)."""

import pytest
from apps.orchestrator.retrieval_metrics import (
    extract_contexts_from_response,
    evaluate_retrieval_for_case
)


class TestMissingContextsHandling:
    """Test handling when contexts are missing or unavailable."""
    
    def test_extract_contexts_missing_field(self):
        """Test extraction when the field doesn't exist."""
        response = {
            "answer": "Some answer",
            "metadata": {"source": "test"}
        }
        
        contexts = extract_contexts_from_response(response, "$.contexts")
        
        assert contexts == []
    
    def test_extract_contexts_null_field(self):
        """Test extraction when field is null."""
        response = {
            "contexts": None,
            "answer": "Some answer"
        }
        
        contexts = extract_contexts_from_response(response, "$.contexts")
        
        assert contexts == []
    
    def test_extract_contexts_empty_list(self):
        """Test extraction when field is empty list."""
        response = {
            "contexts": [],
            "answer": "Some answer"
        }
        
        contexts = extract_contexts_from_response(response, "$.contexts")
        
        assert contexts == []
    
    def test_extract_contexts_list_with_nulls(self):
        """Test extraction when list contains null values."""
        response = {
            "contexts": ["Context 1", None, "Context 2", None]
        }
        
        contexts = extract_contexts_from_response(response, "$.contexts")
        
        # Should filter out null values and convert to strings
        assert contexts == ["Context 1", "Context 2"]
    
    def test_extract_contexts_list_with_mixed_types(self):
        """Test extraction when list contains mixed types."""
        response = {
            "contexts": ["String context", 123, {"nested": "object"}, True]
        }
        
        contexts = extract_contexts_from_response(response, "$.contexts")
        
        # Should convert all to strings
        assert contexts == ["String context", "123", "{'nested': 'object'}", "True"]


class TestJSONPathErrors:
    """Test JSONPath error handling."""
    
    def test_invalid_jsonpath_syntax(self):
        """Test with invalid JSONPath syntax."""
        response = {"contexts": ["Context 1"]}
        
        # Invalid JSONPath with unmatched bracket
        contexts = extract_contexts_from_response(response, "$.contexts[")
        
        assert contexts == []
    
    def test_complex_invalid_jsonpath(self):
        """Test with complex invalid JSONPath."""
        response = {"data": {"contexts": ["Context 1"]}}
        
        # Invalid JSONPath with bad filter syntax
        contexts = extract_contexts_from_response(response, "$.data.contexts[?(@.invalid")
        
        assert contexts == []
    
    def test_nonexistent_nested_path(self):
        """Test with deeply nested nonexistent path."""
        response = {
            "data": {
                "results": {
                    "items": []
                }
            }
        }
        
        contexts = extract_contexts_from_response(response, "$.data.results.contexts.retrieved")
        
        assert contexts == []


class TestCaseEvaluationNAScenarios:
    """Test case-level evaluation N/A scenarios."""
    
    def test_evaluate_case_no_jsonpath_configured(self):
        """Test case evaluation when no JSONPath is configured."""
        response_data = {
            "answer": "Paris is the capital of France.",
            "contexts": ["France is a country in Europe..."]
        }
        expected_contexts = ["France is a country in Europe..."]
        retrieval_config = {}  # No contexts_jsonpath
        
        metrics, status = evaluate_retrieval_for_case(
            response_data, expected_contexts, retrieval_config
        )
        
        assert status == "N/A (no JSONPath configured)"
        assert metrics == {}
    
    def test_evaluate_case_empty_jsonpath(self):
        """Test case evaluation with empty JSONPath."""
        response_data = {"contexts": ["Context 1"]}
        expected_contexts = ["Context 1"]
        retrieval_config = {"contexts_jsonpath": ""}  # Empty JSONPath
        
        metrics, status = evaluate_retrieval_for_case(
            response_data, expected_contexts, retrieval_config
        )
        
        assert status == "N/A (no JSONPath configured)"
        assert metrics == {}
    
    def test_evaluate_case_none_jsonpath(self):
        """Test case evaluation with None JSONPath."""
        response_data = {"contexts": ["Context 1"]}
        expected_contexts = ["Context 1"]
        retrieval_config = {"contexts_jsonpath": None}  # None JSONPath
        
        metrics, status = evaluate_retrieval_for_case(
            response_data, expected_contexts, retrieval_config
        )
        
        assert status == "N/A (no JSONPath configured)"
        assert metrics == {}
    
    def test_evaluate_case_no_contexts_in_response(self):
        """Test case evaluation when response has no contexts."""
        response_data = {
            "answer": "Paris is the capital of France.",
            "metadata": {"confidence": 0.95}
        }
        expected_contexts = ["France is a country..."]
        retrieval_config = {"contexts_jsonpath": "$.contexts"}
        
        metrics, status = evaluate_retrieval_for_case(
            response_data, expected_contexts, retrieval_config
        )
        
        assert status == "N/A (no contexts surfaced)"
        assert metrics == {}
    
    def test_evaluate_case_empty_contexts_list(self):
        """Test case evaluation when contexts list is empty."""
        response_data = {
            "answer": "Paris is the capital of France.",
            "contexts": []  # Empty list
        }
        expected_contexts = ["France is a country..."]
        retrieval_config = {"contexts_jsonpath": "$.contexts"}
        
        metrics, status = evaluate_retrieval_for_case(
            response_data, expected_contexts, retrieval_config
        )
        
        assert status == "N/A (no contexts surfaced)"
        assert metrics == {}
    
    def test_evaluate_case_contexts_all_null(self):
        """Test case evaluation when all contexts are null."""
        response_data = {
            "answer": "Paris is the capital of France.",
            "contexts": [None, None, None]  # All null
        }
        expected_contexts = ["France is a country..."]
        retrieval_config = {"contexts_jsonpath": "$.contexts"}
        
        metrics, status = evaluate_retrieval_for_case(
            response_data, expected_contexts, retrieval_config
        )
        
        assert status == "N/A (no contexts surfaced)"
        assert metrics == {}
    
    def test_evaluate_case_wrong_jsonpath(self):
        """Test case evaluation with wrong JSONPath."""
        response_data = {
            "answer": "Paris is the capital of France.",
            "retrieved_passages": ["France is a country..."]  # Different field name
        }
        expected_contexts = ["France is a country..."]
        retrieval_config = {"contexts_jsonpath": "$.contexts"}  # Wrong path
        
        metrics, status = evaluate_retrieval_for_case(
            response_data, expected_contexts, retrieval_config
        )
        
        assert status == "N/A (no contexts surfaced)"
        assert metrics == {}
    
    def test_evaluate_case_nested_missing_field(self):
        """Test case evaluation with nested missing field."""
        response_data = {
            "answer": "Paris is the capital of France.",
            "data": {
                "other_field": ["Some data"]
                # Missing 'retrieved' field
            }
        }
        expected_contexts = ["France is a country..."]
        retrieval_config = {"contexts_jsonpath": "$.data.retrieved"}
        
        metrics, status = evaluate_retrieval_for_case(
            response_data, expected_contexts, retrieval_config
        )
        
        assert status == "N/A (no contexts surfaced)"
        assert metrics == {}


class TestEdgeCases:
    """Test edge cases for retrieval metrics."""
    
    def test_extract_contexts_very_large_response(self):
        """Test extraction from very large response."""
        # Simulate a large response with many fields
        response = {
            f"field_{i}": f"value_{i}" for i in range(1000)
        }
        response["contexts"] = ["Context 1", "Context 2"]
        
        contexts = extract_contexts_from_response(response, "$.contexts")
        
        assert contexts == ["Context 1", "Context 2"]
    
    def test_extract_contexts_deeply_nested(self):
        """Test extraction from deeply nested structure."""
        response = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "contexts": ["Deep context"]
                        }
                    }
                }
            }
        }
        
        contexts = extract_contexts_from_response(response, "$.level1.level2.level3.level4.contexts")
        
        assert contexts == ["Deep context"]
    
    def test_extract_contexts_array_index_access(self):
        """Test extraction with array index access."""
        response = {
            "results": [
                {"contexts": ["First result contexts"]},
                {"contexts": ["Second result contexts"]}
            ]
        }
        
        # Access first result's contexts
        contexts = extract_contexts_from_response(response, "$.results[0].contexts")
        
        assert contexts == ["First result contexts"]
    
    def test_evaluate_case_with_top_k_but_no_contexts(self):
        """Test case evaluation with top_k configured but no contexts."""
        response_data = {"answer": "Some answer"}
        expected_contexts = ["Expected context"]
        retrieval_config = {
            "contexts_jsonpath": "$.contexts",
            "top_k": 5  # top_k configured but no contexts
        }
        
        metrics, status = evaluate_retrieval_for_case(
            response_data, expected_contexts, retrieval_config
        )
        
        assert status == "N/A (no contexts surfaced)"
        assert metrics == {}
        # top_k should be ignored when no contexts are found
