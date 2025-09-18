"""
Test Performance Metrics and Statistics.

Tests for performance metrics calculation, percentiles, and segmentation.
"""

import pytest
from apps.orchestrator.suites.performance.metrics import (
    RequestResult, calculate_percentiles, calculate_scenario_metrics,
    segment_results, calculate_segmented_metrics, get_p95_for_category
)


def test_calculate_percentiles():
    """Test percentile calculations."""
    
    # Test with known values
    values = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    
    metrics = calculate_percentiles(values)
    
    assert metrics.p50 == 550.0  # Median
    assert metrics.p90 == 910.0  # 90th percentile
    assert abs(metrics.p95 - 955.0) < 0.1  # 95th percentile (floating point tolerance)
    assert abs(metrics.p99 - 991.0) < 0.1  # 99th percentile (floating point tolerance)
    assert metrics.max == 1000.0
    assert metrics.mean == 550.0
    assert metrics.std > 0  # Should have some standard deviation


def test_calculate_percentiles_empty():
    """Test percentile calculations with empty list."""
    
    metrics = calculate_percentiles([])
    
    assert metrics.p50 == 0.0
    assert metrics.p90 == 0.0
    assert metrics.p95 == 0.0
    assert metrics.p99 == 0.0
    assert metrics.max == 0.0
    assert metrics.mean == 0.0
    assert metrics.std == 0.0


def test_calculate_percentiles_single_value():
    """Test percentile calculations with single value."""
    
    metrics = calculate_percentiles([500.0])
    
    assert metrics.p50 == 500.0
    assert metrics.p90 == 500.0
    assert metrics.p95 == 500.0
    assert metrics.p99 == 500.0
    assert metrics.max == 500.0
    assert metrics.mean == 500.0
    assert metrics.std == 0.0


def test_calculate_scenario_metrics():
    """Test scenario metrics calculation."""
    
    # Create test results
    results = [
        RequestResult(latency_ms=100, success=True, tokens_out=50, cost=0.01),
        RequestResult(latency_ms=200, success=True, tokens_out=60, cost=0.012),
        RequestResult(latency_ms=300, success=False, timeout=False),  # Error
        RequestResult(latency_ms=400, success=False, timeout=True),   # Timeout
        RequestResult(latency_ms=150, success=True, tokens_out=55, cost=0.011),
    ]
    
    wall_time_sec = 10.0
    
    metrics = calculate_scenario_metrics(results, wall_time_sec)
    
    # Check counts
    assert metrics.total == 5
    assert metrics.completed == 3
    assert metrics.errors == 1
    assert metrics.timeouts == 1
    
    # Check rates
    assert metrics.error_rate == 0.2  # 1/5
    assert metrics.timeout_rate == 0.2  # 1/5
    
    # Check throughput (completed requests per second)
    assert metrics.throughput_rps == 0.3  # 3/10
    
    # Check latency metrics (only successful requests: 100, 200, 150)
    assert metrics.latency_ms.mean == 150.0  # (100+200+150)/3
    
    # Check token metrics
    assert metrics.tokens_out_total == 165  # 50+60+55
    assert metrics.tokens_out_rate == 16.5  # 165/10
    assert metrics.tokens_per_sec == 16.5
    
    # Check cost metrics
    assert abs(metrics.cost_total - 0.033) < 0.001  # 0.01+0.012+0.011 (floating point tolerance)
    assert abs(metrics.cost_per_request - 0.011) < 0.001  # 0.033/3 (floating point tolerance)


def test_segment_results():
    """Test result segmentation into cold and warm phases."""
    
    results = [
        RequestResult(latency_ms=300, success=True, phase="COLD"),   # Cold 1
        RequestResult(latency_ms=280, success=True, phase="COLD"),   # Cold 2
        RequestResult(latency_ms=250, success=True, phase="WARM"),   # Warmup (excluded)
        RequestResult(latency_ms=200, success=True, phase="WARM"),   # Warmup (excluded)
        RequestResult(latency_ms=150, success=True, phase="WARM"),   # Warm 1
        RequestResult(latency_ms=140, success=True, phase="WARM"),   # Warm 2
        RequestResult(latency_ms=160, success=True, phase="WARM"),   # Warm 3
    ]
    
    cold_n = 2
    warmup_exclude_n = 4  # Exclude first 4 (2 cold + 2 warmup)
    
    cold_results, warm_results = segment_results(results, cold_n, warmup_exclude_n)
    
    # Cold phase: first 2 results
    assert len(cold_results) == 2
    assert cold_results[0].latency_ms == 300
    assert cold_results[1].latency_ms == 280
    
    # Warm phase: results after excluding first 4
    assert len(warm_results) == 3
    assert warm_results[0].latency_ms == 150
    assert warm_results[1].latency_ms == 140
    assert warm_results[2].latency_ms == 160


