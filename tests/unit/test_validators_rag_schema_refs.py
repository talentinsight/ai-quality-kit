"""Unit tests for RAG data validators."""

import pytest
from apps.testdata.validators_rag import (
    validate_schema_and_refs,
    detect_duplicates,
    compute_distribution_stats,
    validate_rag_data,
    RAGValidationResult
)


class TestSchemaAndRefsValidation:
    """Test schema and reference validation."""
    
    def test_valid_data(self):
        """Test validation with valid passages and QA set."""
        passages = [
            {"id": "p1", "text": "The capital of France is Paris."},
            {"id": "p2", "text": "Python is a programming language."}
        ]
        
        qaset = [
            {
                "qid": "q1",
                "question": "What is the capital of France?",
                "expected_answer": "Paris",
                "contexts": ["p1"]
            },
            {
                "qid": "q2",
                "question": "What is Python?",
                "expected_answer": "A programming language",
                "contexts": ["p2"]
            }
        ]
        
        result = validate_schema_and_refs(passages, qaset)
        
        assert result.valid_count == 2
        assert result.invalid_count == 0
        assert len(result.errors) == 0
    
    def test_missing_context_reference(self):
        """Test validation with missing context reference."""
        passages = [
            {"id": "p1", "text": "The capital of France is Paris."}
        ]
        
        qaset = [
            {
                "qid": "q1",
                "question": "What is the capital of France?",
                "expected_answer": "Paris",
                "contexts": ["p1", "p2"]  # p2 doesn't exist
            }
        ]
        
        result = validate_schema_and_refs(passages, qaset)
        
        assert result.valid_count == 0
        assert result.invalid_count == 1
        assert len(result.errors) == 1
        assert "context_id 'p2' not found" in result.errors[0]
    
    def test_easy_case_detection(self):
        """Test detection of easy cases."""
        passages = [
            {"id": "p1", "text": "The capital of France is Paris. It is a beautiful city."}
        ]
        
        qaset = [
            {
                "qid": "q1",
                "question": "What is the capital?",
                "expected_answer": "What is the capital?",  # Same as question
                "contexts": ["p1"]
            },
            {
                "qid": "q2",
                "question": "What is the capital of France?",
                "expected_answer": "Paris",  # Found verbatim in passage
                "contexts": ["p1"]
            }
        ]
        
        result = validate_schema_and_refs(passages, qaset)
        
        assert result.easy_count == 2
        assert len(result.warnings) == 2
        assert "identical" in result.warnings[0]
        assert "verbatim" in result.warnings[1]


class TestDuplicateDetection:
    """Test duplicate detection functionality."""
    
    def test_no_duplicates(self):
        """Test with no duplicates."""
        qaset = [
            {"qid": "q1", "question": "What is Python?", "expected_answer": "A language"},
            {"qid": "q2", "question": "What is Java?", "expected_answer": "Another language"}
        ]
        
        duplicate_count, messages = detect_duplicates(qaset)
        
        assert duplicate_count == 0
        assert len(messages) == 0
    
    def test_duplicate_questions(self):
        """Test detection of duplicate questions."""
        qaset = [
            {"qid": "q1", "question": "What is Python?", "expected_answer": "A language"},
            {"qid": "q2", "question": "What is Python?", "expected_answer": "A programming language"},
            {"qid": "q3", "question": "What is Java?", "expected_answer": "Another language"}
        ]
        
        duplicate_count, messages = detect_duplicates(qaset)
        
        assert duplicate_count == 1  # One duplicate (2 instances - 1)
        assert len(messages) >= 1
        assert "What is Python?" in messages[0]
    
    def test_duplicate_qids(self):
        """Test detection of duplicate QIDs."""
        qaset = [
            {"qid": "q1", "question": "What is Python?", "expected_answer": "A language"},
            {"qid": "q1", "question": "What is Java?", "expected_answer": "Another language"}
        ]
        
        duplicate_count, messages = detect_duplicates(qaset)
        
        assert len(messages) >= 1
        assert "q1" in str(messages)


