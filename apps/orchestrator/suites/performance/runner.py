"""
Performance Test Runner.

Executes performance test scenarios and performs threshold evaluation.
"""

import time
import logging
from typing import List, Dict, Any, Optional, Callable

from .schemas import PerfCase, PerfResult, NormalizedPerf, PerfConfig
from .loader import parse_perf_content
from .harness import LoadHarness
from .metrics import calculate_segmented_metrics, get_p95_for_category, RequestResult
from apps.config.perf import (
    PERF_ENABLED, PERF_P95_MS_MAX, PERF_ERROR_RATE_MAX, PERF_TIMEOUT_RATE_MAX,
    PERF_THROUGHPUT_MIN_RPS, PERF_TOKENS_PER_SEC_MIN, PERF_MEMORY_PEAK_MB_MAX
)

logger = logging.getLogger(__name__)


def run_performance_suite(
    dataset_content: Optional[str] = None,
    config_overrides: Optional[Dict[str, Any]] = None,
    client_callable: Optional[Callable[[str, Dict[str, str]], str]] = None
) -> List[PerfResult]:
    """
    Run the complete Performance suite.
    
    Args:
        dataset_content: Optional performance dataset content (YAML/JSON/JSONL)
        config_overrides: Optional configuration overrides
        client_callable: Optional client for LLM calls
        
    Returns:
        List of PerfResult objects
    """
    if not PERF_ENABLED:
        logger.info("Performance suite is disabled")
        return []
    
    # Load dataset if provided
    if dataset_content:
        try:
            normalized_perf = parse_perf_content(dataset_content)
            logger.info(f"Loaded {len(normalized_perf.scenarios)} performance scenarios from dataset")
        except Exception as e:
            logger.error(f"Failed to parse performance dataset: {e}")
            return []
    else:
        # No dataset provided - return empty results (backward compatible)
        logger.info("No performance dataset provided, skipping performance tests")
        return []
    
    # Apply subtest filtering if specified
    if config_overrides and 'subtests' in config_overrides:
        normalized_perf.scenarios = _filter_scenarios_by_subtests(
            normalized_perf.scenarios, 
            config_overrides['subtests']
        )
        logger.info(f"Filtered to {len(normalized_perf.scenarios)} scenarios based on subtests")
    
    # Execute performance scenarios
    results = []
    harness = LoadHarness(client_callable)
    
    for scenario in normalized_perf.scenarios:
        try:
            result = _execute_perf_scenario(scenario, harness)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to execute performance scenario {scenario.id}: {e}")
            # Create a failed result
            results.append(PerfResult(
                id=scenario.id,
                category=scenario.category.value,
                subtype=scenario.subtype,
                required=scenario.required,
                passed=False,
                reason=f"Execution failed: {str(e)}",
                driver="unknown",
                load={},
                metrics={},
                latency_p95_ms=0.0,
                throughput_rps=0.0,
                error_rate=1.0,
                timeout_rate=0.0,
                headers_observed={}
            ))
    
    logger.info(f"Completed performance suite: {len(results)} scenarios executed")
    return results


def _execute_perf_scenario(scenario: PerfCase, harness: LoadHarness) -> PerfResult:
    """
    Execute a single performance test scenario.
    
    Args:
        scenario: Performance test scenario to execute
        harness: Load generation harness
        
    Returns:
        PerfResult with execution results
    """
    logger.debug(f"Executing performance scenario: {scenario.id}")
    
    start_time = time.monotonic()
    
    # Prepare request parameters
    input_template = scenario.request.input_template
    headers = scenario.request.headers or {}
    
    # Prepare load parameters
    load_config = scenario.load
    segmentation = scenario.segmentation or {}
    cold_n = segmentation.cold_n or 1
    warmup_exclude_n = segmentation.warmup_exclude_n or 0
    phase_headers = segmentation.phase_headers if segmentation.phase_headers is not None else True
    
    # Execute based on load mode
    if load_config.mode.value == "closed_loop":
        import asyncio
        results = asyncio.run(harness.closed_loop(
            concurrency=load_config.concurrency,
            duration_sec=load_config.duration_sec,
            input_template=input_template,
            headers=headers,
            think_time_ms=load_config.think_time_ms or 0,
            cold_n=cold_n,
            phase_headers=phase_headers
        ))
    else:  # open_loop
        import asyncio
        results = asyncio.run(harness.open_loop(
            rate_rps=load_config.rate_rps,
            duration_sec=load_config.duration_sec,
            input_template=input_template,
            headers=headers,
            cold_n=cold_n,
            phase_headers=phase_headers
        ))
    
    end_time = time.monotonic()
    wall_time_sec = end_time - start_time
    
    # Get memory/CPU peaks from first result (they're all the same)
    memory_peak_mb = results[0].memory_peak_mb if results and hasattr(results[0], 'memory_peak_mb') else None
    cpu_peak_pct = results[0].cpu_peak_pct if results and hasattr(results[0], 'cpu_peak_pct') else None
    
    # Calculate metrics with segmentation
    metrics = calculate_segmented_metrics(
        results, wall_time_sec, cold_n, warmup_exclude_n, memory_peak_mb, cpu_peak_pct
    )
    
    # Determine pass/fail
    passed, reason = _evaluate_scenario_result(scenario, metrics)
    
    # Extract key metrics for top-level fields
    overall_metrics = metrics["overall"]
    p95_latency = get_p95_for_category(metrics, scenario.category.value)
    
    # Check for observability headers
    headers_observed = {
        "x_latency_ms_seen": False  # Would need to implement header capture
    }
    
    # Prepare load configuration for result
    load_dict = {
        "mode": load_config.mode.value,
        "duration_sec": load_config.duration_sec,
        "think_time_ms": load_config.think_time_ms or 0
    }
    if load_config.concurrency:
        load_dict["concurrency"] = load_config.concurrency
    if load_config.rate_rps:
        load_dict["rate_rps"] = load_config.rate_rps
    
    return PerfResult(
        id=scenario.id,
        category=scenario.category.value,
        subtype=scenario.subtype,
        required=scenario.required,
        passed=passed,
        reason=reason,
        driver=load_config.mode.value,
        load=load_dict,
        metrics={k: v for k, v in metrics.items()},
        latency_p95_ms=p95_latency,
        throughput_rps=overall_metrics.throughput_rps,
        error_rate=overall_metrics.error_rate,
        timeout_rate=overall_metrics.timeout_rate,
        tokens_per_sec=overall_metrics.tokens_per_sec,
        memory_peak_mb=overall_metrics.memory_peak_mb,
        cpu_peak_pct=overall_metrics.cpu_peak_pct,
        headers_observed=headers_observed
    )