def test_calculate_segmented_metrics():
    """Test segmented metrics calculation."""
    
    results = [
        RequestResult(latency_ms=500, success=True),  # Cold 1
        RequestResult(latency_ms=450, success=True),  # Cold 2
        RequestResult(latency_ms=200, success=True),  # Warm 1
        RequestResult(latency_ms=180, success=True),  # Warm 2
        RequestResult(latency_ms=190, success=True),  # Warm 3
        RequestResult(latency_ms=170, success=True),  # Warm 4
    ]
    
    wall_time_sec = 12.0
    cold_n = 2
    warmup_exclude_n = 2  # Same as cold_n, no additional warmup exclusion
    
    metrics = calculate_segmented_metrics(
        results, wall_time_sec, cold_n, warmup_exclude_n
    )
    
    # Should have overall, cold, and warm metrics
    assert "overall" in metrics
    assert "cold" in metrics
    assert "warm" in metrics
    
    # Overall metrics
    assert metrics["overall"].total == 6
    assert metrics["overall"].completed == 6
    
    # Cold metrics (first 2 results)
    assert metrics["cold"].total == 2
    assert metrics["cold"].latency_ms.mean == 475.0  # (500+450)/2
    
    # Warm metrics (last 4 results)
    assert metrics["warm"].total == 4
    assert metrics["warm"].latency_ms.mean == 185.0  # (200+180+190+170)/4


def test_get_p95_for_category():
    """Test P95 selection based on category."""
    
    # Create mock metrics
    metrics = {
        "overall": type('MockMetrics', (), {
            'latency_ms': type('MockLatency', (), {'p95': 300.0})()
        })(),
        "cold": type('MockMetrics', (), {
            'latency_ms': type('MockLatency', (), {'p95': 500.0})()
        })(),
        "warm": type('MockMetrics', (), {
            'latency_ms': type('MockLatency', (), {'p95': 200.0})()
        })()
    }
    
    # Test cold_start category uses cold P95
    assert get_p95_for_category(metrics, "cold_start") == 500.0
    
    # Test warm category uses warm P95
    assert get_p95_for_category(metrics, "warm") == 200.0
    
    # Test other categories use overall P95
    assert get_p95_for_category(metrics, "throughput") == 300.0
    assert get_p95_for_category(metrics, "stress") == 300.0
    assert get_p95_for_category(metrics, "memory") == 300.0


def test_get_p95_for_category_missing_segments():
    """Test P95 selection when segmented metrics are missing."""
    
    # Metrics with only overall
    metrics = {
        "overall": type('MockMetrics', (), {
            'latency_ms': type('MockLatency', (), {'p95': 300.0})()
        })()
    }
    
    # Should fall back to overall for all categories
    assert get_p95_for_category(metrics, "cold_start") == 300.0
    assert get_p95_for_category(metrics, "warm") == 300.0
    assert get_p95_for_category(metrics, "throughput") == 300.0


def test_request_result_creation():
    """Test RequestResult object creation and attributes."""
    
    # Test successful request
    result = RequestResult(
        latency_ms=250.5,
        success=True,
        timeout=False,
        tokens_out=75,
        cost=0.015,
        phase="WARM"
    )
    
    assert result.latency_ms == 250.5
    assert result.success is True
    assert result.timeout is False
    assert result.tokens_out == 75
    assert result.cost == 0.015
    assert result.phase == "WARM"
    
    # Test failed request
    failed_result = RequestResult(
        latency_ms=1000.0,
        success=False,
        timeout=True
    )
    
    assert failed_result.latency_ms == 1000.0
    assert failed_result.success is False
    assert failed_result.timeout is True
    assert failed_result.tokens_out == 0  # Default
    assert failed_result.cost == 0.0  # Default
    assert failed_result.phase is None  # Default


def test_metrics_with_memory_and_cpu():
    """Test metrics calculation with memory and CPU data."""
    
    results = [
        RequestResult(latency_ms=100, success=True),
        RequestResult(latency_ms=200, success=True),
    ]
    
    wall_time_sec = 5.0
    memory_peak_mb = 256.5
    cpu_peak_pct = 85.2
    
    metrics = calculate_scenario_metrics(
        results, wall_time_sec, memory_peak_mb, cpu_peak_pct
    )
    
    assert metrics.memory_peak_mb == 256.5
    assert metrics.cpu_peak_pct == 85.2
    assert metrics.total == 2
    assert metrics.completed == 2


def test_metrics_edge_cases():
    """Test metrics calculation edge cases."""
    
    # Empty results
    empty_metrics = calculate_scenario_metrics([], 10.0)
    assert empty_metrics.total == 0
    assert empty_metrics.completed == 0
    assert empty_metrics.throughput_rps == 0.0
    
    # All failed requests
    failed_results = [
        RequestResult(latency_ms=1000, success=False),
        RequestResult(latency_ms=2000, success=False, timeout=True),
    ]
    
    failed_metrics = calculate_scenario_metrics(failed_results, 5.0)
    assert failed_metrics.total == 2
    assert failed_metrics.completed == 0
    assert failed_metrics.errors == 1
    assert failed_metrics.timeouts == 1
    assert failed_metrics.error_rate == 0.5
    assert failed_metrics.timeout_rate == 0.5
    assert failed_metrics.throughput_rps == 0.0
    
    # Zero wall time (should handle gracefully)
    zero_time_metrics = calculate_scenario_metrics([
        RequestResult(latency_ms=100, success=True)
    ], 0.0)
    assert zero_time_metrics.throughput_rps == 0.0
