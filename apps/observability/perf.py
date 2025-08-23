"""Performance monitoring and cold/warm phase detection."""

import os
import time
from typing import Tuple, Optional
from dotenv import load_dotenv

load_dotenv()

# Global state for tracking first request
first_request_monotonic: Optional[float] = None


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


def reset_perf_tracking() -> None:
    """Reset performance tracking (useful for testing)."""
    global first_request_monotonic
    first_request_monotonic = None