class TestDistributionStats:
    """Test distribution statistics computation."""
    
    def test_basic_stats(self):
        """Test basic distribution statistics."""
        qaset = [
            {
                "qid": "q1",
                "question": "Short question?",
                "expected_answer": "Short answer",
                "contexts": ["p1", "p2"]
            },
            {
                "qid": "q2",
                "question": "This is a much longer question with more words?",
                "expected_answer": "This is also a longer answer with more detail",
                "contexts": ["p1"]
            }
        ]
        
        stats = compute_distribution_stats(qaset)
        
        assert stats["total_questions"] == 2
        assert stats["avg_question_length"] > 0
        assert stats["avg_answer_length"] > 0
        assert stats["questions_with_contexts"] == 2
        assert stats["avg_contexts_per_question"] == 1.5  # (2 + 1) / 2
    
    def test_empty_qaset(self):
        """Test with empty QA set."""
        stats = compute_distribution_stats([])
        
        assert stats["total_questions"] == 0
        assert stats["avg_question_length"] == 0
        assert stats["avg_answer_length"] == 0
    
    def test_metadata_distribution(self):
        """Test metadata distribution extraction."""
        qaset = [
            {
                "qid": "q1",
                "question": "Easy question?",
                "expected_answer": "Easy answer",
                "meta": {"difficulty": "easy", "category": "factual"}
            },
            {
                "qid": "q2",
                "question": "Hard question?",
                "expected_answer": "Hard answer",
                "meta": {"difficulty": "hard", "category": "factual"}
            },
            {
                "qid": "q3",
                "question": "Medium question?",
                "expected_answer": "Medium answer",
                "meta": {"difficulty": "medium", "category": "reasoning"}
            }
        ]
        
        stats = compute_distribution_stats(qaset)
        
        assert "difficulty_distribution" in stats
        assert stats["difficulty_distribution"]["easy"] == 1
        assert stats["difficulty_distribution"]["hard"] == 1
        assert stats["difficulty_distribution"]["medium"] == 1
        
        assert "category_distribution" in stats
        assert stats["category_distribution"]["factual"] == 2
        assert stats["category_distribution"]["reasoning"] == 1


class TestComprehensiveValidation:
    """Test comprehensive RAG data validation."""
    
    def test_comprehensive_validation(self):
        """Test full validation pipeline."""
        passages = [
            {"id": "p1", "text": "The capital of France is Paris."},
            {"id": "p2", "text": "Python is a programming language."}
        ]
        
        qaset = [
            {
                "qid": "q1",
                "question": "What is the capital of France?",
                "expected_answer": "Paris",
                "contexts": ["p1"]
            },
            {
                "qid": "q2",
                "question": "What is Python?",
                "expected_answer": "A programming language",
                "contexts": ["p2"]
            },
            {
                "qid": "q3",
                "question": "What is Python?",  # Duplicate
                "expected_answer": "A language",
                "contexts": ["p2"]
            }
        ]
        
        result = validate_rag_data(passages, qaset)
        
        # Check overall results
        assert result.valid_count == 3
        assert result.invalid_count == 0
        assert result.duplicate_count == 1  # One duplicate question
        
        # Check distribution stats
        assert result.distribution_stats["total_questions"] == 3
        assert result.distribution_stats["avg_question_length"] > 0
        
        # Should have some warnings (duplicates)
        assert len(result.warnings) > 0
    
    def test_validation_with_errors(self):
        """Test validation with various error conditions."""
        passages = [
            {"id": "p1", "text": "The capital of France is Paris."}
        ]
        
        qaset = [
            {
                "qid": "q1",
                "question": "What is the capital?",
                "expected_answer": "Paris",
                "contexts": ["p1", "p2"]  # p2 missing
            },
            {
                "qid": "q2",
                "question": "Same question",
                "expected_answer": "Same question",  # Easy case
                "contexts": ["p1"]
            }
        ]
        
        result = validate_rag_data(passages, qaset)
        
        # Should have validation errors
        assert result.invalid_count == 1
        assert result.easy_count == 1
        assert len(result.errors) > 0
        assert len(result.warnings) > 0
