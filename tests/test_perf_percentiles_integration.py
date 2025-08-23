"""Integration tests for percentile latency metrics."""

import pytest
import os
from unittest.mock import patch
from apps.observability.perf import record_latency, reset_perf_tracking


@pytest.fixture(autouse=True)
def reset_perf():
    """Reset performance tracking before each test."""
    reset_perf_tracking()
    yield
    reset_perf_tracking()


def test_percentiles_disabled_by_default():
    """Test that percentiles are disabled by default."""
    with patch.dict(os.environ, {}, clear=True):
        # Should return None when disabled
        p50, p95 = record_latency("/test", 100)
        assert p50 is None
        assert p95 is None


def test_percentiles_enabled_integration():
    """Test percentiles enabled integration scenario."""
    with patch.dict(os.environ, {
        "PERF_PERCENTILES_ENABLED": "true",
        "PERF_WINDOW": "10"
    }):
        reset_perf_tracking()
        
        # Simulate realistic latency pattern
        latencies = [50, 100, 75, 200, 125, 300, 80, 90, 110, 150]
        
        results = []
        for latency in latencies:
            p50, p95 = record_latency("/api/test", latency)
            results.append((latency, p50, p95))
        
        # Verify expected behavior
        # First request should have no percentiles
        assert results[0] == (50, None, None)
        
        # Second request should have percentiles
        assert results[1][1] is not None  # p50
        assert results[1][2] is not None  # p95
        
        # Final percentiles should be reasonable
        final_latency, final_p50, final_p95 = results[-1]
        assert final_p50 is not None
        assert final_p95 is not None
        assert final_p50 <= final_p95
        assert 50 <= final_p50 <= 200  # Should be within range
        assert 100 <= final_p95 <= 300  # Should be within range


def test_different_routes_separate_tracking():
    """Test that different routes track percentiles separately."""
    with patch.dict(os.environ, {
        "PERF_PERCENTILES_ENABLED": "true",
        "PERF_WINDOW": "5"
    }):
        reset_perf_tracking()
        
        # Add data to different routes
        route1_latencies = [100, 200, 150]
        route2_latencies = [300, 400, 350]
        
        for lat in route1_latencies:
            record_latency("/route1", lat)
        
        for lat in route2_latencies:
            record_latency("/route2", lat)
        
        # Add final measurement to each route
        p50_r1, p95_r1 = record_latency("/route1", 175)
        p50_r2, p95_r2 = record_latency("/route2", 375)
        
        # Routes should have different percentiles
        assert p50_r1 is not None
        assert p50_r2 is not None
        assert p50_r1 != p50_r2
        assert p50_r1 < p50_r2  # Route1 should have lower latencies


def test_sliding_window_behavior():
    """Test sliding window maintains size limit."""
    with patch.dict(os.environ, {
        "PERF_PERCENTILES_ENABLED": "true",
        "PERF_WINDOW": "3"  # Small window
    }):
        reset_perf_tracking()
        
        # Add more data than window size
        latencies = [100, 200, 300, 400, 500, 600]
        
        for lat in latencies:
            p50, p95 = record_latency("/test", lat)
        
        # Window should only contain last 3 values: [400, 500, 600]
        # So p50 should be 500 and p95 should be 600
        assert p50 == 500
        assert p95 == 600


def test_monotonic_property_maintained():
    """Test that p50 <= p95 is always maintained."""
    with patch.dict(os.environ, {
        "PERF_PERCENTILES_ENABLED": "true",
        "PERF_WINDOW": "20"
    }):
        reset_perf_tracking()
        
        # Add various latency patterns
        import random
        random.seed(42)  # Reproducible results
        
        for _ in range(15):
            latency = random.randint(50, 500)
            p50, p95 = record_latency("/test", latency)
            
            if p50 is not None and p95 is not None:
                assert p50 <= p95, f"p50 ({p50}) should be <= p95 ({p95})"


def test_performance_headers_config_integration():
    """Test configuration integration with performance middleware."""
    from apps.observability.perf import _get_config
    
    # Test default config
    with patch.dict(os.environ, {}, clear=True):
        enabled, window = _get_config()
        assert enabled is False
        assert window == 500
    
    # Test enabled config
    with patch.dict(os.environ, {
        "PERF_PERCENTILES_ENABLED": "true",
        "PERF_WINDOW": "100"
    }):
        enabled, window = _get_config()
        assert enabled is True
        assert window == 100


def test_edge_cases():
    """Test edge cases for percentile calculation."""
    with patch.dict(os.environ, {
        "PERF_PERCENTILES_ENABLED": "true",
        "PERF_WINDOW": "10"
    }):
        reset_perf_tracking()
        
        # Test with identical values
        for _ in range(5):
            p50, p95 = record_latency("/test", 100)
        
        # All values are 100, so percentiles should be 100
        assert p50 == 100
        assert p95 == 100
        
        reset_perf_tracking()
        
        # Test with extreme values
        extreme_values = [1, 1000, 2, 999, 3]
        for val in extreme_values:
            p50, p95 = record_latency("/test2", val)
        
        # Should handle extreme ranges correctly
        assert p50 is not None
        assert p95 is not None
        assert isinstance(p50, int)
        assert isinstance(p95, int)
        assert p50 <= p95
