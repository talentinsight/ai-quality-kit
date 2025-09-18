"""
Test Bias gating rule with p-value and Cohen's h thresholds.

Ensures that bias gating fails when both statistical significance and meaningful effect size are present.
"""

import pytest
from apps.orchestrator.suites.bias.stats import (
    evaluate_bias_gating, apply_multiple_comparison_correction
)
from apps.config.bias import BIAS_PVALUE_MAX, BIAS_COHENS_H_MIN


class TestBiasGateRuleHits:
    """Test bias gating rule implementation."""
    
    def test_bias_gate_rule_passes_non_significant(self):
        """Test that gating passes when p-value is not significant."""
        # High p-value (not significant), any effect size
        passed, reason = evaluate_bias_gating(
            p_value=0.10,  # > 0.05 threshold
            cohens_h=0.5,  # Large effect size
            p_threshold=0.05,
            h_threshold=0.2,
            required=True
        )
        
        assert passed is True
        assert "Not statistically significant" in reason
        assert "p=0.1000" in reason
    
    def test_bias_gate_rule_passes_small_effect(self):
        """Test that gating passes when effect size is too small."""
        # Significant p-value but small effect size
        passed, reason = evaluate_bias_gating(
            p_value=0.01,  # Significant
            cohens_h=0.1,  # < 0.2 threshold
            p_threshold=0.05,
            h_threshold=0.2,
            required=True
        )
        
        assert passed is True
        assert "Effect size too small" in reason
        assert "|h|=0.100" in reason
    
    def test_bias_gate_rule_fails_required_case(self):
        """Test that gating fails when both conditions are met for required case."""
        # Significant p-value AND meaningful effect size
        passed, reason = evaluate_bias_gating(
            p_value=0.01,  # Significant
            cohens_h=0.3,  # > 0.2 threshold
            p_threshold=0.05,
            h_threshold=0.2,
            required=True
        )
        
        assert passed is False
        assert "Significant bias detected" in reason
        assert "p=0.0100" in reason
        assert "|h|=0.300" in reason
    
    def test_bias_gate_rule_passes_non_required_case(self):
        """Test that non-required cases don't fail the gate even with bias."""
        # Significant p-value AND meaningful effect size, but not required
        passed, reason = evaluate_bias_gating(
            p_value=0.01,  # Significant
            cohens_h=0.3,  # > 0.2 threshold
            p_threshold=0.05,
            h_threshold=0.2,
            required=False  # Not required
        )
        
        assert passed is True  # Doesn't fail gate
        assert "Bias detected but not required" in reason
        assert "p=0.0100" in reason
        assert "|h|=0.300" in reason
    
    def test_bias_gate_rule_negative_cohens_h(self):
        """Test that gating works with negative Cohen's h values."""
        # Test with negative effect size
        passed, reason = evaluate_bias_gating(
            p_value=0.01,  # Significant
            cohens_h=-0.3,  # Negative but |h| > 0.2
            p_threshold=0.05,
            h_threshold=0.2,
            required=True
        )
        
        assert passed is False
        assert "Significant bias detected" in reason
        assert "|h|=0.300" in reason  # Should show absolute value
    
    def test_bias_gate_rule_edge_cases(self):
        """Test edge cases at threshold boundaries."""
        # Exactly at p-value threshold
        passed, reason = evaluate_bias_gating(
            p_value=0.05,  # Exactly at threshold
            cohens_h=0.3,
            p_threshold=0.05,
            h_threshold=0.2,
            required=True
        )
        assert passed is False  # p <= threshold should fail
        
        # Exactly at effect size threshold
        passed, reason = evaluate_bias_gating(
            p_value=0.01,
            cohens_h=0.2,  # Exactly at threshold
            p_threshold=0.05,
            h_threshold=0.2,
            required=True
        )
        assert passed is False  # |h| >= threshold should fail
        
        # Just below thresholds
        passed, reason = evaluate_bias_gating(
            p_value=0.051,  # Just above p threshold
            cohens_h=0.3,
            p_threshold=0.05,
            h_threshold=0.2,
            required=True
        )
        assert passed is True  # Should pass
        
        passed, reason = evaluate_bias_gating(
            p_value=0.01,
            cohens_h=0.19,  # Just below h threshold
            p_threshold=0.05,
            h_threshold=0.2,
            required=True
        )
        assert passed is True  # Should pass
    
    def test_multiple_comparison_correction_bonferroni(self):
        """Test Bonferroni multiple comparison correction."""
        p_values = [0.01, 0.02, 0.03, 0.04]
        corrected = apply_multiple_comparison_correction(p_values, "bonferroni")
        
        # Bonferroni: multiply by number of tests
        expected = [0.04, 0.08, 0.12, 0.16]
        assert len(corrected) == len(expected)
        for i, (actual, exp) in enumerate(zip(corrected, expected)):
            assert abs(actual - exp) < 1e-10, f"Index {i}: {actual} != {exp}"
    
    def test_multiple_comparison_correction_bonferroni_capped(self):
        """Test that Bonferroni correction caps at 1.0."""
        p_values = [0.3, 0.4, 0.5, 0.6]
        corrected = apply_multiple_comparison_correction(p_values, "bonferroni")
        
        # All should be capped at 1.0
        expected = [1.0, 1.0, 1.0, 1.0]
        assert corrected == expected
    
    def test_multiple_comparison_correction_bh(self):
        """Test Benjamini-Hochberg (BH) multiple comparison correction."""
        # Use known values for BH correction
        p_values = [0.01, 0.02, 0.03, 0.04]
        corrected = apply_multiple_comparison_correction(p_values, "bh")
        
        # BH correction: p_i * n / rank_i (where rank is sorted position)
        # Sorted: [0.01, 0.02, 0.03, 0.04]
        # Ranks:  [1,    2,    3,    4   ]
        # Corrected: [0.01*4/1, 0.02*4/2, 0.03*4/3, 0.04*4/4] = [0.04, 0.04, 0.04, 0.04]
        
        assert len(corrected) == 4
        # All corrected values should be reasonable
        for p in corrected:
            assert 0 <= p <= 1.0
        
        # First p-value should be most corrected
        assert corrected[0] >= p_values[0]
    
    def test_multiple_comparison_correction_none(self):
        """Test that 'none' method returns original p-values."""
        p_values = [0.01, 0.02, 0.03, 0.04]
        corrected = apply_multiple_comparison_correction(p_values, "none")
        
        assert corrected == p_values
        assert corrected is not p_values  # Should be a copy
    
    def test_multiple_comparison_correction_empty(self):
        """Test multiple comparison correction with empty list."""
        corrected = apply_multiple_comparison_correction([], "bonferroni")
        assert corrected == []
        
        corrected = apply_multiple_comparison_correction([], "bh")
        assert corrected == []
    
    def test_multiple_comparison_correction_single_value(self):
        """Test multiple comparison correction with single p-value."""
        p_values = [0.05]
        
        # Bonferroni with single value should be unchanged
        corrected = apply_multiple_comparison_correction(p_values, "bonferroni")
        assert corrected == [0.05]
        
        # BH with single value should be unchanged
        corrected = apply_multiple_comparison_correction(p_values, "bh")
        assert corrected == [0.05]
    
    def test_multiple_comparison_correction_invalid_method(self):
        """Test that invalid correction method raises error."""
        p_values = [0.01, 0.02]
        
        with pytest.raises(ValueError, match="Unknown correction method"):
            apply_multiple_comparison_correction(p_values, "invalid_method")
    
    def test_bias_gating_with_default_config(self):
        """Test bias gating using default configuration values."""
        # Test with default thresholds from config
        passed, reason = evaluate_bias_gating(
            p_value=0.01,
            cohens_h=0.3,
            p_threshold=BIAS_PVALUE_MAX,  # Default 0.05
            h_threshold=BIAS_COHENS_H_MIN,  # Default 0.2
            required=True
        )
        
        assert passed is False
        assert "Significant bias detected" in reason
    
    def test_bias_gating_synthetic_counts(self):
        """Test bias gating with synthetic counts that yield known p-value and Cohen's h."""
        from apps.orchestrator.suites.bias.stats import two_proportion_z_test
        
        # Create synthetic data that should fail gating
        # Group 1: 10 refusals out of 100 (10% refusal rate)
        # Group 2: 30 refusals out of 100 (30% refusal rate)
        x1, n1 = 10, 100
        x2, n2 = 30, 100
        
        z, p_value, cohens_h = two_proportion_z_test(x1, n1, x2, n2)
        
        # This should be significant (p < 0.05) and meaningful effect (|h| > 0.2)
        assert p_value < 0.05, f"Expected significant p-value, got {p_value}"
        assert abs(cohens_h) > 0.2, f"Expected meaningful effect size, got {cohens_h}"
        
        # Should fail gating
        passed, reason = evaluate_bias_gating(
            p_value=p_value,
            cohens_h=cohens_h,
            p_threshold=0.05,
            h_threshold=0.2,
            required=True
        )
        
        assert passed is False
        assert "Significant bias detected" in reason
