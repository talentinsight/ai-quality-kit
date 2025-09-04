"""Unit tests for robustness catalog determinism."""

import pytest
from apps.orchestrator.robustness_catalog import (
    RobustnessCatalog,
    should_apply_robustness_perturbations,
    apply_perturbations_to_sample
)
from apps.orchestrator.run_tests import OrchestratorRequest


class TestRobustnessCatalogDeterminism:
    """Test deterministic behavior of robustness catalog."""
    
    def test_catalog_deterministic_with_same_seed(self):
        """Test that same seed produces same results."""
        text = "What is the capital of France?"
        
        catalog1 = RobustnessCatalog(seed=42)
        catalog2 = RobustnessCatalog(seed=42)
        
        results1 = catalog1.apply_perturbations(text)
        results2 = catalog2.apply_perturbations(text)
        
        # Should produce identical results
        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1.perturbation_type == r2.perturbation_type
            assert r1.perturbed_text == r2.perturbed_text
            assert r1.applied == r2.applied
    
    def test_catalog_different_with_different_seeds(self):
        """Test that different seeds produce different results."""
        text = "What is the capital of France?"
        
        catalog1 = RobustnessCatalog(seed=42)
        catalog2 = RobustnessCatalog(seed=123)
        
        results1 = catalog1.apply_perturbations(text)
        results2 = catalog2.apply_perturbations(text)
        
        # Should produce different results (at least some difference)
        different = False
        for r1, r2 in zip(results1, results2):
            if r1.perturbation_type != r2.perturbation_type or r1.perturbed_text != r2.perturbed_text:
                different = True
                break
        
        assert different, "Different seeds should produce different results"
    
    def test_same_text_same_perturbations(self):
        """Test that same text gets same perturbations."""
        text = "What is the capital of France?"
        catalog = RobustnessCatalog(seed=42)
        
        results1 = catalog.apply_perturbations(text)
        results2 = catalog.apply_perturbations(text)
        
        # Should be identical
        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1.perturbation_type == r2.perturbation_type
            assert r1.perturbed_text == r2.perturbed_text
    
    def test_different_text_different_perturbations(self):
        """Test that different text gets different perturbations."""
        catalog = RobustnessCatalog(seed=42)
        
        text1 = "What is the capital of France?"
        text2 = "How do you calculate compound interest?"
        
        results1 = catalog.apply_perturbations(text1)
        results2 = catalog.apply_perturbations(text2)
        
        # Should produce different perturbations
        assert results1[0].perturbed_text != results2[0].perturbed_text


class TestPerturbationTypes:
    """Test individual perturbation types."""
    
    def test_typo_noise_deterministic(self):
        """Test typo noise is deterministic."""
        catalog = RobustnessCatalog(seed=42)
        text = "This is a long sentence with multiple words to test typo noise"
        
        result1 = catalog._apply_typo_noise(text)
        result2 = catalog._apply_typo_noise(text)
        
        assert result1.perturbed_text == result2.perturbed_text
        assert result1.applied == result2.applied
    
    def test_casing_flip_deterministic(self):
        """Test casing flip is deterministic."""
        catalog = RobustnessCatalog(seed=42)
        text = "This is a sentence with multiple words"
        
        result1 = catalog._apply_casing_flip(text)
        result2 = catalog._apply_casing_flip(text)
        
        assert result1.perturbed_text == result2.perturbed_text
        assert result1.applied == result2.applied
    
    def test_negation_insert_deterministic(self):
        """Test negation insert is deterministic."""
        catalog = RobustnessCatalog(seed=42)
        text = "This is a good example"
        
        result1 = catalog._apply_negation_insert(text)
        result2 = catalog._apply_negation_insert(text)
        
        assert result1.perturbed_text == result2.perturbed_text
        assert result1.applied == result2.applied
    
    def test_distractor_suffix_deterministic(self):
        """Test distractor suffix is deterministic."""
        catalog = RobustnessCatalog(seed=42)
        text = "What is the capital of France?"
        
        result1 = catalog._apply_distractor_suffix(text)
        result2 = catalog._apply_distractor_suffix(text)
        
        assert result1.perturbed_text == result2.perturbed_text
        assert result1.applied == result2.applied
    
    def test_typo_noise_skips_short_text(self):
        """Test typo noise skips very short text."""
        catalog = RobustnessCatalog(seed=42)
        short_text = "Hi"
        
        result = catalog._apply_typo_noise(short_text)
        
        assert not result.applied
        assert "text too short" in result.details
    
    def test_negation_insert_no_suitable_point(self):
        """Test negation insert when no suitable point found."""
        catalog = RobustnessCatalog(seed=42)
        text = "Hello world"  # No suitable verbs for negation
        
        result = catalog._apply_negation_insert(text)
        
        assert not result.applied
        assert "no suitable negation point found" in result.details


