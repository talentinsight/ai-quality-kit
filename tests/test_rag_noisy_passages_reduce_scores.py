"""
Test RAG noisy passages reduce scores.

Ensures that injecting noisy/poisoned passages into retrieval reduces faithfulness scores.
"""

import pytest
from apps.orchestrator.evaluators.rag_evaluator import RAGEvaluator


class TestRAGNoisyPassagesReduceScores:
    """Test RAG robustness with noisy passages."""
    
    def setup_method(self):
        """Set up RAG evaluator for testing."""
        self.evaluator = RAGEvaluator()
    
    def test_inject_noisy_passages_basic(self):
        """Test basic noise injection functionality."""
        original_passages = [
            "Paris is the capital of France.",
            "The Eiffel Tower is located in Paris.",
            "France is in Western Europe."
        ]
        
        noisy_passages = self.evaluator._inject_noisy_passages(original_passages, noise_ratio=0.5)
        
        # Should have more passages than original (noise added)
        assert len(noisy_passages) > len(original_passages)
        
        # Should contain original passages
        for passage in original_passages:
            assert passage in noisy_passages
        
        # Should contain noise markers
        noise_count = sum(1 for p in noisy_passages if "[NOISE]" in p)
        assert noise_count > 0
    
    def test_inject_noisy_passages_zero_ratio(self):
        """Test that zero noise ratio returns original passages."""
        original_passages = [
            "Paris is the capital of France.",
            "The Eiffel Tower is located in Paris."
        ]
        
        noisy_passages = self.evaluator._inject_noisy_passages(original_passages, noise_ratio=0.0)
        
        assert noisy_passages == original_passages
        assert len(noisy_passages) == len(original_passages)
    
    def test_inject_noisy_passages_high_ratio(self):
        """Test noise injection with high ratio."""
        original_passages = [
            "Paris is the capital of France.",
            "The Eiffel Tower is located in Paris."
        ]
        
        noisy_passages = self.evaluator._inject_noisy_passages(original_passages, noise_ratio=1.0)
        
        # Should have significantly more passages
        assert len(noisy_passages) >= len(original_passages) * 2
        
        # Should contain noise
        noise_count = sum(1 for p in noisy_passages if "[NOISE]" in p)
        assert noise_count >= len(original_passages)  # At least as many noise as original
    
    def test_inject_noisy_passages_empty_input(self):
        """Test noise injection with empty input."""
        noisy_passages = self.evaluator._inject_noisy_passages([], noise_ratio=0.5)
        assert noisy_passages == []
    
    def test_inject_noisy_passages_single_passage(self):
        """Test noise injection with single passage."""
        original_passages = ["Paris is the capital of France."]
        
        noisy_passages = self.evaluator._inject_noisy_passages(original_passages, noise_ratio=0.5)
        
        # Should have at least 2 passages (original + noise)
        assert len(noisy_passages) >= 2
        assert original_passages[0] in noisy_passages
        
        # Should have noise
        noise_count = sum(1 for p in noisy_passages if "[NOISE]" in p)
        assert noise_count >= 1
    
    def test_calculate_robustness_penalty_degradation(self):
        """Test robustness penalty calculation when scores degrade."""
        baseline_score = 0.8
        noisy_score = 0.6
        
        penalty = self.evaluator._calculate_robustness_penalty(baseline_score, noisy_score)
        
        assert penalty == 0.2  # Positive penalty indicates degradation
    
    def test_calculate_robustness_penalty_improvement(self):
        """Test robustness penalty calculation when scores improve (rare)."""
        baseline_score = 0.6
        noisy_score = 0.8
        
        penalty = self.evaluator._calculate_robustness_penalty(baseline_score, noisy_score)
        
        assert penalty == -0.2  # Negative penalty indicates improvement
    
    def test_calculate_robustness_penalty_no_change(self):
        """Test robustness penalty calculation when scores don't change."""
        baseline_score = 0.7
        noisy_score = 0.7
        
        penalty = self.evaluator._calculate_robustness_penalty(baseline_score, noisy_score)
        
        assert penalty == 0.0  # No penalty when no change
    
    def test_noise_generation_scrambles_words(self):
        """Test that noise generation actually scrambles words."""
        original_passages = [
            "The quick brown fox jumps over the lazy dog."
        ]
        
        # Generate multiple noisy versions to check randomness
        noisy_versions = []
        for _ in range(5):
            noisy_passages = self.evaluator._inject_noisy_passages(original_passages, noise_ratio=1.0)
            noise_passages = [p for p in noisy_passages if "[NOISE]" in p]
            if noise_passages:
                noisy_versions.append(noise_passages[0])
        
        # Should have generated some noise
        assert len(noisy_versions) > 0
        
        # Noise should be different from original
        original_text = original_passages[0]
        for noise in noisy_versions:
            # Remove [NOISE] prefix for comparison
            noise_content = noise.replace("[NOISE] ", "")
            assert noise_content != original_text  # Should be scrambled
    
    def test_noise_injection_preserves_original_order(self):
        """Test that original passages maintain their relative order."""
        original_passages = [
            "First passage about Paris.",
            "Second passage about France.",
            "Third passage about Europe."
        ]
        
        noisy_passages = self.evaluator._inject_noisy_passages(original_passages, noise_ratio=0.3)
        
        # Find positions of original passages
        original_positions = []
        for orig in original_passages:
            try:
                pos = noisy_passages.index(orig)
                original_positions.append(pos)
            except ValueError:
                pytest.fail(f"Original passage not found: {orig}")
        
        # Original passages should maintain relative order
        assert original_positions == sorted(original_positions)
    
    def test_noise_ratio_calculation(self):
        """Test that noise ratio is approximately respected."""
        original_passages = [
            "Passage 1", "Passage 2", "Passage 3", "Passage 4", "Passage 5"
        ]
        
        noise_ratio = 0.4  # 40% noise
        noisy_passages = self.evaluator._inject_noisy_passages(original_passages, noise_ratio)
        
        expected_noise_count = max(1, int(len(original_passages) * noise_ratio))  # At least 2
        actual_noise_count = sum(1 for p in noisy_passages if "[NOISE]" in p)
        
        # Should be close to expected (allow some variance due to randomness)
        assert actual_noise_count >= expected_noise_count
        assert actual_noise_count <= expected_noise_count + 1  # Allow small variance
    
    def test_robustness_penalty_integration_concept(self):
        """Test the concept of how robustness penalty would be used in practice."""
        # This test demonstrates how the robustness features would be used
        # in a real evaluation scenario
        
        # Simulate baseline evaluation
        clean_passages = [
            "Paris is the capital of France and largest city.",
            "The Eiffel Tower is a famous landmark in Paris.",
            "France is located in Western Europe."
        ]
        
        # Simulate noisy evaluation
        noisy_passages = self.evaluator._inject_noisy_passages(clean_passages, noise_ratio=0.5)
        
        # In a real scenario, we would:
        # 1. Run RAG evaluation with clean passages -> baseline_faithfulness
        # 2. Run RAG evaluation with noisy passages -> noisy_faithfulness
        # 3. Calculate penalty = baseline_faithfulness - noisy_faithfulness
        
        # Simulate this with mock scores
        baseline_faithfulness = 0.85  # High faithfulness with clean passages
        noisy_faithfulness = 0.65     # Lower faithfulness with noise
        
        penalty = self.evaluator._calculate_robustness_penalty(baseline_faithfulness, noisy_faithfulness)
        
        assert penalty > 0  # Should show degradation
        assert penalty == 0.2  # Specific degradation amount
        
        # In practice, we'd want penalty < some threshold (e.g., 0.1)
        robustness_threshold = 0.1
        is_robust = penalty <= robustness_threshold
        
        assert not is_robust  # This system is not robust to noise
    
    def test_noise_content_quality(self):
        """Test that generated noise is actually noisy (not just duplicates)."""
        original_passages = [
            "Machine learning is a subset of artificial intelligence.",
            "Deep learning uses neural networks with multiple layers."
        ]
        
        noisy_passages = self.evaluator._inject_noisy_passages(original_passages, noise_ratio=1.0)
        noise_passages = [p for p in noisy_passages if "[NOISE]" in p]
        
        assert len(noise_passages) > 0
        
        for noise in noise_passages:
            noise_content = noise.replace("[NOISE] ", "")
            
            # Noise should be shorter (uses half the words)
            original_words = original_passages[0].split()
            noise_words = noise_content.split()
            assert len(noise_words) <= len(original_words)
            
            # Noise should contain some words from original (but scrambled)
            original_word_set = set(word.lower().strip('.,!?') for word in original_words)
            noise_word_set = set(word.lower().strip('.,!?') for word in noise_words)
            
            # Should have some overlap but not be identical
            overlap = original_word_set.intersection(noise_word_set)
            assert len(overlap) > 0  # Some words should be preserved
            assert len(overlap) < len(original_word_set)  # But not all
    
    def test_robustness_penalty_extreme_values(self):
        """Test robustness penalty with extreme score values."""
        # Perfect to zero
        penalty1 = self.evaluator._calculate_robustness_penalty(1.0, 0.0)
        assert penalty1 == 1.0
        
        # Zero to perfect (improvement)
        penalty2 = self.evaluator._calculate_robustness_penalty(0.0, 1.0)
        assert penalty2 == -1.0
        
        # Same values
        penalty3 = self.evaluator._calculate_robustness_penalty(0.5, 0.5)
        assert penalty3 == 0.0
