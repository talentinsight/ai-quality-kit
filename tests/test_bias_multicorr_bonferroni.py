"""
Test Bias multiple comparison correction with Bonferroni method.

Verifies that Bonferroni correction is properly applied to multiple bias comparisons.
"""

import pytest
from apps.orchestrator.suites.bias.stats import apply_multiple_comparison_correction


class TestBiasMulticorrBonferroni:
    """Test Bonferroni multiple comparison correction for bias testing."""
    
    def test_bias_multicorr_bonferroni_two_cases(self):
        """Test Bonferroni correction with two test cases."""
        # Two p-values from two bias comparisons
        p_values = [0.02, 0.03]
        corrected = apply_multiple_comparison_correction(p_values, "bonferroni")
        
        # Bonferroni: multiply each p-value by number of tests
        expected = [0.02 * 2, 0.03 * 2]  # [0.04, 0.06]
        
        assert len(corrected) == 2
        assert abs(corrected[0] - 0.04) < 1e-10
        assert abs(corrected[1] - 0.06) < 1e-10
    
    def test_bias_multicorr_bonferroni_multiple_cases(self):
        """Test Bonferroni correction with multiple test cases."""
        # Five p-values from five bias comparisons
        p_values = [0.01, 0.02, 0.03, 0.04, 0.05]
        corrected = apply_multiple_comparison_correction(p_values, "bonferroni")
        
        # Bonferroni: multiply each p-value by 5
        expected = [0.05, 0.10, 0.15, 0.20, 0.25]
        
        assert len(corrected) == 5
        for i, (actual, exp) in enumerate(zip(corrected, expected)):
            assert abs(actual - exp) < 1e-10, f"Index {i}: {actual} != {exp}"
    
    def test_bias_multicorr_bonferroni_capping(self):
        """Test that Bonferroni correction caps values at 1.0."""
        # High p-values that would exceed 1.0 after correction
        p_values = [0.4, 0.5, 0.6, 0.7, 0.8]
        corrected = apply_multiple_comparison_correction(p_values, "bonferroni")
        
        # All should be capped at 1.0 (since 0.4*5=2.0 > 1.0, etc.)
        expected = [1.0, 1.0, 1.0, 1.0, 1.0]
        
        assert corrected == expected
    
    def test_bias_multicorr_bonferroni_mixed_significance(self):
        """Test Bonferroni correction with mixed significant/non-significant p-values."""
        # Mix of low and high p-values
        p_values = [0.001, 0.01, 0.05, 0.1, 0.2]
        corrected = apply_multiple_comparison_correction(p_values, "bonferroni")
        
        # Multiply by 5
        expected = [0.005, 0.05, 0.25, 0.5, 1.0]  # Last one capped
        
        assert len(corrected) == 5
        for i, (actual, exp) in enumerate(zip(corrected, expected)):
            assert abs(actual - exp) < 1e-10, f"Index {i}: {actual} != {exp}"
    
    def test_bias_multicorr_bonferroni_preserves_order(self):
        """Test that Bonferroni correction preserves relative order."""
        # Unsorted p-values
        p_values = [0.03, 0.01, 0.05, 0.02, 0.04]
        corrected = apply_multiple_comparison_correction(p_values, "bonferroni")
        
        # Should preserve original order
        expected = [0.15, 0.05, 0.25, 0.10, 0.20]
        
        assert len(corrected) == 5
        for i, (actual, exp) in enumerate(zip(corrected, expected)):
            assert abs(actual - exp) < 1e-10, f"Index {i}: {actual} != {exp}"
        
        # Verify relative order is preserved
        original_order = [i for i, _ in sorted(enumerate(p_values), key=lambda x: x[1])]
        corrected_order = [i for i, _ in sorted(enumerate(corrected), key=lambda x: x[1])]
        assert original_order == corrected_order
    
    def test_bias_multicorr_bonferroni_edge_cases(self):
        """Test Bonferroni correction edge cases."""
        # Single p-value
        corrected = apply_multiple_comparison_correction([0.05], "bonferroni")
        assert corrected == [0.05]  # No change with single test
        
        # Zero p-value
        corrected = apply_multiple_comparison_correction([0.0, 0.01], "bonferroni")
        assert corrected == [0.0, 0.02]  # 0.0 stays 0.0
        
        # p-value of 1.0
        corrected = apply_multiple_comparison_correction([1.0, 0.5], "bonferroni")
        assert corrected == [1.0, 1.0]  # Both capped at 1.0
    
    def test_bias_multicorr_bonferroni_vs_bh_comparison(self):
        """Compare Bonferroni vs Benjamini-Hochberg corrections."""
        p_values = [0.01, 0.02, 0.03, 0.04, 0.05]
        
        bonferroni = apply_multiple_comparison_correction(p_values, "bonferroni")
        bh = apply_multiple_comparison_correction(p_values, "bh")
        
        # Bonferroni should be more conservative (higher corrected p-values)
        for i in range(len(p_values)):
            assert bonferroni[i] >= bh[i], f"Bonferroni should be >= BH at index {i}"
    
    def test_bias_multicorr_bonferroni_realistic_scenario(self):
        """Test Bonferroni correction in realistic bias testing scenario."""
        # Simulate p-values from bias comparisons across different demographic groups
        # E.g., comparing gender, age, race groups against baseline
        p_values = [
            0.02,   # Gender comparison - significant
            0.08,   # Age comparison - not significant
            0.001,  # Race comparison - highly significant
            0.15,   # Accent comparison - not significant
            0.04    # Intersectional comparison - borderline
        ]
        
        corrected = apply_multiple_comparison_correction(p_values, "bonferroni")
        
        # With 5 comparisons, multiply by 5
        expected = [0.10, 0.40, 0.005, 0.75, 0.20]
        
        assert len(corrected) == 5
        for i, (actual, exp) in enumerate(zip(corrected, expected)):
            assert abs(actual - exp) < 1e-10, f"Index {i}: {actual} != {exp}"
        
        # Check which remain significant after correction (α = 0.05)
        significant_after_correction = [p <= 0.05 for p in corrected]
        expected_significant = [False, False, True, False, False]  # Only race remains significant
        
        assert significant_after_correction == expected_significant
    
    def test_bias_multicorr_bonferroni_integration_with_gating(self):
        """Test integration of Bonferroni correction with bias gating logic."""
        from apps.orchestrator.suites.bias.stats import evaluate_bias_gating
        
        # Original p-values that would be significant
        original_p_values = [0.02, 0.03, 0.04]
        
        # Apply Bonferroni correction
        corrected_p_values = apply_multiple_comparison_correction(original_p_values, "bonferroni")
        # Expected: [0.06, 0.09, 0.12] - all now non-significant
        
        # Test gating with corrected p-values
        for i, corrected_p in enumerate(corrected_p_values):
            passed, reason = evaluate_bias_gating(
                p_value=corrected_p,
                cohens_h=0.3,  # Large effect size
                p_threshold=0.05,
                h_threshold=0.2,
                required=True
            )
            
            # All should pass because corrected p-values are > 0.05
            assert passed is True, f"Index {i}: Expected to pass with corrected p={corrected_p}"
            assert "Not statistically significant" in reason
    
    def test_bias_multicorr_bonferroni_mathematical_properties(self):
        """Test mathematical properties of Bonferroni correction."""
        p_values = [0.01, 0.02, 0.03]
        corrected = apply_multiple_comparison_correction(p_values, "bonferroni")
        
        # Property 1: Corrected p-values should be >= original
        for orig, corr in zip(p_values, corrected):
            assert corr >= orig, f"Corrected {corr} should be >= original {orig}"
        
        # Property 2: All corrected p-values should be <= 1.0
        for corr in corrected:
            assert corr <= 1.0, f"Corrected p-value {corr} should be <= 1.0"
        
        # Property 3: If original p-value is 0, corrected should be 0
        zero_test = apply_multiple_comparison_correction([0.0, 0.01], "bonferroni")
        assert zero_test[0] == 0.0
        
        # Property 4: Correction factor equals number of tests
        n_tests = len(p_values)
        for orig, corr in zip(p_values, corrected):
            if corr < 1.0:  # Only check non-capped values
                assert abs(corr - orig * n_tests) < 1e-10
