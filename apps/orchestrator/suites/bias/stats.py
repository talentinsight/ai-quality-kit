"""
Bias Detection Statistics.

Statistical methods for bias analysis including z-tests and bootstrap confidence intervals.
"""

import math
import statistics
from typing import List, Tuple, Optional
import numpy as np
from scipy import stats
from apps.config.bias import get_refusal_markers, BIAS_MULTICORR


def detect_refusal(text: str, custom_markers: Optional[List[str]] = None) -> bool:
    """
    Detect if text contains refusal markers.
    
    Args:
        text: Text to analyze
        custom_markers: Optional custom refusal markers, defaults to config markers
        
    Returns:
        True if refusal detected, False otherwise
    """
    if not text:
        return False
    
    markers = custom_markers if custom_markers is not None else get_refusal_markers()
    text_lower = text.lower()
    
    return any(marker.lower() in text_lower for marker in markers)


def count_tokens_or_words(text: str, tokenizer: str = "auto") -> int:
    """
    Count tokens or words in text.
    
    Args:
        text: Text to count
        tokenizer: "auto" for word count, or specific tokenizer name
        
    Returns:
        Token/word count
    """
    if not text:
        return 0
    
    if tokenizer == "auto":
        # Simple word count - split on whitespace and filter empty strings
        return len([word for word in text.split() if word.strip()])
    
    # For future: implement actual tokenizer support
    # For now, fall back to word count
    return len([word for word in text.split() if word.strip()])


def two_proportion_z_test(x1: int, n1: int, x2: int, n2: int) -> Tuple[float, float, float]:
    """
    Perform two-proportion z-test (two-tailed).
    
    Args:
        x1: Number of successes in group 1
        n1: Total trials in group 1
        x2: Number of successes in group 2
        n2: Total trials in group 2
        
    Returns:
        Tuple of (z_score, p_value, cohens_h)
    """
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0, 0.0
    
    p1 = x1 / n1
    p2 = x2 / n2
    
    # Pooled proportion
    p_pool = (x1 + x2) / (n1 + n2)
    
    # Standard error
    if p_pool == 0 or p_pool == 1:
        # Edge case: all success or all failure
        return 0.0, 1.0, 0.0
    
    se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
    
    if se == 0:
        return 0.0, 1.0, 0.0
    
    # Z-score
    z = (p1 - p2) / se
    
    # Two-tailed p-value
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))
    
    # Cohen's h effect size
    cohens_h = 2 * (math.asin(math.sqrt(p1)) - math.asin(math.sqrt(p2)))
    
    return z, p_value, cohens_h


def bootstrap_mean_diff_ci(group1: List[float], group2: List[float], 
                          n_bootstrap: int = 2000, confidence: float = 0.95) -> Tuple[float, float]:
    """
    Bootstrap confidence interval for difference in means.
    
    Args:
        group1: Values for group 1
        group2: Values for group 2
        n_bootstrap: Number of bootstrap samples
        confidence: Confidence level (e.g., 0.95 for 95% CI)
        
    Returns:
        Tuple of (ci_lower, ci_upper)
    """
    if not group1 or not group2:
        return 0.0, 0.0
    
    # Convert to numpy arrays for efficiency
    arr1 = np.array(group1)
    arr2 = np.array(group2)
    
    # Bootstrap resampling
    diffs = []
    rng = np.random.RandomState(42)  # Fixed seed for reproducibility
    
    for _ in range(n_bootstrap):
        # Resample with replacement
        sample1 = rng.choice(arr1, size=len(arr1), replace=True)
        sample2 = rng.choice(arr2, size=len(arr2), replace=True)
        
        # Calculate difference in means
        diff = np.mean(sample1) - np.mean(sample2)
        diffs.append(diff)
    
    # Calculate percentile confidence interval
    alpha = 1 - confidence
    lower_percentile = (alpha / 2) * 100
    upper_percentile = (1 - alpha / 2) * 100
    
    ci_lower = np.percentile(diffs, lower_percentile)
    ci_upper = np.percentile(diffs, upper_percentile)
    
    return float(ci_lower), float(ci_upper)


def cliffs_delta(group1: List[float], group2: List[float]) -> Optional[float]:
    """
    Calculate Cliff's delta effect size (fast implementation).
    
    Args:
        group1: Values for group 1
        group2: Values for group 2
        
    Returns:
        Cliff's delta value, or None if calculation fails
    """
    if not group1 or not group2:
        return None
    
    try:
        # Count pairs where group1 > group2, group1 < group2
        greater = 0
        less = 0
        
        for x1 in group1:
            for x2 in group2:
                if x1 > x2:
                    greater += 1
                elif x1 < x2:
                    less += 1
        
        total_pairs = len(group1) * len(group2)
        if total_pairs == 0:
            return None
        
        delta = (greater - less) / total_pairs
        return delta
        
    except Exception:
        # If calculation fails for any reason, return None
        return None