class TestSamplePerturbations:
    """Test sample-level perturbation application."""
    
    def test_apply_perturbations_to_sample_deterministic(self):
        """Test that sample perturbations are deterministic."""
        qa_cases = [
            {"qid": "q1", "question": "What is the capital of France?", "expected_answer": "Paris"},
            {"qid": "q2", "question": "How do you calculate interest?", "expected_answer": "Formula"},
            {"qid": "q3", "question": "What is machine learning?", "expected_answer": "AI subset"}
        ]
        
        catalog1 = RobustnessCatalog(seed=42)
        catalog2 = RobustnessCatalog(seed=42)
        
        perturbed1 = apply_perturbations_to_sample(qa_cases, catalog1, sample_size=2)
        perturbed2 = apply_perturbations_to_sample(qa_cases, catalog2, sample_size=2)
        
        # Should produce identical results
        assert len(perturbed1) == len(perturbed2) == 2
        
        for p1, p2 in zip(perturbed1, perturbed2):
            assert p1["qid"] == p2["qid"]
            assert p1["question"] == p2["question"]
            assert p1["original_question"] == p2["original_question"]
            assert p1["perturbations_applied"] == p2["perturbations_applied"]
    
    def test_apply_perturbations_sample_size_respected(self):
        """Test that sample size is respected."""
        qa_cases = [
            {"qid": f"q{i}", "question": f"Question {i}?", "expected_answer": f"Answer {i}"}
            for i in range(10)
        ]
        
        catalog = RobustnessCatalog(seed=42)
        
        perturbed = apply_perturbations_to_sample(qa_cases, catalog, sample_size=3)
        
        assert len(perturbed) == 3
    
    def test_apply_perturbations_preserves_metadata(self):
        """Test that perturbations preserve other metadata."""
        qa_cases = [
            {
                "qid": "q1", 
                "question": "What is the capital of France?", 
                "expected_answer": "Paris",
                "contexts": ["France is a country..."],
                "meta": {"difficulty": "easy"}
            }
        ]
        
        catalog = RobustnessCatalog(seed=42)
        perturbed = apply_perturbations_to_sample(qa_cases, catalog)
        
        assert len(perturbed) == 1
        case = perturbed[0]
        
        # Original metadata should be preserved
        assert case["qid"] == "q1"
        assert case["expected_answer"] == "Paris"
        assert case["contexts"] == ["France is a country..."]
        assert case["meta"] == {"difficulty": "easy"}
        
        # New fields should be added
        assert "original_question" in case
        assert "perturbations_applied" in case
        assert "perturbation_details" in case


class TestPerturbationConditions:
    """Test conditions for applying perturbations."""
    
    def test_should_apply_when_gt_not_available(self):
        """Test perturbations applied when GT not available."""
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            ground_truth="not_available"
        )
        
        should_apply = should_apply_robustness_perturbations(request)
        
        assert should_apply is True
    
    def test_should_not_apply_when_gt_available(self):
        """Test perturbations not applied when GT available (unless prompt robustness selected)."""
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            ground_truth="available"
        )
        
        should_apply = should_apply_robustness_perturbations(request)
        
        assert should_apply is False
    
    def test_should_apply_when_prompt_robustness_in_selected_tests(self):
        """Test perturbations applied when prompt robustness in selected tests."""
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            ground_truth="available"
        )
        
        selected_tests = ["rag_basic", "prompt_robustness_test", "other_test"]
        should_apply = should_apply_robustness_perturbations(request, selected_tests)
        
        assert should_apply is True
    
    def test_should_apply_when_prompt_robustness_in_suite_config(self):
        """Test perturbations applied when prompt robustness enabled in suite config."""
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            ground_truth="available",
            suite_configs={
                "rag_reliability_robustness": {
                    "prompt_robustness": {"enabled": True}
                }
            }
        )
        
        should_apply = should_apply_robustness_perturbations(request)
        
        assert should_apply is True
    
    def test_should_not_apply_when_prompt_robustness_disabled(self):
        """Test perturbations not applied when prompt robustness explicitly disabled."""
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            ground_truth="available",
            suite_configs={
                "rag_reliability_robustness": {
                    "prompt_robustness": {"enabled": False}
                }
            }
        )
        
        should_apply = should_apply_robustness_perturbations(request)
        
        assert should_apply is False


class TestPerturbationSummary:
    """Test perturbation summary generation."""
    
    def test_get_perturbation_summary(self):
        """Test perturbation summary generation."""
        catalog = RobustnessCatalog(seed=42)
        text = "This is a test sentence with multiple words"
        
        results = catalog.apply_perturbations(text)
        summary = catalog.get_perturbation_summary(results)
        
        assert "total_attempted" in summary
        assert "total_applied" in summary
        assert "perturbation_types" in summary
        assert "details" in summary
        
        assert summary["total_attempted"] == len(results)
        assert summary["total_applied"] <= summary["total_attempted"]
        assert len(summary["perturbation_types"]) == summary["total_applied"]
        assert len(summary["details"]) == summary["total_applied"]
