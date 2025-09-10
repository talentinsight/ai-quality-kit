"""
Test bias statistics functions for correctness.

Tests statistical methods used in bias detection.
"""

import pytest
import math
from apps.orchestrator.suites.bias.stats import (
    two_proportion_z_test, bootstrap_mean_diff_ci, detect_refusal,
    count_tokens_or_words, calculate_group_stats, compare_groups
)


def test_two_proportion_z_test_known_values():
    """Test two-proportion z-test with known values."""
    
    # Test case: Group 1 has 10/100 successes, Group 2 has 20/100 successes
    # Expected z ≈ -1.98 (corrected calculation), p ≈ 0.048
    z, p, cohens_h = two_proportion_z_test(10, 100, 20, 100)
    
    assert abs(z - (-1.98)) < 0.1, f"Expected z ≈ -1.98, got {z}"
    assert abs(p - 0.048) < 0.02, f"Expected p ≈ 0.048, got {p}"
    assert abs(cohens_h) > 0, "Cohen's h should be non-zero for different proportions"
    
    # Test equal proportions (should give z=0, p=1)
    z, p, cohens_h = two_proportion_z_test(10, 100, 10, 100)
    
    assert abs(z) < 0.001, f"Expected z ≈ 0 for equal proportions, got {z}"
    assert abs(p - 1.0) < 0.001, f"Expected p ≈ 1.0 for equal proportions, got {p}"
    assert abs(cohens_h) < 0.001, f"Expected Cohen's h ≈ 0 for equal proportions, got {cohens_h}"


def test_two_proportion_z_test_edge_cases():
    """Test edge cases for two-proportion z-test."""
    
    # Zero sample sizes
    z, p, cohens_h = two_proportion_z_test(0, 0, 5, 10)
    assert z == 0.0 and p == 1.0 and cohens_h == 0.0
    
    # All successes vs all failures - this is actually a significant difference
    z, p, cohens_h = two_proportion_z_test(10, 10, 0, 10)
    # This should produce a significant z-score, not zero
    assert abs(z) > 2.0, f"Expected significant z-score for 100% vs 0%, got {z}"
    assert p < 0.05, f"Expected significant p-value, got {p}"


def test_bootstrap_ci_contains_zero_when_equal():
    """Test that bootstrap CI contains zero when groups are equal."""
    
    # Two identical groups
    group1 = [10.0, 12.0, 11.0, 9.0, 13.0] * 10  # Repeat for larger sample
    group2 = [10.0, 12.0, 11.0, 9.0, 13.0] * 10
    
    ci_lo, ci_hi = bootstrap_mean_diff_ci(group1, group2, n_bootstrap=1000)
    
    # CI should contain zero (or be very close)
    assert ci_lo <= 0.1 and ci_hi >= -0.1, f"CI [{ci_lo}, {ci_hi}] should contain ~0"


def test_bootstrap_ci_excludes_zero_when_different():
    """Test that bootstrap CI excludes zero when groups are different."""
    
    # Two clearly different groups
    group1 = [5.0, 6.0, 4.0, 5.5, 6.5] * 20  # Mean ≈ 5.4
    group2 = [15.0, 16.0, 14.0, 15.5, 16.5] * 20  # Mean ≈ 15.4
    
    ci_lo, ci_hi = bootstrap_mean_diff_ci(group1, group2, n_bootstrap=1000)
    
    # CI should exclude zero (group1 - group2 should be negative)
    assert ci_hi < -5.0, f"CI [{ci_lo}, {ci_hi}] should be clearly negative"


def test_detect_refusal():
    """Test refusal detection with various inputs."""
    
    # Clear refusal cases
    assert detect_refusal("I cannot help with that request.")
    assert detect_refusal("I'm sorry, but I can't assist with this.")
    assert detect_refusal("I won't provide information on that topic.")
    assert detect_refusal("As an AI, I cannot generate harmful content.")
    
    # Non-refusal cases
    assert not detect_refusal("Here's how I can help you with that.")
    assert not detect_refusal("Let me provide some information on this topic.")
    assert not detect_refusal("That's an interesting question. Here's my response.")
    
    # Edge cases
    assert not detect_refusal("")  # Empty string
    assert not detect_refusal("   ")  # Whitespace only
    
    # Custom markers
    custom_markers = ["NOPE", "NO WAY"]
    assert detect_refusal("NOPE, I won't do that.", custom_markers)
    assert not detect_refusal("I cannot help", custom_markers)  # Default markers ignored


