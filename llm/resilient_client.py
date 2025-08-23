"""
Resilient client wrapper for hardening outbound LLM/provider calls.
"""
import asyncio
import os
import time
import random
import logging
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, Union, Awaitable
from dataclasses import dataclass
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

T = TypeVar('T')

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class ResilienceConfig:
    """Configuration for resilient client."""
    timeout_s: float = 20.0
    max_retries: int = 2
    backoff_base_ms: int = 200
    circuit_fails: int = 5
    circuit_reset_s: float = 30.0
    
    @classmethod
    def from_env(cls) -> 'ResilienceConfig':
        """Load configuration from environment variables."""
        return cls(
            timeout_s=float(os.getenv("PROVIDER_TIMEOUT_S", "20")),
            max_retries=int(os.getenv("PROVIDER_MAX_RETRIES", "2")),
            backoff_base_ms=int(os.getenv("PROVIDER_BACKOFF_BASE_MS", "200")),
            circuit_fails=int(os.getenv("PROVIDER_CIRCUIT_FAILS", "5")),
            circuit_reset_s=float(os.getenv("PROVIDER_CIRCUIT_RESET_S", "30"))
        )


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """Circuit breaker implementation."""
    
    def __init__(self, config: ResilienceConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.success_count = 0
        
    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        now = time.time()
        
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if now - self.last_failure_time >= self.config.circuit_reset_s:
                logger.info("Circuit breaker moving to half-open state", 
                          extra={"event": "circuit_half_open", "reset_time": self.config.circuit_reset_s})
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        elif self.state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self):
        """Record successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker closing after successful test", 
                       extra={"event": "circuit_close"})
            self.state = CircuitState.CLOSED
        
        self.failure_count = 0
        self.success_count += 1
    
    def record_failure(self):
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            logger.warning("Circuit breaker opening after failed test", 
                          extra={"event": "circuit_open", "failure_count": self.failure_count})
            self.state = CircuitState.OPEN
        elif self.state == CircuitState.CLOSED and self.failure_count >= self.config.circuit_fails:
            logger.warning("Circuit breaker opening due to consecutive failures", 
                          extra={"event": "circuit_open", "failure_count": self.failure_count, 
                                "threshold": self.config.circuit_fails})
            self.state = CircuitState.OPEN


def is_transient_error(error: Exception) -> bool:
    """Check if an error is transient and should be retried."""
    # Network/timeout errors
    if isinstance(error, (asyncio.TimeoutError, ConnectionError, OSError)):
        return True
    
    # HTTP errors - only retry 5xx, not 4xx
    error_str = str(error).lower()
    
    # OpenAI API errors
    if "openai" in error_str:
        if any(code in error_str for code in ["500", "502", "503", "504", "timeout"]):
            return True
        if any(code in error_str for code in ["400", "401", "403", "404", "429"]):
            return False
    
    # Anthropic API errors
    if "anthropic" in error_str:
        if any(code in error_str for code in ["500", "502", "503", "504", "timeout"]):
            return True
        if any(code in error_str for code in ["400", "401", "403", "404", "429"]):
            return False
    
    # Generic HTTP status patterns
    if any(pattern in error_str for pattern in ["5", "timeout", "connection", "network"]):
        return True
    
    if any(pattern in error_str for pattern in ["4", "unauthorized", "forbidden", "not found"]):
        return False
    
    # Default to transient for unknown errors
    return True


class ResilientClient:
    """Resilient wrapper for LLM provider calls."""
    
    def __init__(self, config: Optional[ResilienceConfig] = None):
        self.config = config or ResilienceConfig.from_env()
        self.circuit_breaker = CircuitBreaker(self.config)
        
    async def call_with_resilience(self, func: Callable[[], T], operation_name: str = "provider_call") -> T:
        """Execute function with resilience patterns."""
        if not self.circuit_breaker.can_execute():
            logger.warning("Circuit breaker is open, failing fast", 
                          extra={"event": "circuit_open", "operation": operation_name})
            raise CircuitBreakerError("Circuit breaker is open")
        
        last_error = None
        
        for attempt in range(self.config.max_retries + 1):  # +1 for initial attempt
            try:
                start_time = time.time()
                logger.debug("Starting provider call", 
                           extra={"event": "provider_call", "operation": operation_name, 
                                 "attempt": attempt + 1, "max_attempts": self.config.max_retries + 1})
                
                # Execute with timeout
                result = await asyncio.wait_for(
                    self._execute_sync_or_async(func),
                    timeout=self.config.timeout_s
                )
                
                duration_ms = (time.time() - start_time) * 1000
                logger.info("Provider call succeeded", 
                          extra={"event": "provider_success", "operation": operation_name,
                                "attempt": attempt + 1, "duration_ms": duration_ms})
                
                self.circuit_breaker.record_success()
                return result
                
            except Exception as error:
                last_error = error
                duration_ms = (time.time() - start_time) * 1000
                
                logger.warning("Provider call failed", 
                             extra={"event": "provider_error", "operation": operation_name,
                                   "attempt": attempt + 1, "error": str(error), 
                                   "duration_ms": duration_ms})
                
                # Check if we should retry
                if attempt < self.config.max_retries and is_transient_error(error):
                    # Calculate backoff with jitter
                    backoff_ms = self.config.backoff_base_ms * (2 ** attempt)
                    jitter_ms = random.randint(0, 100)
                    delay_ms = backoff_ms + jitter_ms
                    delay_s = delay_ms / 1000.0
                    
                    logger.info("Retrying provider call after backoff", 
                              extra={"event": "retry", "operation": operation_name,
                                    "attempt": attempt + 1, "delay_ms": delay_ms, 
                                    "backoff_ms": backoff_ms, "jitter_ms": jitter_ms})
                    
                    await asyncio.sleep(delay_s)
                    continue
                else:
                    # No more retries or non-transient error
                    break
        
        # All retries exhausted or non-transient error
        self.circuit_breaker.record_failure()
        
        if last_error:
            raise last_error
        else:
            raise RuntimeError("All retries exhausted")
    
    async def _execute_sync_or_async(self, func: Callable[[], T]) -> T:
        """Execute function whether it's sync or async."""
        if asyncio.iscoroutinefunction(func):
            return await func()
        else:
            # Run sync function in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func)
    
    def get_circuit_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state for monitoring."""
        return {
            "state": self.circuit_breaker.state.value,
            "failure_count": self.circuit_breaker.failure_count,
            "success_count": self.circuit_breaker.success_count,
            "last_failure_time": self.circuit_breaker.last_failure_time,
            "config": {
                "timeout_s": self.config.timeout_s,
                "max_retries": self.config.max_retries,
                "circuit_fails": self.config.circuit_fails,
                "circuit_reset_s": self.config.circuit_reset_s
            }
        }


# Global resilient client instance
_resilient_client: Optional[ResilientClient] = None


def get_resilient_client() -> ResilientClient:
    """Get global resilient client instance."""
    global _resilient_client
    if _resilient_client is None:
        _resilient_client = ResilientClient()
    return _resilient_client


def reset_resilient_client():
    """Reset global resilient client (useful for testing)."""
    global _resilient_client
    _resilient_client = None


# Decorator for easy resilience wrapping
def resilient(operation_name: str = "provider_call"):
    """Decorator to make functions resilient."""
    def decorator(func: Callable[..., T]) -> Callable[..., Awaitable[T]]:
        async def wrapper(*args, **kwargs) -> T:
            client = get_resilient_client()
            bound_func = lambda: func(*args, **kwargs)
            return await client.call_with_resilience(bound_func, operation_name)
        return wrapper
    return decorator
