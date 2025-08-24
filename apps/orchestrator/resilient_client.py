"""Resilient client for provider robustness testing."""

import asyncio
import time
import random
from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass
import httpx


@dataclass
class ResilienceResult:
    """Result of a resilience test."""
    request_id: str
    started_at: float
    ended_at: float
    latency_ms: int
    outcome: Literal["success", "timeout", "upstream_5xx", "upstream_429", "circuit_open", "client_4xx"]
    attempts: int
    error_class: Optional[str]
    mode: Literal["passive", "synthetic"]


class CircuitBreaker:
    """Simple circuit breaker implementation."""
    
    def __init__(self, fail_threshold: int = 5, reset_timeout: int = 30):
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half_open
    
    def is_open(self) -> bool:
        """Check if circuit is open."""
        if self.state == "open":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "half_open"
                return False
            return True
        return False
    
    def record_success(self):
        """Record successful call."""
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.fail_threshold:
            self.state = "open"


class ResilientClient:
    """Client with resilience features for testing."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.semaphores: Dict[str, asyncio.Semaphore] = {}
    
    def _get_circuit_breaker(self, key: str, config: Dict[str, Any]) -> CircuitBreaker:
        """Get or create circuit breaker for key."""
        if key not in self.circuit_breakers:
            circuit_config = config.get("circuit", {"fails": 5, "reset_s": 30})
            self.circuit_breakers[key] = CircuitBreaker(
                fail_threshold=circuit_config.get("fails", 5),
                reset_timeout=circuit_config.get("reset_s", 30)
            )
        return self.circuit_breakers[key]
    
    def _get_semaphore(self, key: str, concurrency: int) -> asyncio.Semaphore:
        """Get or create semaphore for concurrency control."""
        if key not in self.semaphores:
            self.semaphores[key] = asyncio.Semaphore(concurrency)
        return self.semaphores[key]
    
    async def _make_synthetic_call(self, request_id: str, config: Dict[str, Any]) -> ResilienceResult:
        """Make synthetic call with controlled failures."""
        started_at = time.time()
        
        # Simulate different failure modes in synthetic mode
        failure_types = ["success", "timeout", "upstream_5xx", "upstream_429"]
        weights = [0.6, 0.15, 0.15, 0.1]  # 60% success, 40% various failures
        
        outcome_str = random.choices(failure_types, weights=weights)[0]
        outcome = outcome_str  # type: ignore
        
        # Simulate realistic latencies
        if outcome == "timeout":
            await asyncio.sleep(config.get("timeout_ms", 20000) / 1000.0)
            latency_ms = config.get("timeout_ms", 20000)
        elif outcome == "upstream_5xx":
            await asyncio.sleep(random.uniform(0.1, 0.5))
            latency_ms = int(random.uniform(100, 500))
        elif outcome == "upstream_429":
            await asyncio.sleep(random.uniform(0.05, 0.2))
            latency_ms = int(random.uniform(50, 200))
        else:  # success
            await asyncio.sleep(random.uniform(0.1, 1.0))
            latency_ms = int(random.uniform(100, 1000))
        
        ended_at = time.time()
        
        return ResilienceResult(
            request_id=request_id,
            started_at=started_at,
            ended_at=ended_at,
            latency_ms=latency_ms,
            outcome=outcome,  # type: ignore
            attempts=1,
            error_class=f"Synthetic{outcome.title()}Error" if outcome != "success" else None,
            mode="synthetic"
        )
    
    async def _make_real_call(self, query: str, provider: str, model: str, config: Dict[str, Any]) -> ResilienceResult:
        """Make real API call."""
        import httpx
        
        request_id = f"req_{int(time.time() * 1000)}"
        started_at = time.time()
        attempts = 0
        last_error = None
        
        timeout_ms = config.get("timeout_ms", 20000)
        max_retries = config.get("retries", 0)
        
        for attempt in range(max_retries + 1):
            attempts += 1
            
            try:
                async with httpx.AsyncClient(timeout=timeout_ms / 1000.0) as client:
                    response = await client.post(
                        "http://localhost:8000/ask",
                        json={"query": query, "provider": provider, "model": model}
                    )
                    
                    ended_at = time.time()
                    latency_ms = int((ended_at - started_at) * 1000)
                    
                    if response.status_code == 200:
                        return ResilienceResult(
                            request_id=request_id,
                            started_at=started_at,
                            ended_at=ended_at,
                            latency_ms=latency_ms,
                            outcome="success",
                            attempts=attempts,
                            error_class=None,
                            mode="passive"
                        )
                    elif response.status_code == 429:
                        # Don't retry on 429
                        break
                    elif 400 <= response.status_code < 500:
                        # Don't retry on 4xx
                        break
                    else:
                        # Retry on 5xx
                        last_error = f"HTTP {response.status_code}"
                        if attempt < max_retries:
                            await asyncio.sleep(2 ** attempt * 0.1)  # Exponential backoff
                        continue
                        
            except asyncio.TimeoutError:
                last_error = "TimeoutError"
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt * 0.1)
                continue
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt * 0.1)
                continue
        
        # All attempts failed
        ended_at = time.time()
        latency_ms = int((ended_at - started_at) * 1000)
        
        # Classify the outcome
        if "TimeoutError" in str(last_error):
            outcome = "timeout"
        elif "429" in str(last_error):
            outcome = "upstream_429"
        elif any(code in str(last_error) for code in ["500", "502", "503", "504"]):
            outcome = "upstream_5xx"
        elif any(code in str(last_error) for code in ["400", "401", "403", "404"]):
            outcome = "client_4xx"
        else:
            outcome = "upstream_5xx"  # Default classification
        
        return ResilienceResult(
            request_id=request_id,
            started_at=started_at,
            ended_at=ended_at,
            latency_ms=latency_ms,
            outcome=outcome,
            attempts=attempts,
            error_class=last_error,
            mode="passive"
        )
    
    async def call_with_resilience(self, query: str, provider: str, model: str, config: Dict[str, Any]) -> ResilienceResult:
        """Make a call with resilience features."""
        request_id = f"req_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        key = f"{provider}:{model}"
        
        # Check circuit breaker
        circuit_breaker = self._get_circuit_breaker(key, config)
        if circuit_breaker.is_open():
            return ResilienceResult(
                request_id=request_id,
                started_at=time.time(),
                ended_at=time.time(),
                latency_ms=0,
                outcome="circuit_open",
                attempts=0,
                error_class="CircuitBreakerOpenError",
                mode=config.get("mode", "passive")
            )
        
        # Respect concurrency limits
        concurrency = config.get("concurrency", 10)
        semaphore = self._get_semaphore(key, concurrency)
        
        async with semaphore:
            try:
                if config.get("mode") == "synthetic" and provider == "mock":
                    result = await self._make_synthetic_call(request_id, config)
                else:
                    result = await self._make_real_call(query, provider, model, config)
                
                # Update circuit breaker
                if result.outcome == "success":
                    circuit_breaker.record_success()
                elif result.outcome in ["upstream_5xx", "timeout"]:
                    circuit_breaker.record_failure()
                
                return result
                
            except Exception as e:
                circuit_breaker.record_failure()
                return ResilienceResult(
                    request_id=request_id,
                    started_at=time.time(),
                    ended_at=time.time(),
                    latency_ms=0,
                    outcome="upstream_5xx",
                    attempts=1,
                    error_class=str(e),
                    mode=config.get("mode", "passive")
                )
