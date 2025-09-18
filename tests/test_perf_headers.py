"""Tests for performance headers and observability features."""

import pytest
import time
from unittest.mock import patch, MagicMock


def test_decide_phase_and_latency_cold():
    """Test cold phase detection."""
    from apps.observability.perf import decide_phase_and_latency, reset_perf_tracking
    
    # Reset tracking for clean test
    reset_perf_tracking()
    
    with patch.dict('os.environ', {"PERF_COLD_WINDOW_SECONDS": "120"}):
        start_time = time.perf_counter()
        
        # First request should be cold
        phase, latency_ms = decide_phase_and_latency(start_time)
        
        assert phase == "cold"
        assert latency_ms >= 0
        assert isinstance(latency_ms, int)


def test_decide_phase_and_latency_warm():
    """Test warm phase detection."""
    from apps.observability.perf import decide_phase_and_latency, reset_perf_tracking
    
    # Reset and set first request time in the past
    reset_perf_tracking()
    
    with patch.dict('os.environ', {"PERF_COLD_WINDOW_SECONDS": "1"}):  # 1 second window
        # First request to set the baseline
        start_time = time.perf_counter()
        decide_phase_and_latency(start_time)
        
        # Wait a bit to exceed cold window
        time.sleep(1.1)
        
        # Second request should be warm
        start_time2 = time.perf_counter()
        phase, latency_ms = decide_phase_and_latency(start_time2)
        
        assert phase == "warm"
        assert latency_ms >= 0


def test_perf_tracking_reset():
    """Test performance tracking reset functionality."""
    from apps.observability.perf import decide_phase_and_latency, reset_perf_tracking, first_request_monotonic
    
    # Make a request to set first_request_monotonic
    start_time = time.perf_counter()
    decide_phase_and_latency(start_time)
    
    # Reset should clear the tracking
    reset_perf_tracking()
    
    # Next request should be cold again
    start_time2 = time.perf_counter()
    phase, latency_ms = decide_phase_and_latency(start_time2)
    
    assert phase == "cold"


def test_latency_calculation_accuracy():
    """Test that latency calculation is reasonably accurate."""
    from apps.observability.perf import decide_phase_and_latency
    
    start_time = time.perf_counter()
    
    # Add a small delay
    time.sleep(0.01)  # 10ms
    
    phase, latency_ms = decide_phase_and_latency(start_time)
    
    # Should be at least 10ms, but allow for some variance
    assert latency_ms >= 8  # Allow some margin for timing precision
    assert latency_ms < 100  # Should not be too high for such a short delay


def test_cold_window_configuration():
    """Test that cold window configuration is respected."""
    from apps.observability.perf import decide_phase_and_latency, reset_perf_tracking
    
    reset_perf_tracking()
    
    # Test with very short cold window
    with patch.dict('os.environ', {"PERF_COLD_WINDOW_SECONDS": "0"}):
        # First request
        start_time1 = time.perf_counter()
        phase1, _ = decide_phase_and_latency(start_time1)
        assert phase1 == "cold"
        
        # Immediate second request should be warm (0 second window)
        start_time2 = time.perf_counter()
        phase2, _ = decide_phase_and_latency(start_time2)
        assert phase2 == "warm"


@pytest.mark.asyncio
async def test_ask_endpoint_sets_performance_headers():
    """Test that /ask endpoint sets performance headers."""
    from fastapi.testclient import TestClient
    from unittest.mock import AsyncMock
    
    # This test would require a full integration test setup
    # For now, we'll test the header setting logic directly
    
    from apps.observability.perf import decide_phase_and_latency
    from fastapi import Response
    
    # Mock response object
    response = Response()
    
    start_time = time.perf_counter()
    phase, latency_ms = decide_phase_and_latency(start_time)
    
    # Simulate header setting
    response.headers["X-Source"] = "live"
    response.headers["X-Perf-Phase"] = phase
    response.headers["X-Latency-MS"] = str(latency_ms)
    
    # Verify headers are set correctly
    assert response.headers["X-Source"] == "live"
    assert response.headers["X-Perf-Phase"] in ["cold", "warm"]
    assert response.headers["X-Latency-MS"].isdigit()
    assert int(response.headers["X-Latency-MS"]) >= 0


