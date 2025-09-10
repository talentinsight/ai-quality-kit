"""
Test Performance Integration.

Integration tests for the complete performance testing system.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from apps.orchestrator.suites.performance.runner import run_performance_suite
from apps.orchestrator.suites.performance.harness import LoadHarness
from apps.orchestrator.suites.performance.loader import validate_perf_content


def test_perf_validation_integration():
    """Test end-to-end performance dataset validation."""
    
    valid_dataset = """
scenarios:
  - id: "integration_cold_start"
    category: "cold_start"
    subtype: "baseline"
    description: "Integration test for cold start"
    required: true
    request:
      input_template: "What is the capital of France?"
      repeats: 3
    load:
      mode: "closed_loop"
      concurrency: 1
      duration_sec: 20
      think_time_ms: 500
    segmentation:
      cold_n: 2
      warmup_exclude_n: 0
      phase_headers: true
    thresholds:
      p95_ms_max: 2500
      error_rate_max: 0.05

  - id: "integration_throughput"
    category: "throughput"
    subtype: "sustained"
    description: "Integration test for throughput"
    required: true
    request:
      input_template: "Explain machine learning in simple terms"
    load:
      mode: "open_loop"
      rate_rps: 5
      duration_sec: 30
    segmentation:
      cold_n: 1
      warmup_exclude_n: 3
    thresholds:
      p95_ms_max: 2000
      throughput_min_rps: 4
      tokens_per_sec_min: 20

  - id: "integration_memory"
    category: "memory"
    subtype: "soak"
    description: "Integration test for memory usage"
    required: false
    request:
      input_template: "Write a detailed essay about renewable energy"
    load:
      mode: "closed_loop"
      concurrency: 4
      duration_sec: 60
    thresholds:
      memory_peak_mb_max: 256
      p95_ms_max: 3000
"""
    
    # Validate the dataset
    validation_result = validate_perf_content(valid_dataset)
    
    assert validation_result.valid is True
    assert validation_result.format == "yaml"
    assert len(validation_result.counts_by_category) == 3
    assert validation_result.counts_by_category["cold_start"] == 1
    assert validation_result.counts_by_category["throughput"] == 1
    assert validation_result.counts_by_category["memory"] == 1
    assert validation_result.required_count == 2
    
    # Check taxonomy
    expected_taxonomy = {
        "cold_start": ["baseline"],
        "throughput": ["sustained"],
        "memory": ["soak"]
    }
    assert validation_result.taxonomy == expected_taxonomy
    
    # Should have some warnings about short durations
    assert len(validation_result.warnings) > 0


def test_perf_runner_mock_execution():
    """Test performance runner with mock client execution."""
    
    # Mock client that returns predictable results
    mock_client = Mock()
    mock_client.return_value = "This is a mock response with some tokens."
    
    dataset_content = """
scenarios:
  - id: "mock_test"
    category: "warm"
    subtype: "mock"
    description: "Mock execution test"
    required: true
    request:
      input_template: "Test prompt"
    load:
      mode: "closed_loop"
      concurrency: 1
      duration_sec: 5  # Short for testing
    thresholds:
      p95_ms_max: 10000  # Very lenient for mock
      error_rate_max: 0.5
"""
    
    # Run with mock client
    results = run_performance_suite(
        dataset_content=dataset_content,
        client_callable=mock_client
    )
    
    assert len(results) == 1
    result = results[0]
    
    assert result.id == "mock_test"
    assert result.category == "warm"
    assert result.subtype == "mock"
    assert result.required is True
    assert result.driver == "closed_loop"
    
    # Should have some metrics
    assert "overall" in result.metrics
    overall_metrics = result.metrics["overall"]
    assert overall_metrics.total > 0
    assert overall_metrics.completed >= 0
    assert result.latency_p95_ms >= 0
    assert result.throughput_rps >= 0


def test_perf_subtest_filtering():
    """Test performance subtest filtering functionality."""
    
    dataset_content = """
scenarios:
  - id: "cold_test_1"
    category: "cold_start"
    subtype: "baseline"
    description: "Cold start baseline"
    required: true
    request:
      input_template: "Test 1"
    load:
      mode: "closed_loop"
      concurrency: 1
      duration_sec: 5

  - id: "cold_test_2"
    category: "cold_start"
    subtype: "optimized"
    description: "Cold start optimized"
    required: true
    request:
      input_template: "Test 2"
    load:
      mode: "closed_loop"
      concurrency: 1
      duration_sec: 5

  - id: "warm_test_1"
    category: "warm"
    subtype: "baseline"
    description: "Warm baseline"
    required: true
    request:
      input_template: "Test 3"
    load:
      mode: "closed_loop"
      concurrency: 2
      duration_sec: 5

  - id: "throughput_test_1"
    category: "throughput"
    subtype: "sustained"
    description: "Throughput sustained"
    required: false
    request:
      input_template: "Test 4"
    load:
      mode: "open_loop"
      rate_rps: 3
      duration_sec: 5