def _evaluate_scenario_result(scenario: PerfCase, metrics: Dict[str, Any]) -> tuple[bool, str]:
    """
    Evaluate whether a performance scenario passes or fails.
    
    Args:
        scenario: Performance test scenario
        metrics: Calculated metrics
        
    Returns:
        Tuple of (passed, reason)
    """
    # Get thresholds (scenario overrides or defaults)
    thresholds = scenario.thresholds
    p95_max = thresholds.p95_ms_max if thresholds else PERF_P95_MS_MAX
    error_rate_max = thresholds.error_rate_max if thresholds else PERF_ERROR_RATE_MAX
    timeout_rate_max = thresholds.timeout_rate_max if thresholds else PERF_TIMEOUT_RATE_MAX
    throughput_min = thresholds.throughput_min_rps if thresholds else PERF_THROUGHPUT_MIN_RPS
    tokens_per_sec_min = thresholds.tokens_per_sec_min if thresholds else PERF_TOKENS_PER_SEC_MIN
    memory_max = thresholds.memory_peak_mb_max if thresholds else PERF_MEMORY_PEAK_MB_MAX
    
    failures = []
    overall_metrics = metrics["overall"]
    
    # Check P95 latency (category-specific)
    p95_latency = get_p95_for_category(metrics, scenario.category.value)
    if p95_latency > p95_max:
        failures.append(f"P95 latency {p95_latency:.1f}ms > {p95_max}ms")
    
    # Check error rate
    if overall_metrics.error_rate > error_rate_max:
        failures.append(f"Error rate {overall_metrics.error_rate:.3f} > {error_rate_max:.3f}")
    
    # Check timeout rate
    if overall_metrics.timeout_rate > timeout_rate_max:
        failures.append(f"Timeout rate {overall_metrics.timeout_rate:.3f} > {timeout_rate_max:.3f}")
    
    # Check throughput
    if overall_metrics.throughput_rps < throughput_min:
        failures.append(f"Throughput {overall_metrics.throughput_rps:.1f} RPS < {throughput_min} RPS")
    
    # Check tokens per second (if available)
    if (overall_metrics.tokens_per_sec is not None and 
        tokens_per_sec_min > 0 and 
        overall_metrics.tokens_per_sec < tokens_per_sec_min):
        failures.append(f"Tokens/sec {overall_metrics.tokens_per_sec:.1f} < {tokens_per_sec_min}")
    
    # Check memory usage (for memory category)
    if (scenario.category.value == "memory" and 
        overall_metrics.memory_peak_mb is not None and 
        overall_metrics.memory_peak_mb > memory_max):
        failures.append(f"Memory peak {overall_metrics.memory_peak_mb:.1f}MB > {memory_max}MB")
    
    if failures:
        return False, "; ".join(failures)
    else:
        return True, "All thresholds passed"


def _filter_scenarios_by_subtests(
    scenarios: List[PerfCase], 
    subtests: Dict[str, List[str]]
) -> List[PerfCase]:
    """
    Filter performance scenarios based on selected subtests.
    
    Args:
        scenarios: List of performance scenarios
        subtests: Dictionary mapping categories to selected subtypes
        
    Returns:
        Filtered list of performance scenarios
    """
    filtered_scenarios = []
    
    for scenario in scenarios:
        category = scenario.category.value
        subtype = scenario.subtype
        
        # Include scenario if its category/subtype is selected
        if category in subtests and subtype in subtests[category]:
            filtered_scenarios.append(scenario)
    
    return filtered_scenarios
