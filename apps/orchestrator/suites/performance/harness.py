"""
Performance Load Harness.

Implements closed-loop and open-loop load generation drivers.
"""

import asyncio
import time
import logging
from typing import List, Optional, Callable, Dict, Any
import random

from .metrics import RequestResult
from apps.config.perf import PERF_OBSERVABILITY_HEADERS, PERF_TIMEOUT_MS, PERF_RPS_TOLERANCE

logger = logging.getLogger(__name__)


def compute_schedule(rate_rps: float, duration_sec: int, start_time: float = None) -> List[float]:
    """
    Compute accurate request schedule for open-loop load generation.
    
    Args:
        rate_rps: Target requests per second
        duration_sec: Total duration in seconds
        start_time: Start time (monotonic), defaults to time.monotonic()
        
    Returns:
        List of absolute timestamps when requests should be sent
    """
    if start_time is None:
        start_time = time.monotonic()
    
    total_requests = int(rate_rps * duration_sec)
    schedule = []
    
    # Use precise timing to avoid drift
    for i in range(total_requests):
        request_time = start_time + (i / rate_rps)
        if request_time - start_time < duration_sec:  # Within duration
            schedule.append(request_time)
    
    return schedule


class LoadHarness:
    """Load generation harness with multiple drivers."""
    
    def __init__(self, 
                 client_callable: Optional[Callable[[str, Dict[str, str]], str]] = None,
                 timeout_ms: int = PERF_TIMEOUT_MS):
        """
        Initialize load harness.
        
        Args:
            client_callable: Function to call LLM (prompt, headers) -> response
            timeout_ms: Request timeout in milliseconds
        """
        self.client_callable = client_callable
        self.timeout_ms = timeout_ms / 1000.0  # Convert to seconds
        self.memory_tracker = MemoryTracker()
        
    async def closed_loop(self,
                         concurrency: int,
                         duration_sec: int,
                         input_template: str,
                         headers: Optional[Dict[str, str]] = None,
                         think_time_ms: int = 0,
                         cold_n: int = 1,
                         phase_headers: bool = True) -> List[RequestResult]:
        """
        Closed-loop load generation.
        
        Args:
            concurrency: Number of concurrent workers
            duration_sec: Total duration in seconds
            input_template: Request template
            headers: Additional headers
            think_time_ms: Think time between requests per worker
            cold_n: Number of cold phase requests
            phase_headers: Whether to send phase headers
            
        Returns:
            List of request results
        """
        logger.info(f"Starting closed-loop test: {concurrency} workers, {duration_sec}s duration")
        
        results = []
        results_lock = asyncio.Lock()
        start_time = time.monotonic()
        end_time = start_time + duration_sec
        request_counter = 0
        
        self.memory_tracker.start()
        
        async def worker():
            nonlocal request_counter
            
            while time.monotonic() < end_time:
                # Determine phase
                async with results_lock:
                    request_num = request_counter
                    request_counter += 1
                
                phase = "COLD" if request_num < cold_n else "WARM"
                
                # Make request
                result = await self._make_request(
                    input_template, headers, phase, phase_headers
                )
                
                # Store result
                async with results_lock:
                    results.append(result)
                
                # Think time
                if think_time_ms > 0:
                    await asyncio.sleep(think_time_ms / 1000.0)
        
        # Start workers
        workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
        
        # Wait for duration or all workers to complete
        try:
            await asyncio.wait_for(
                asyncio.gather(*workers, return_exceptions=True),
                timeout=duration_sec + 5  # Small buffer
            )
        except asyncio.TimeoutError:
            # Cancel remaining workers
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
        
        memory_peak_mb, cpu_peak_pct = self.memory_tracker.stop()
        
        # Add memory/CPU info to results metadata
        for result in results:
            if hasattr(result, 'memory_peak_mb'):
                result.memory_peak_mb = memory_peak_mb
            if hasattr(result, 'cpu_peak_pct'):
                result.cpu_peak_pct = cpu_peak_pct
        
        logger.info(f"Closed-loop test completed: {len(results)} requests")
        return results
    
    async def open_loop(self,
                       rate_rps: float,
                       duration_sec: int,
                       input_template: str,
                       headers: Optional[Dict[str, str]] = None,
                       cold_n: int = 1,
                       phase_headers: bool = True) -> List[RequestResult]:
        """
        Open-loop load generation with accurate RPS control.
        
        Args:
            rate_rps: Target requests per second
            duration_sec: Total duration in seconds
            input_template: Request template
            headers: Additional headers
            cold_n: Number of cold phase requests
            phase_headers: Whether to send phase headers
            
        Returns:
            List of request results
        """
        logger.info(f"Starting open-loop test: {rate_rps} RPS, {duration_sec}s duration")
        
        results = []
        results_lock = asyncio.Lock()
        
        self.memory_tracker.start()
        
        # Compute precise schedule
        start_time = time.monotonic()
        schedule = compute_schedule(rate_rps, duration_sec, start_time)
        
        logger.debug(f"Computed schedule for {len(schedule)} requests over {duration_sec}s")
        
        async def scheduler():
            for i, request_time in enumerate(schedule):
                # Determine phase
                phase = "COLD" if i < cold_n else "WARM"
                
                # Wait until it's time for this request
                current_time = time.monotonic()
                wait_time = request_time - current_time
                
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                
                # Schedule request (fire and forget)
                asyncio.create_task(self._scheduled_request(
                    input_template, headers, phase, phase_headers, results, results_lock
                ))
        
        # Run scheduler
        await scheduler()
        
        # Wait for in-flight requests to complete
        await asyncio.sleep(min(5.0, self.timeout_ms))
        
        memory_peak_mb, cpu_peak_pct = self.memory_tracker.stop()
        
        # Add memory/CPU info to results metadata
        for result in results:
            if hasattr(result, 'memory_peak_mb'):
                result.memory_peak_mb = memory_peak_mb
            if hasattr(result, 'cpu_peak_pct'):
                result.cpu_peak_pct = cpu_peak_pct
        
        # Validate RPS accuracy
        actual_duration = time.monotonic() - start_time
        actual_rps = len(results) / actual_duration if actual_duration > 0 else 0
        rps_error = abs(actual_rps - rate_rps) / rate_rps if rate_rps > 0 else 0
        
        if rps_error > PERF_RPS_TOLERANCE:
            logger.warning(f"RPS accuracy outside tolerance: target={rate_rps:.2f}, actual={actual_rps:.2f}, error={rps_error:.1%}")
        else:
            logger.info(f"RPS accuracy within tolerance: target={rate_rps:.2f}, actual={actual_rps:.2f}, error={rps_error:.1%}")
        
        logger.info(f"Open-loop test completed: {len(results)} requests in {actual_duration:.2f}s")
        return results
    
    async def _scheduled_request(self,
                               input_template: str,
                               headers: Optional[Dict[str, str]],
                               phase: str,
                               phase_headers: bool,
                               results: List[RequestResult],
                               results_lock: asyncio.Lock):
        """Handle a scheduled request in open-loop mode."""
        result = await self._make_request(input_template, headers, phase, phase_headers)
        
        async with results_lock:
            results.append(result)
    
    async def _make_request(self,
                          input_template: str,
                          headers: Optional[Dict[str, str]],
                          phase: str,
                          phase_headers: bool) -> RequestResult:
        """
        Make a single request and measure performance.
        
        Args:
            input_template: Request template
            headers: Additional headers
            phase: "COLD" or "WARM"
            phase_headers: Whether to send phase headers
            
        Returns:
            RequestResult with timing and metadata
        """
        # Prepare headers
        request_headers = dict(headers or {})
        if phase_headers and PERF_OBSERVABILITY_HEADERS:
            request_headers["X-Perf-Phase"] = phase
        
        # Mock execution if no client
        if not self.client_callable:
            return await self._mock_request(phase)
        
        # Make actual request
        start_time = time.monotonic()
        success = False
        timeout = False
        response = ""
        tokens_out = 0
        cost = 0.0
        
        try:
            # Call client with timeout
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, self.client_callable, input_template, request_headers
                ),
                timeout=self.timeout_ms
            )
            success = True
            
            # Extract tokens/cost from response if available
            # This would need to be implemented based on your client interface
            tokens_out = self._extract_tokens(response)
            cost = self._extract_cost(response)
            
            # Extract observed latency from response headers if available
            # Note: This assumes the client could return headers in the future
            observed_header_latency_ms = self._extract_header_latency(response)
            
        except asyncio.TimeoutError:
            timeout = True
            logger.debug(f"Request timeout after {self.timeout_ms}s")
        except Exception as e:
            logger.debug(f"Request failed: {e}")
        
        end_time = time.monotonic()
        latency_ms = (end_time - start_time) * 1000
        
        return RequestResult(
            latency_ms=latency_ms,
            success=success,
            timeout=timeout,
            tokens_out=tokens_out if tokens_out > 0 else None,
            cost=cost if cost > 0 else None,
            phase=phase
        )
    
    async def _mock_request(self, phase: str) -> RequestResult:
        """Mock request for testing purposes."""
        # Simulate realistic latency with some variance
        base_latency = 150.0 if phase == "WARM" else 300.0  # Cold start penalty
        latency_ms = base_latency + random.gauss(0, 50)  # Add noise
        latency_ms = max(10.0, latency_ms)  # Minimum 10ms
        
        # Simulate request time
        await asyncio.sleep(latency_ms / 1000.0)
        
        # Mock occasional failures
        success = random.random() > 0.01  # 1% failure rate
        timeout = not success and random.random() < 0.3  # 30% of failures are timeouts
        
        # Mock token/cost data
        tokens_out = random.randint(50, 200) if success else 0
        cost = tokens_out * 0.0001 if success else 0.0
        
        return RequestResult(
            latency_ms=latency_ms,
            success=success,
            timeout=timeout,
            tokens_out=tokens_out,
            cost=cost,
            phase=phase,
            observed_header_latency_ms=observed_header_latency_ms if 'observed_header_latency_ms' in locals() else None
        )
    
    def _extract_tokens(self, response: str) -> int:
        """Extract token count from response (placeholder implementation)."""
        # This would need to be implemented based on your client interface
        # For now, return a mock value
        return len(response.split()) * 2 if response else 0
    
    def _extract_cost(self, response: str) -> float:
        """Extract cost from response (placeholder implementation)."""
        # This would need to be implemented based on your client interface
        # For now, return a mock value
        tokens = self._extract_tokens(response)
        return tokens * 0.0001 if tokens > 0 else 0.0
    
    def _extract_header_latency(self, response: str) -> Optional[float]:
        """
        Extract observed latency from X-Latency-MS header (placeholder implementation).
        
        Args:
            response: Response from client (would need to include headers in future)
            
        Returns:
            Observed latency in milliseconds or None if not available
        """
        # This is a placeholder implementation
        # In a real implementation, the client would need to return headers
        # and this method would parse the X-Latency-MS header
        
        # For now, return None to indicate "N/A"
        return None


