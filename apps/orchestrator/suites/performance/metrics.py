"""
Performance Metrics Calculation.

Statistical methods for performance analysis including percentiles and segmentation.
"""

import statistics
from typing import List, Dict, Optional, Tuple
import numpy as np
from .schemas import LatencyMetrics, PerfMetrics


class RequestResult:
    """Individual request result."""
    def __init__(self, 
                 latency_ms: float, 
                 success: bool, 
                 timeout: bool = False,
                 tokens_out: Optional[int] = None,
                 cost: Optional[float] = None,
                 phase: Optional[str] = None):
        self.latency_ms = latency_ms
        self.success = success
        self.timeout = timeout
        self.tokens_out = tokens_out or 0
        self.cost = cost or 0.0
        self.phase = phase  # "COLD" or "WARM"


def calculate_percentiles(values: List[float]) -> LatencyMetrics:
    """
    Calculate latency percentiles from a list of values.
    
    Args:
        values: List of latency values in milliseconds
        
    Returns:
        LatencyMetrics with percentiles and statistics
    """
    if not values:
        return LatencyMetrics(
            p50=0.0, p90=0.0, p95=0.0, p99=0.0,
            max=0.0, mean=0.0, std=0.0
        )
    
    # Sort values for percentile calculation
    sorted_values = sorted(values)
    n = len(sorted_values)
    
    # Calculate percentiles using numpy for consistency
    p50 = np.percentile(sorted_values, 50)
    p90 = np.percentile(sorted_values, 90)
    p95 = np.percentile(sorted_values, 95)
    p99 = np.percentile(sorted_values, 99)
    
    # Calculate basic statistics
    max_val = max(sorted_values)
    mean_val = statistics.mean(sorted_values)
    std_val = statistics.stdev(sorted_values) if len(sorted_values) > 1 else 0.0
    
    return LatencyMetrics(
        p50=float(p50),
        p90=float(p90),
        p95=float(p95),
        p99=float(p99),
        max=float(max_val),
        mean=float(mean_val),
        std=float(std_val)
    )


def calculate_scenario_metrics(results: List[RequestResult], 
                             wall_time_sec: float,
                             memory_peak_mb: Optional[float] = None,
                             cpu_peak_pct: Optional[float] = None) -> PerfMetrics:
    """
    Calculate performance metrics for a scenario.
    
    Args:
        results: List of request results
        wall_time_sec: Total wall clock time for the scenario
        memory_peak_mb: Peak memory usage in MB (optional)
        cpu_peak_pct: Peak CPU usage percentage (optional)
        
    Returns:
        PerfMetrics with calculated statistics
    """
    if not results:
        return PerfMetrics(
            total=0, completed=0, errors=0, timeouts=0,
            error_rate=0.0, timeout_rate=0.0,
            latency_ms=LatencyMetrics(p50=0, p90=0, p95=0, p99=0, max=0, mean=0, std=0),
            throughput_rps=0.0,
            memory_peak_mb=memory_peak_mb,
            cpu_peak_pct=cpu_peak_pct
        )
    
    # Count results
    total = len(results)
    completed = sum(1 for r in results if r.success)
    errors = sum(1 for r in results if not r.success and not r.timeout)
    timeouts = sum(1 for r in results if r.timeout)
    
    # Calculate rates
    error_rate = errors / total if total > 0 else 0.0
    timeout_rate = timeouts / total if total > 0 else 0.0
    
    # Calculate latency metrics (only for completed requests)
    completed_latencies = [r.latency_ms for r in results if r.success]
    latency_metrics = calculate_percentiles(completed_latencies)
    
    # Calculate throughput (completed requests per second)
    throughput_rps = completed / wall_time_sec if wall_time_sec > 0 else 0.0
    
    # Calculate token metrics
    tokens_out_total = sum(r.tokens_out for r in results if r.success)
    tokens_out_rate = tokens_out_total / wall_time_sec if wall_time_sec > 0 else 0.0
    tokens_per_sec = tokens_out_rate  # Same as tokens_out_rate
    
    # Calculate cost metrics
    cost_total = sum(r.cost for r in results if r.success)
    cost_per_request = cost_total / completed if completed > 0 else 0.0
    
    return PerfMetrics(
        total=total,
        completed=completed,
        errors=errors,
        timeouts=timeouts,
        error_rate=error_rate,
        timeout_rate=timeout_rate,
        latency_ms=latency_metrics,
        throughput_rps=throughput_rps,
        tokens_out_total=tokens_out_total if tokens_out_total > 0 else None,
        tokens_out_rate=tokens_out_rate if tokens_out_rate > 0 else None,
        tokens_per_sec=tokens_per_sec if tokens_per_sec > 0 else None,
        cost_total=cost_total if cost_total > 0 else None,
        cost_per_request=cost_per_request if cost_per_request > 0 else None,
        memory_peak_mb=memory_peak_mb,
        cpu_peak_pct=cpu_peak_pct
    )


