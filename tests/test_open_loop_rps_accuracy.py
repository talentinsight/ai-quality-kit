"""
Test Performance open-loop RPS accuracy.

Ensures that the open-loop rate controller maintains accurate RPS within tolerance.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from apps.orchestrator.suites.performance.harness import LoadHarness, compute_schedule
from apps.orchestrator.suites.performance.metrics import RequestResult
from apps.config.perf import PERF_RPS_TOLERANCE


class TestOpenLoopRPSAccuracy:
    """Test open-loop RPS accuracy and scheduling."""
    
    def test_compute_schedule_basic(self):
        """Test basic schedule computation."""
        # Test 10 RPS for 5 seconds = 50 requests
        start_time = 1000.0  # Fixed start time
        schedule = compute_schedule(10.0, 5, start_time)
        
        # Should have 50 requests
        assert len(schedule) == 50
        
        # First request at start_time
        assert schedule[0] == start_time
        
        # Requests should be spaced 0.1 seconds apart (1/10 RPS)
        for i in range(1, len(schedule)):
            expected_time = start_time + (i * 0.1)
            assert abs(schedule[i] - expected_time) < 1e-10
        
        # Last request should be before end time
        assert schedule[-1] < start_time + 5.0
    
    def test_compute_schedule_fractional_rps(self):
        """Test schedule computation with fractional RPS."""
        # Test 2.5 RPS for 4 seconds = 10 requests
        start_time = 2000.0
        schedule = compute_schedule(2.5, 4, start_time)
        
        # Should have 10 requests
        assert len(schedule) == 10
        
        # Requests should be spaced 0.4 seconds apart (1/2.5 RPS)
        for i in range(len(schedule)):
            expected_time = start_time + (i * 0.4)
            assert abs(schedule[i] - expected_time) < 1e-10
    
    def test_compute_schedule_high_rate(self):
        """Test schedule computation with high RPS."""
        # Test 100 RPS for 1 second = 100 requests
        start_time = 3000.0
        schedule = compute_schedule(100.0, 1, start_time)
        
        # Should have 100 requests
        assert len(schedule) == 100
        
        # Requests should be spaced 0.01 seconds apart
        for i in range(1, min(10, len(schedule))):  # Check first 10
            expected_time = start_time + (i * 0.01)
            assert abs(schedule[i] - expected_time) < 1e-10
    
    @pytest.mark.asyncio
    async def test_open_loop_rps_accuracy_mock_time(self):
        """Test open-loop RPS accuracy with mocked time."""
        # Mock client that responds instantly
        mock_client = AsyncMock(return_value="test response")
        
        # Mock memory tracker
        mock_memory_tracker = Mock()
        mock_memory_tracker.start = Mock()
        mock_memory_tracker.stop = Mock(return_value=(100.0, 50.0))
        
        harness = LoadHarness(mock_client, timeout_ms=1000)
        harness.memory_tracker = mock_memory_tracker
        
        # Mock time to control scheduling precisely
        fake_time = 1000.0
        scheduled_times = []
        
        def mock_monotonic():
            return fake_time
        
        async def mock_sleep(duration):
            nonlocal fake_time
            fake_time += duration
            # Track when requests are scheduled
            scheduled_times.append(fake_time)
        
        with patch('time.monotonic', side_effect=mock_monotonic), \
             patch('asyncio.sleep', side_effect=mock_sleep), \
             patch.object(harness, '_make_request') as mock_make_request:
            
            # Configure _make_request to return immediately
            mock_make_request.return_value = RequestResult(
                success=True,
                latency_ms=100,
                phase="WARM",
                timestamp=fake_time,
                error=None,
                tokens_out=10,
                cost=0.001
            )
            
            # Test 10 RPS for 10 seconds
            target_rps = 10.0
            duration_sec = 10
            
            results = await harness.open_loop(
                rate_rps=target_rps,
                duration_sec=duration_sec,
                input_template="Test prompt",
                headers=None,
                cold_n=1,
                phase_headers=True
            )
            
            # Verify request count is within tolerance
            expected_requests = int(target_rps * duration_sec)  # 100 requests
            actual_requests = len(results)
            
            # Allow some variance due to timing
            tolerance = max(1, int(expected_requests * PERF_RPS_TOLERANCE))
            assert abs(actual_requests - expected_requests) <= tolerance, \
                f"Expected ~{expected_requests} requests, got {actual_requests}"
            
            # Verify _make_request was called the right number of times
            assert mock_make_request.call_count == actual_requests
    
    @pytest.mark.asyncio
    async def test_open_loop_rps_accuracy_real_time(self):
        """Test open-loop RPS accuracy with real time (shorter duration)."""
        # Mock client with small delay to simulate real behavior
        async def mock_client_with_delay(prompt, headers=None):
            await asyncio.sleep(0.01)  # 10ms delay
            return "test response"
        
        # Mock memory tracker
        mock_memory_tracker = Mock()
        mock_memory_tracker.start = Mock()
        mock_memory_tracker.stop = Mock(return_value=(100.0, 50.0))
        
        harness = LoadHarness(mock_client_with_delay, timeout_ms=1000)
        harness.memory_tracker = mock_memory_tracker
        
        with patch.object(harness, '_make_request') as mock_make_request:
            # Configure _make_request to return quickly
            async def quick_request(*args, **kwargs):
                await asyncio.sleep(0.005)  # 5ms
                return RequestResult(
                    success=True,
                    latency_ms=5,
                    phase="WARM",
                    timestamp=time.monotonic(),
                    error=None,
                    tokens_out=10,
                    cost=0.001
                )
            
            mock_make_request.side_effect = quick_request
            
            # Test 5 RPS for 2 seconds (short test to avoid long waits)
            target_rps = 5.0
            duration_sec = 2
            
            start_time = time.monotonic()
            results = await harness.open_loop(
                rate_rps=target_rps,
                duration_sec=duration_sec,
                input_template="Test prompt",
                cold_n=1
            )
            actual_duration = time.monotonic() - start_time
            
            # Verify timing accuracy
            expected_requests = int(target_rps * duration_sec)  # 10 requests
            actual_requests = len(results)
            actual_rps = actual_requests / actual_duration if actual_duration > 0 else 0
            
            # Check RPS accuracy
            rps_error = abs(actual_rps - target_rps) / target_rps if target_rps > 0 else 0
            assert rps_error <= PERF_RPS_TOLERANCE, \
                f"RPS error {rps_error:.1%} exceeds tolerance {PERF_RPS_TOLERANCE:.1%}"
            
            # Verify request count is reasonable
            tolerance = max(1, int(expected_requests * PERF_RPS_TOLERANCE))
            assert abs(actual_requests - expected_requests) <= tolerance, \
                f"Expected ~{expected_requests} requests, got {actual_requests}"
    
    def test_compute_schedule_edge_cases(self):
        """Test schedule computation edge cases."""
        # Very low RPS
        schedule = compute_schedule(0.5, 10, 0.0)  # 0.5 RPS for 10s = 5 requests
        assert len(schedule) == 5
        assert schedule[1] - schedule[0] == 2.0  # 2 second intervals
        
        # Very short duration
        schedule = compute_schedule(10.0, 0.1, 0.0)  # 10 RPS for 0.1s = 1 request
        assert len(schedule) == 1
        
        # Zero duration
        schedule = compute_schedule(10.0, 0, 0.0)
        assert len(schedule) == 0
    
    @pytest.mark.asyncio
    async def test_open_loop_phase_headers(self):
        """Test that phase headers are correctly set in open-loop mode."""
        mock_client = AsyncMock(return_value="response")
        
        mock_memory_tracker = Mock()
        mock_memory_tracker.start = Mock()
        mock_memory_tracker.stop = Mock(return_value=(100.0, 50.0))
        
        harness = LoadHarness(mock_client, timeout_ms=1000)
        harness.memory_tracker = mock_memory_tracker
        
        request_phases = []
        
        async def capture_phase_request(input_template, headers, phase, phase_headers):
            request_phases.append(phase)
            return RequestResult(
                success=True,
                latency_ms=10,
                phase=phase,
                timestamp=time.monotonic(),
                error=None,
                tokens_out=5,
                cost=0.001
            )
        
        with patch.object(harness, '_make_request', side_effect=capture_phase_request):
            # Test with cold_n=3
            await harness.open_loop(
                rate_rps=5.0,
                duration_sec=1,  # Short test
                input_template="Test",
                cold_n=3,
                phase_headers=True
            )
            
            # First 3 should be COLD, rest WARM
            assert len(request_phases) >= 3
            assert request_phases[0] == "COLD"
            assert request_phases[1] == "COLD"
            assert request_phases[2] == "COLD"
            
            if len(request_phases) > 3:
                assert all(phase == "WARM" for phase in request_phases[3:])
    
    def test_rps_tolerance_configuration(self):
        """Test that RPS tolerance is properly configured."""
        # Test that tolerance is reasonable
        assert 0 < PERF_RPS_TOLERANCE <= 1.0
        assert PERF_RPS_TOLERANCE == 0.05  # Default 5%
