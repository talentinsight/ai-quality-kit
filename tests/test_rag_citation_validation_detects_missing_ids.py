"""
Test RAG citation validation detects missing IDs.

Ensures that citation validation correctly identifies when citations reference non-existent passages.
"""

import pytest
from apps.orchestrator.evaluators.rag_evaluator import RAGEvaluator


class TestRAGCitationValidationDetectsMissingIds:
    """Test RAG citation validation functionality."""
    
    def setup_method(self):
        """Set up RAG evaluator for testing."""
        self.evaluator = RAGEvaluator()
    
    def test_citation_validation_valid_citations(self):
        """Test that valid citations are correctly identified."""
        answer = "The capital of France is Paris [1]. It has a population of over 2 million [2]."
        retrieved_passage_ids = ["passage_1", "passage_2", "passage_3"]
        
        citation_valid = self.evaluator._validate_citations(answer, retrieved_passage_ids)
        
        assert citation_valid is True
    
    def test_citation_validation_invalid_citations(self):
        """Test that invalid citations are correctly identified."""
        answer = "The capital of France is Paris [1]. It has a population of over 2 million [5]."
        retrieved_passage_ids = ["passage_1", "passage_2", "passage_3"]  # Only 3 passages
        
        citation_valid = self.evaluator._validate_citations(answer, retrieved_passage_ids)
        
        assert citation_valid is False  # Citation [5] is invalid
    
    def test_citation_validation_no_citations(self):
        """Test that answers without citations return None."""
        answer = "The capital of France is Paris. It has a population of over 2 million."
        retrieved_passage_ids = ["passage_1", "passage_2", "passage_3"]
        
        citation_valid = self.evaluator._validate_citations(answer, retrieved_passage_ids)
        
        assert citation_valid is None  # No citations to validate
    
    def test_citation_validation_no_passages(self):
        """Test that citations with no retrieved passages are invalid."""
        answer = "The capital of France is Paris [1]. It has a population of over 2 million [2]."
        retrieved_passage_ids = []  # No passages retrieved
        
        citation_valid = self.evaluator._validate_citations(answer, retrieved_passage_ids)
        
        assert citation_valid is False  # Citations present but no passages
    
    def test_citation_validation_mixed_valid_invalid(self):
        """Test that mixed valid/invalid citations are correctly identified as invalid."""
        answer = "Paris is the capital [1]. Population is 2M [2]. Area is large [10]."
        retrieved_passage_ids = ["passage_1", "passage_2", "passage_3"]  # Only 3 passages
        
        citation_valid = self.evaluator._validate_citations(answer, retrieved_passage_ids)
        
        assert citation_valid is False  # Citation [10] is invalid
    
    def test_citation_validation_different_formats(self):
        """Test citation validation with different citation formats."""
        # Test with square brackets
        answer1 = "Information from source [1] and [2]."
        retrieved_passage_ids = ["p1", "p2"]
        assert self.evaluator._validate_citations(answer1, retrieved_passage_ids) is True
        
        # Test with parentheses
        answer2 = "Information from source (1) and (2)."
        assert self.evaluator._validate_citations(answer2, retrieved_passage_ids) is True
        
        # Test with angle brackets
        answer3 = "Information from source <1> and <2>."
        assert self.evaluator._validate_citations(answer3, retrieved_passage_ids) is True
        
        # Test invalid with different formats
        answer4 = "Information from source [1] and [5]."
        assert self.evaluator._validate_citations(answer4, retrieved_passage_ids) is False
    
    def test_citation_validation_duplicate_citations(self):
        """Test that duplicate citations are handled correctly."""
        answer = "Paris is the capital [1]. Paris is in France [1]. Population is 2M [2]."
        retrieved_passage_ids = ["passage_1", "passage_2"]
        
        citation_valid = self.evaluator._validate_citations(answer, retrieved_passage_ids)
        
        assert citation_valid is True  # Duplicates are fine if valid
    
    def test_citation_validation_zero_citation(self):
        """Test that zero citations are treated as invalid."""
        answer = "Information from source [0] and [1]."
        retrieved_passage_ids = ["passage_1", "passage_2"]
        
        citation_valid = self.evaluator._validate_citations(answer, retrieved_passage_ids)
        
        assert citation_valid is False  # Citation [0] is invalid (1-based indexing)
    
    def test_citation_validation_edge_case_boundary(self):
        """Test citation validation at boundary conditions."""
        retrieved_passage_ids = ["p1", "p2", "p3"]
        
        # Valid boundary cases
        answer_valid = "Source [1] and [3]."  # First and last valid
        assert self.evaluator._validate_citations(answer_valid, retrieved_passage_ids) is True
        
        # Invalid boundary cases
        answer_invalid = "Source [1] and [4]."  # [4] exceeds boundary
        assert self.evaluator._validate_citations(answer_invalid, retrieved_passage_ids) is False
    
    def test_citation_extraction_patterns(self):
        """Test that citation extraction works with various patterns."""
        # Test the underlying extraction method
        answer = "Text with [1], (2), <3>, and [10] citations."
        citations = self.evaluator._extract_citations(answer)
        
        expected_citations = [1, 2, 3, 10]
        assert sorted(citations) == sorted(expected_citations)
    
    def test_citation_extraction_no_citations(self):
        """Test citation extraction with no citations."""
        answer = "Text with no citations at all."
        citations = self.evaluator._extract_citations(answer)
        
        assert citations == []
    
    def test_citation_extraction_mixed_text(self):
        """Test citation extraction with mixed text and numbers."""
        answer = "Price is $100 [1] and temperature is 20°C (2). Version 3.0 <3>."
        citations = self.evaluator._extract_citations(answer)
        
        expected_citations = [1, 2, 3]
        assert sorted(citations) == sorted(expected_citations)
    
    def test_citation_accuracy_calculation(self):
        """Test citation accuracy calculation."""
        # All valid citations
        answer1 = "Source [1] and [2]."
        retrieved_passage_ids = ["p1", "p2", "p3"]
        accuracy1 = self.evaluator._calculate_citation_accuracy(answer1, retrieved_passage_ids)
        assert accuracy1 == 1.0  # 2/2 valid
        
        # Partially valid citations
        answer2 = "Source [1] and [5]."
        accuracy2 = self.evaluator._calculate_citation_accuracy(answer2, retrieved_passage_ids)
        assert accuracy2 == 0.5  # 1/2 valid
        
        # No valid citations
        answer3 = "Source [10] and [20]."
        accuracy3 = self.evaluator._calculate_citation_accuracy(answer3, retrieved_passage_ids)
        assert accuracy3 == 0.0  # 0/2 valid
        
        # No citations
        answer4 = "Source without citations."
        accuracy4 = self.evaluator._calculate_citation_accuracy(answer4, retrieved_passage_ids)
        assert accuracy4 is None  # No citations to evaluate
    
    def test_citation_validation_integration(self):
        """Test integration of citation validation with RAG metrics calculation."""
        # This would test the full pipeline, but requires more setup
        # For now, we'll test that the methods work together correctly
        
        answer = "The answer cites source [1] and [2], but also [10]."
        retrieved_passage_ids = ["p1", "p2"]
        
        # Test both accuracy and validation
        accuracy = self.evaluator._calculate_citation_accuracy(answer, retrieved_passage_ids)
        valid = self.evaluator._validate_citations(answer, retrieved_passage_ids)
        
        assert accuracy == 2/3  # 2 out of 3 citations valid
        assert valid is False    # Not all citations valid
    
    def test_citation_validation_empty_strings(self):
        """Test citation validation with empty strings."""
        # Empty answer
        assert self.evaluator._validate_citations("", ["p1", "p2"]) is None
        
        # Empty passages list
        assert self.evaluator._validate_citations("Text [1]", []) is False
        
        # Both empty
        assert self.evaluator._validate_citations("", []) is None