def segment_results(results: List[RequestResult], 
                   cold_n: int = 1, 
                   warmup_exclude_n: int = 0) -> Tuple[List[RequestResult], List[RequestResult]]:
    """
    Segment results into cold and warm phases.
    
    Args:
        results: List of request results
        cold_n: Number of requests to consider as cold phase
        warmup_exclude_n: Number of requests to exclude from warm phase
        
    Returns:
        Tuple of (cold_results, warm_results)
    """
    if not results:
        return [], []
    
    # Cold phase: first cold_n requests
    cold_results = results[:cold_n]
    
    # Warm phase: remaining requests after excluding warmup
    warm_start_idx = max(cold_n, warmup_exclude_n)
    warm_results = results[warm_start_idx:]
    
    return cold_results, warm_results


def calculate_segmented_metrics(results: List[RequestResult],
                              wall_time_sec: float,
                              cold_n: int = 1,
                              warmup_exclude_n: int = 0,
                              memory_peak_mb: Optional[float] = None,
                              cpu_peak_pct: Optional[float] = None) -> Dict[str, PerfMetrics]:
    """
    Calculate metrics with cold/warm segmentation.
    
    Args:
        results: List of request results
        wall_time_sec: Total wall clock time
        cold_n: Number of cold phase requests
        warmup_exclude_n: Number of warmup requests to exclude
        memory_peak_mb: Peak memory usage
        cpu_peak_pct: Peak CPU usage
        
    Returns:
        Dictionary with "overall", "cold", and "warm" metrics
    """
    metrics = {}
    
    # Overall metrics
    metrics["overall"] = calculate_scenario_metrics(
        results, wall_time_sec, memory_peak_mb, cpu_peak_pct
    )
    
    # Segmented metrics if we have enough results
    if len(results) > cold_n:
        cold_results, warm_results = segment_results(results, cold_n, warmup_exclude_n)
        
        if cold_results:
            # Cold phase metrics (use proportional wall time)
            cold_wall_time = wall_time_sec * len(cold_results) / len(results)
            metrics["cold"] = calculate_scenario_metrics(
                cold_results, cold_wall_time, memory_peak_mb, cpu_peak_pct
            )
        
        if warm_results:
            # Warm phase metrics (use proportional wall time)
            warm_wall_time = wall_time_sec * len(warm_results) / len(results)
            metrics["warm"] = calculate_scenario_metrics(
                warm_results, warm_wall_time, memory_peak_mb, cpu_peak_pct
            )
    
    return metrics


def get_p95_for_category(metrics: Dict[str, PerfMetrics], category: str) -> float:
    """
    Get the appropriate P95 latency for a given category.
    
    Args:
        metrics: Dictionary of metrics (overall, cold, warm)
        category: Performance category
        
    Returns:
        P95 latency in milliseconds
    """
    if category == "cold_start" and "cold" in metrics:
        return metrics["cold"].latency_ms.p95
    elif category == "warm" and "warm" in metrics:
        return metrics["warm"].latency_ms.p95
    else:
        return metrics["overall"].latency_ms.p95


def format_metrics_for_reporting(metrics: PerfMetrics) -> Dict[str, any]:
    """
    Format metrics for reporting (flatten nested structures).
    
    Args:
        metrics: PerfMetrics object
        
    Returns:
        Flattened dictionary suitable for CSV/Excel export
    """
    return {
        "total": metrics.total,
        "completed": metrics.completed,
        "errors": metrics.errors,
        "timeouts": metrics.timeouts,
        "error_rate": metrics.error_rate,
        "timeout_rate": metrics.timeout_rate,
        "p50": metrics.latency_ms.p50,
        "p90": metrics.latency_ms.p90,
        "p95": metrics.latency_ms.p95,
        "p99": metrics.latency_ms.p99,
        "max": metrics.latency_ms.max,
        "mean": metrics.latency_ms.mean,
        "std": metrics.latency_ms.std,
        "throughput_rps": metrics.throughput_rps,
        "tokens_out_total": metrics.tokens_out_total,
        "tokens_out_rate": metrics.tokens_out_rate,
        "tokens_per_sec": metrics.tokens_per_sec,
        "cost_total": metrics.cost_total,
        "cost_per_request": metrics.cost_per_request,
        "memory_peak_mb": metrics.memory_peak_mb,
        "cpu_peak_pct": metrics.cpu_peak_pct
    }