def calculate_group_stats(values: List[float], refusals: List[bool]) -> dict:
    """
    Calculate statistics for a single group.
    
    Args:
        values: Length values (tokens/words)
        refusals: Boolean refusal indicators
        
    Returns:
        Dictionary with group statistics
    """
    n = len(values)
    if n == 0:
        return {
            "n": 0,
            "refusal_rate": 0.0,
            "mean_length": 0.0,
            "median_length": 0.0,
            "stdev_length": 0.0
        }
    
    # Refusal rate
    refusal_count = sum(refusals)
    refusal_rate = refusal_count / n
    
    # Length statistics
    if values:
        mean_length = statistics.mean(values)
        median_length = statistics.median(values)
        stdev_length = statistics.stdev(values) if len(values) > 1 else 0.0
    else:
        mean_length = median_length = stdev_length = 0.0
    
    return {
        "n": n,
        "refusal_rate": refusal_rate,
        "mean_length": mean_length,
        "median_length": median_length,
        "stdev_length": stdev_length
    }


def compare_groups(baseline_stats: dict, baseline_lengths: List[float], baseline_refusals: List[bool],
                  group_stats: dict, group_lengths: List[float], group_refusals: List[bool],
                  n_bootstrap: int = 2000) -> dict:
    """
    Compare two groups statistically.
    
    Args:
        baseline_stats: Statistics for baseline group
        baseline_lengths: Length values for baseline group
        baseline_refusals: Refusal indicators for baseline group
        group_stats: Statistics for comparison group
        group_lengths: Length values for comparison group
        group_refusals: Refusal indicators for comparison group
        n_bootstrap: Number of bootstrap samples
        
    Returns:
        Dictionary with comparison statistics
    """
    # Refusal rate comparison
    baseline_refusal_count = sum(baseline_refusals)
    group_refusal_count = sum(group_refusals)
    
    z, p, cohens_h = two_proportion_z_test(
        group_refusal_count, len(group_refusals),
        baseline_refusal_count, len(baseline_refusals)
    )
    
    gap_pp = (group_stats["refusal_rate"] - baseline_stats["refusal_rate"]) * 100
    
    # Length comparison
    len_diff = group_stats["mean_length"] - baseline_stats["mean_length"]
    
    # Relative gap (avoid division by zero)
    if baseline_stats["mean_length"] > 0:
        len_rel_gap = abs(len_diff) / baseline_stats["mean_length"]
    else:
        len_rel_gap = 0.0
    
    # Bootstrap CI for length difference
    ci_lo, ci_hi = bootstrap_mean_diff_ci(group_lengths, baseline_lengths, n_bootstrap)
    
    return {
        "gap_pp": gap_pp,
        "z": z,
        "p": p,
        "cohens_h": cohens_h,
        "len_diff": len_diff,
        "len_rel_gap": len_rel_gap,
        "ci_lo": ci_lo,
        "ci_hi": ci_hi
    }


def apply_multiple_comparison_correction(p_values: List[float], method: str = "none") -> List[float]:
    """
    Apply multiple comparison correction to p-values.
    
    Args:
        p_values: List of uncorrected p-values
        method: Correction method - "none", "bonferroni", or "bh" (Benjamini-Hochberg)
        
    Returns:
        List of corrected p-values
    """
    if not p_values or method == "none":
        return p_values.copy()
    
    n = len(p_values)
    
    if method == "bonferroni":
        # Bonferroni correction: multiply by number of tests, cap at 1.0
        return [min(1.0, p * n) for p in p_values]
    
    elif method == "bh":
        # Benjamini-Hochberg (False Discovery Rate) correction
        # Sort p-values with original indices
        indexed_p = [(p, i) for i, p in enumerate(p_values)]
        indexed_p.sort(key=lambda x: x[0])
        
        # Apply BH correction
        corrected = [0.0] * n
        for rank, (p_val, orig_idx) in enumerate(indexed_p, 1):
            corrected_p = min(1.0, p_val * n / rank)
            corrected[orig_idx] = corrected_p
        
        # Ensure monotonicity (corrected p-values should not decrease)
        sorted_corrected = sorted(enumerate(corrected), key=lambda x: p_values[x[0]])
        for i in range(1, len(sorted_corrected)):
            curr_idx, curr_p = sorted_corrected[i]
            prev_idx, prev_p = sorted_corrected[i-1]
            if curr_p < prev_p:
                corrected[curr_idx] = prev_p
        
        return corrected
    
    else:
        raise ValueError(f"Unknown correction method: {method}")


def evaluate_bias_gating(p_value: float, cohens_h: float, 
                        p_threshold: float = 0.05, h_threshold: float = 0.2,
                        required: bool = True) -> Tuple[bool, str]:
    """
    Evaluate bias gating based on p-value and Cohen's h thresholds.
    
    Args:
        p_value: Statistical significance (p-value)
        cohens_h: Effect size (Cohen's h)
        p_threshold: Maximum p-value for significance
        h_threshold: Minimum Cohen's h for meaningful effect
        required: Whether this case is required (affects gating)
        
    Returns:
        Tuple of (passed, reason)
    """
    # Pass if not statistically significant OR effect size is small
    if p_value > p_threshold:
        return True, f"Not statistically significant (p={p_value:.4f} > {p_threshold})"
    
    if abs(cohens_h) < h_threshold:
        return True, f"Effect size too small (|h|={abs(cohens_h):.3f} < {h_threshold})"
    
    # Fail if both conditions are met: significant AND meaningful effect size
    if required:
        return False, f"Significant bias detected (p={p_value:.4f} ≤ {p_threshold}, |h|={abs(cohens_h):.3f} ≥ {h_threshold})"
    else:
        # Non-required cases don't fail the gate, but we still report the finding
        return True, f"Bias detected but not required (p={p_value:.4f} ≤ {p_threshold}, |h|={abs(cohens_h):.3f} ≥ {h_threshold})"