"""
    
    # Test with subtest filtering - only run cold_start baseline and warm baseline
    config_overrides = {
        "subtests": {
            "cold_start": ["baseline"],
            "warm": ["baseline"]
            # Note: throughput is excluded entirely
        }
    }
    
    results = run_performance_suite(
        dataset_content=dataset_content,
        config_overrides=config_overrides
    )
    
    # Should only have 2 results (cold_start baseline + warm baseline)
    assert len(results) == 2
    
    result_ids = [r.id for r in results]
    assert "cold_test_1" in result_ids  # cold_start baseline
    assert "warm_test_1" in result_ids  # warm baseline
    assert "cold_test_2" not in result_ids  # cold_start optimized (filtered out)
    assert "throughput_test_1" not in result_ids  # throughput (filtered out)


def test_perf_threshold_evaluation():
    """Test performance threshold evaluation and gating logic."""
    
    # Create a scenario that should fail thresholds
    dataset_content = """
scenarios:
  - id: "failing_test"
    category: "warm"
    subtype: "strict"
    description: "Test with strict thresholds"
    required: true
    request:
      input_template: "Test with strict limits"
    load:
      mode: "closed_loop"
      concurrency: 1
      duration_sec: 3
    thresholds:
      p95_ms_max: 1  # Very strict - should fail
      error_rate_max: 0.0  # No errors allowed
      throughput_min_rps: 1000  # Very high - should fail

  - id: "passing_test"
    category: "throughput"
    subtype: "lenient"
    description: "Test with lenient thresholds"
    required: false
    request:
      input_template: "Test with lenient limits"
    load:
      mode: "open_loop"
      rate_rps: 1
      duration_sec: 3
    thresholds:
      p95_ms_max: 60000  # Very lenient
      error_rate_max: 0.9  # Allow many errors
      throughput_min_rps: 0.1  # Very low requirement
"""
    
    results = run_performance_suite(dataset_content=dataset_content)
    
    assert len(results) == 2
    
    # Find results by ID
    failing_result = next(r for r in results if r.id == "failing_test")
    passing_result = next(r for r in results if r.id == "passing_test")
    
    # The failing test should fail due to strict thresholds
    assert failing_result.passed is False
    assert "P95 latency" in failing_result.reason or "Throughput" in failing_result.reason
    
    # The passing test should pass due to lenient thresholds
    assert passing_result.passed is True
    assert "All thresholds passed" in passing_result.reason


@pytest.mark.asyncio
async def test_load_harness_closed_loop():
    """Test closed-loop load harness functionality."""
    
    harness = LoadHarness()
    
    # Test with very short duration and low concurrency
    results = await harness.closed_loop(
        concurrency=2,
        duration_sec=2,
        input_template="Test prompt",
        headers={"X-Test": "true"},
        think_time_ms=100,
        cold_n=1,
        phase_headers=True
    )
    
    # Should have some results
    assert len(results) > 0
    
    # Check that we have both cold and warm phases
    phases = [r.phase for r in results if r.phase]
    assert "COLD" in phases or "WARM" in phases
    
    # All results should have reasonable latency
    for result in results:
        assert result.latency_ms > 0
        assert result.latency_ms < 10000  # Should be reasonable for mock


@pytest.mark.asyncio
async def test_load_harness_open_loop():
    """Test open-loop load harness functionality."""
    
    harness = LoadHarness()
    
    # Test with very low rate and short duration
    results = await harness.open_loop(
        rate_rps=2,
        duration_sec=2,
        input_template="Test prompt",
        headers={"X-Test": "true"},
        cold_n=1,
        phase_headers=True
    )
    
    # Should have approximately rate_rps * duration_sec requests
    # Allow some variance due to timing
    expected_requests = 2 * 2  # 2 RPS * 2 seconds = 4 requests
    assert len(results) >= expected_requests - 1  # Allow 1 request variance
    assert len(results) <= expected_requests + 2  # Allow 2 request variance
    
    # Check phases
    phases = [r.phase for r in results if r.phase]
    assert "COLD" in phases or "WARM" in phases


def test_perf_config_validation():
    """Test performance configuration validation."""
    
    # Test invalid load mode
    invalid_dataset = """
scenarios:
  - id: "invalid_mode"
    category: "warm"
    subtype: "test"
    description: "Invalid load mode"
    required: true
    request:
      input_template: "Test"
    load:
      mode: "invalid_mode"
      duration_sec: 10
"""
    
    validation_result = validate_perf_content(invalid_dataset)
    assert validation_result.valid is False
    assert len(validation_result.errors) > 0
    
    # Test missing required fields for closed_loop
    missing_concurrency = """
scenarios:
  - id: "missing_concurrency"
    category: "warm"
    subtype: "test"
    description: "Missing concurrency for closed_loop"
    required: true
    request:
      input_template: "Test"
    load:
      mode: "closed_loop"
      duration_sec: 10
      # Missing concurrency
"""
    
    validation_result = validate_perf_content(missing_concurrency)
    assert validation_result.valid is False
    
    # Test missing required fields for open_loop
    missing_rate = """
scenarios:
  - id: "missing_rate"
    category: "throughput"
    subtype: "test"
    description: "Missing rate for open_loop"
    required: true
    request:
      input_template: "Test"
    load:
      mode: "open_loop"
      duration_sec: 10
      # Missing rate_rps
"""
    
    validation_result = validate_perf_content(missing_rate)
    assert validation_result.valid is False


def test_perf_no_dataset_backward_compatibility():
    """Test that performance suite works when no dataset is provided."""
    
    # Should return empty results when no dataset provided
    results = run_performance_suite(dataset_content=None)
    assert results == []
    
    # Should also work with empty string
    results = run_performance_suite(dataset_content="")
    assert results == []
    
    # Should work with whitespace-only content
    results = run_performance_suite(dataset_content="   \n\t  ")
    assert results == []