class MemoryTracker:
    """Track memory and CPU usage during test execution."""
    
    def __init__(self):
        self.monitoring = False
        self.peak_memory_mb = 0.0
        self.peak_cpu_pct = 0.0
        self._monitor_task = None
        
        # Try to import psutil for system monitoring
        try:
            import psutil
            self.psutil = psutil
            self.process = psutil.Process()
        except ImportError:
            self.psutil = None
            self.process = None
    
    def start(self):
        """Start monitoring system resources."""
        if not self.psutil:
            return
        
        self.monitoring = True
        self.peak_memory_mb = 0.0
        self.peak_cpu_pct = 0.0
        self._monitor_task = asyncio.create_task(self._monitor_loop())
    
    def stop(self) -> tuple[Optional[float], Optional[float]]:
        """Stop monitoring and return peak values."""
        if not self.psutil:
            return None, None
        
        self.monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
        
        return self.peak_memory_mb, self.peak_cpu_pct
    
    async def _monitor_loop(self):
        """Monitor system resources in a loop."""
        try:
            while self.monitoring:
                if self.process:
                    # Memory usage
                    memory_info = self.process.memory_info()
                    memory_mb = memory_info.rss / 1024 / 1024
                    self.peak_memory_mb = max(self.peak_memory_mb, memory_mb)
                    
                    # CPU usage
                    cpu_pct = self.process.cpu_percent()
                    self.peak_cpu_pct = max(self.peak_cpu_pct, cpu_pct)
                
                await asyncio.sleep(0.1)  # Sample every 100ms
        except asyncio.CancelledError:
            pass
