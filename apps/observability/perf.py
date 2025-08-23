"""Performance monitoring and cold/warm phase detection."""

import os
import time
import threading
from collections import defaultdict, deque
from typing import Tuple, Optional, Dict, Deque
from dotenv import load_dotenv

load_dotenv()

# Global state for tracking first request
first_request_monotonic: Optional[float] = None

# Percentile tracking
_latency_buffers: Dict[str, Deque[int]] = defaultdict(lambda: deque())
_buffer_lock = threading.Lock()


def decide_phase_and_latency(t0: float) -> Tuple[str, int]:
    """
    Determine performance phase (cold/warm) and calculate latency.
    
    Args:
        t0: Start time from time.perf_counter()
        
    Returns:
        Tuple of (phase, latency_ms) where phase is "cold" or "warm"
    """
    global first_request_monotonic
    
    # Calculate latency
    latency_ms = int((time.perf_counter() - t0) * 1000)
    
    # Get cold window from environment
    cold_window_seconds = int(os.getenv("PERF_COLD_WINDOW_SECONDS", "120"))
    
    # Record first request time if not set
    if first_request_monotonic is None:
        first_request_monotonic = time.perf_counter()
        return "cold", latency_ms
    
    # Check if we're still in cold window
    elapsed_since_first = time.perf_counter() - first_request_monotonic
    
    if elapsed_since_first < cold_window_seconds:
        return "cold", latency_ms
    else:
        return "warm", latency_ms


def _get_config() -> Tuple[bool, int]:
    """Get percentile configuration from environment."""
    enabled = os.getenv("PERF_PERCENTILES_ENABLED", "false").lower() == "true"
    window_size = int(os.getenv("PERF_WINDOW", "500"))
    return enabled, window_size


def _calculate_percentile(values: list, percentile: float) -> int:
    """
    Calculate percentile using nearest-rank method.
    
    Args:
        values: List of latency values (will be sorted)
        percentile: Percentile to calculate (0.0 to 1.0)
        
    Returns:
        Percentile value in milliseconds
    """
    if not values:
        return 0
    
    sorted_values = sorted(values)
    n = len(sorted_values)
    
    # Nearest-rank method
    rank = max(1, int(percentile * n + 0.5))
    return sorted_values[rank - 1]


def record_latency(route: str, latency_ms: int) -> Tuple[Optional[int], Optional[int]]:
    """
    Record latency for a route and return current p50/p95 if enabled.
    
    Args:
        route: Route identifier (e.g., "/ask", "/orchestrator/run_tests")
        latency_ms: Latency in milliseconds
        
    Returns:
        Tuple of (p50_ms, p95_ms) if percentiles enabled, (None, None) otherwise
    """
    enabled, window_size = _get_config()
    
    if not enabled:
        return None, None
    
    with _buffer_lock:
        # Get or create buffer for this route
        buffer = _latency_buffers[route]
        
        # Add new latency
        buffer.append(latency_ms)
        
        # Maintain sliding window size
        while len(buffer) > window_size:
            buffer.popleft()
        
        # Calculate percentiles if we have enough data
        if len(buffer) >= 2:  # Need at least 2 data points
            values = list(buffer)
            p50 = _calculate_percentile(values, 0.50)
            p95 = _calculate_percentile(values, 0.95)
            return p50, p95
        else:
            return None, None


def reset_perf_tracking() -> None:
    """Reset performance tracking (useful for testing)."""
    global first_request_monotonic, _latency_buffers
    
    first_request_monotonic = None
    
    with _buffer_lock:
        _latency_buffers.clear()