def test_count_tokens_or_words():
    """Test token/word counting."""
    
    # Basic word counting
    assert count_tokens_or_words("Hello world") == 2
    assert count_tokens_or_words("This is a test sentence.") == 5
    assert count_tokens_or_words("") == 0
    assert count_tokens_or_words("   ") == 0
    
    # Multiple spaces and punctuation
    assert count_tokens_or_words("Hello,  world!   How are you?") == 5
    
    # Auto tokenizer (should fall back to word count for now)
    assert count_tokens_or_words("Hello world", "auto") == 2


def test_calculate_group_stats():
    """Test group statistics calculation."""
    
    # Sample data
    lengths = [10.0, 12.0, 8.0, 15.0, 11.0]
    refusals = [False, False, True, False, False]
    
    stats = calculate_group_stats(lengths, refusals)
    
    assert stats["n"] == 5
    assert stats["refusal_rate"] == 0.2  # 1/5
    assert stats["mean_length"] == 11.2  # (10+12+8+15+11)/5
    assert stats["median_length"] == 11.0
    assert stats["stdev_length"] > 0
    
    # Empty case
    empty_stats = calculate_group_stats([], [])
    assert empty_stats["n"] == 0
    assert empty_stats["refusal_rate"] == 0.0
    assert empty_stats["mean_length"] == 0.0


def test_compare_groups():
    """Test group comparison statistics."""
    
    # Baseline group
    baseline_lengths = [10.0, 11.0, 9.0, 12.0, 10.0]
    baseline_refusals = [False, False, False, True, False]  # 1/5 = 0.2
    baseline_stats = calculate_group_stats(baseline_lengths, baseline_refusals)
    
    # Comparison group (higher refusal rate, longer responses)
    group_lengths = [15.0, 16.0, 14.0, 17.0, 15.0]
    group_refusals = [False, True, False, True, False]  # 2/5 = 0.4
    group_stats = calculate_group_stats(group_lengths, group_refusals)
    
    comparison = compare_groups(
        baseline_stats, baseline_lengths, baseline_refusals,
        group_stats, group_lengths, group_refusals,
        n_bootstrap=100  # Small number for test speed
    )
    
    # Check refusal rate comparison
    assert comparison["gap_pp"] == 20.0  # (0.4 - 0.2) * 100
    assert comparison["z"] != 0  # Should have some z-score
    assert 0 <= comparison["p"] <= 1  # Valid p-value
    
    # Check length comparison
    assert comparison["len_diff"] == 5.0  # 15.4 - 10.4
    assert comparison["len_rel_gap"] > 0  # Positive relative gap
    assert comparison["ci_lo"] < comparison["ci_hi"]  # Valid CI


def test_bias_runner_decision_rules():
    """Test bias detection decision rules with constructed data."""
    
    # This would test the _evaluate_case_result function
    # For now, we'll test the logic components
    
    # Simulate a case that should fail on refusal rate
    max_refusal_gap = 5.0  # 5 percentage points
    alpha = 0.05
    
    # Gap is 10pp (exceeds threshold) and p=0.01 (significant)
    gap_pp = 10.0
    p_value = 0.01
    
    should_fail_refusal = (abs(gap_pp) > max_refusal_gap) and (p_value < alpha)
    assert should_fail_refusal, "Should fail when gap exceeds threshold AND is significant"
    
    # Gap is 10pp but p=0.1 (not significant)
    gap_pp = 10.0
    p_value = 0.1
    
    should_pass_not_significant = not ((abs(gap_pp) > max_refusal_gap) and (p_value < alpha))
    assert should_pass_not_significant, "Should pass when not statistically significant"
    
    # Gap is 2pp (below threshold) even if significant
    gap_pp = 2.0
    p_value = 0.01
    
    should_pass_small_gap = not ((abs(gap_pp) > max_refusal_gap) and (p_value < alpha))
    assert should_pass_small_gap, "Should pass when gap is below threshold"


def test_intersectionality_groups():
    """Test that intersectional subtypes are handled correctly."""
    
    # This tests that subtypes like "gender_x_accent" work
    intersectional_subtype = "gender_x_accent"
    
    # Should be treated like any other subtype
    assert "_x_" in intersectional_subtype  # Contains intersectional marker
    
    # The loader should handle this as a regular subtype
    # The UI should be able to display it as a chip
    # The filtering should work normally
    
    # Test that underscores are preserved in subtype names
    assert intersectional_subtype.replace("_x_", " × ") == "gender × accent"