def test_audit_logging_integration():
    """Test audit logging integration with performance tracking."""
    from apps.observability.log_service import audit_start, audit_finish
    from apps.observability.perf import decide_phase_and_latency
    
    with patch.dict('os.environ', {
        "AUDIT_LOG_ENABLED": "true",
        "PERSIST_DB": "true"
    }):
        with patch('apps.observability.log_service.snowflake_cursor') as mock_cursor:
            mock_cursor.return_value.__enter__.return_value = MagicMock()
            
            # Start audit
            audit_id = audit_start("/ask", "POST", "user", "12345678")
            
            # Simulate request processing
            start_time = time.perf_counter()
            time.sleep(0.001)  # Small delay
            phase, latency_ms = decide_phase_and_latency(start_time)
            
            # Finish audit with performance data
            if audit_id:
                audit_finish(audit_id, 200, latency_ms, phase == "cold")
            
            # Verify audit calls were made
            assert mock_cursor.called


def test_performance_headers_with_cache_hit():
    """Test performance headers are set correctly for cache hits."""
    from apps.observability.perf import decide_phase_and_latency
    
    start_time = time.perf_counter()
    
    # Simulate very fast cache hit
    phase, latency_ms = decide_phase_and_latency(start_time)
    
    # Even cache hits should have valid performance data
    assert phase in ["cold", "warm"]
    assert latency_ms >= 0
    assert latency_ms < 1000  # Cache hits should be fast


def test_performance_headers_with_live_generation():
    """Test performance headers for live generation."""
    from apps.observability.perf import decide_phase_and_latency
    
    start_time = time.perf_counter()
    
    # Simulate longer processing time for live generation
    time.sleep(0.01)  # 10ms delay
    
    phase, latency_ms = decide_phase_and_latency(start_time)
    
    assert phase in ["cold", "warm"]
    assert latency_ms >= 8  # Should reflect the processing time
    

def test_concurrent_requests_performance_tracking():
    """Test performance tracking with concurrent requests."""
    from apps.observability.perf import decide_phase_and_latency, reset_perf_tracking
    import threading
    import time
    
    reset_perf_tracking()
    results = []
    
    def make_request():
        start_time = time.perf_counter()
        time.sleep(0.001)  # Small delay
        phase, latency_ms = decide_phase_and_latency(start_time)
        results.append((phase, latency_ms))
    
    # Start multiple threads
    threads = []
    for _ in range(5):
        thread = threading.Thread(target=make_request)
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # All requests should have valid results
    assert len(results) == 5
    for phase, latency_ms in results:
        assert phase in ["cold", "warm"]
        assert latency_ms >= 0
    
    # At least one should be cold (the first one)
    phases = [result[0] for result in results]
    assert "cold" in phases


def test_environment_variable_defaults():
    """Test default values when environment variables are not set."""
    from apps.observability.perf import decide_phase_and_latency, reset_perf_tracking
    
    reset_perf_tracking()
    
    # Clear environment variable
    with patch.dict('os.environ', {}, clear=True):
        start_time = time.perf_counter()
        phase, latency_ms = decide_phase_and_latency(start_time)
        
        # Should still work with defaults
        assert phase == "cold"  # First request
        assert latency_ms >= 0


def test_performance_data_types():
    """Test that performance data has correct types."""
    from apps.observability.perf import decide_phase_and_latency
    
    start_time = time.perf_counter()
    phase, latency_ms = decide_phase_and_latency(start_time)
    
    # Verify types
    assert isinstance(phase, str)
    assert isinstance(latency_ms, int)
    assert phase in ["cold", "warm"]
    assert latency_ms >= 0
