"""
Tests for resilient client wrapper.
"""
import pytest
import asyncio
import time
from unittest.mock import patch, AsyncMock, MagicMock
from llm.resilient_client import (
    ResilientClient, ResilienceConfig, CircuitBreaker, CircuitState,
    CircuitBreakerError, is_transient_error, get_resilient_client, reset_resilient_client
)


class TestResilienceConfig:
    """Test resilience configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ResilienceConfig()
        assert config.timeout_s == 20.0
        assert config.max_retries == 2
        assert config.backoff_base_ms == 200
        assert config.circuit_fails == 5
        assert config.circuit_reset_s == 30.0
    
    @patch.dict('os.environ', {
        'PROVIDER_TIMEOUT_S': '15',
        'PROVIDER_MAX_RETRIES': '3',
        'PROVIDER_BACKOFF_BASE_MS': '100',
        'PROVIDER_CIRCUIT_FAILS': '3',
        'PROVIDER_CIRCUIT_RESET_S': '60'
    })
    def test_config_from_env(self):
        """Test configuration from environment variables."""
        config = ResilienceConfig.from_env()
        assert config.timeout_s == 15.0
        assert config.max_retries == 3
        assert config.backoff_base_ms == 100
        assert config.circuit_fails == 3
        assert config.circuit_reset_s == 60.0


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_initial_state(self):
        """Test circuit breaker starts in closed state."""
        config = ResilienceConfig(circuit_fails=3, circuit_reset_s=10)
        breaker = CircuitBreaker(config)
        
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.can_execute() is True
    
    def test_record_success(self):
        """Test recording successful operations."""
        config = ResilienceConfig(circuit_fails=3)
        breaker = CircuitBreaker(config)
        
        breaker.record_success()
        assert breaker.failure_count == 0
        assert breaker.success_count == 1
        assert breaker.state == CircuitState.CLOSED
    
    def test_circuit_opens_after_failures(self):
        """Test circuit opens after consecutive failures."""
        config = ResilienceConfig(circuit_fails=3)
        breaker = CircuitBreaker(config)
        
        # Record failures
        for i in range(3):
            breaker.record_failure()
            if i < 2:
                assert breaker.state == CircuitState.CLOSED
            else:
                assert breaker.state == CircuitState.OPEN
        
        # Should not allow execution when open
        assert breaker.can_execute() is False
    
    def test_circuit_half_open_after_timeout(self):
        """Test circuit moves to half-open after reset timeout."""
        config = ResilienceConfig(circuit_fails=2, circuit_reset_s=0.1)
        breaker = CircuitBreaker(config)
        
        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        
        # Wait for reset timeout
        time.sleep(0.2)
        
        # Should move to half-open
        assert breaker.can_execute() is True
        assert breaker.state == CircuitState.HALF_OPEN
    
    def test_circuit_closes_on_success_in_half_open(self):
        """Test circuit closes on successful operation in half-open state."""
        config = ResilienceConfig(circuit_fails=2, circuit_reset_s=0.1)
        breaker = CircuitBreaker(config)
        
        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        time.sleep(0.2)
        breaker.can_execute()  # Move to half-open
        
        # Record success should close circuit
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
    
    def test_circuit_reopens_on_failure_in_half_open(self):
        """Test circuit reopens on failure in half-open state."""
        config = ResilienceConfig(circuit_fails=2, circuit_reset_s=0.1)
        breaker = CircuitBreaker(config)
        
        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        time.sleep(0.2)
        breaker.can_execute()  # Move to half-open
        
        # Record failure should reopen circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN


class TestTransientErrorDetection:
    """Test transient error detection logic."""
    
    def test_network_errors_are_transient(self):
        """Test network-related errors are considered transient."""
        assert is_transient_error(ConnectionError("Connection failed")) is True
        assert is_transient_error(OSError("Network unreachable")) is True
        assert is_transient_error(asyncio.TimeoutError()) is True
    
    def test_http_5xx_errors_are_transient(self):
        """Test HTTP 5xx errors are considered transient."""
        assert is_transient_error(Exception("HTTP 500 Internal Server Error")) is True
        assert is_transient_error(Exception("HTTP 502 Bad Gateway")) is True
        assert is_transient_error(Exception("HTTP 503 Service Unavailable")) is True
        assert is_transient_error(Exception("HTTP 504 Gateway Timeout")) is True
        assert is_transient_error(Exception("Request timeout")) is True
    
    def test_http_4xx_errors_are_not_transient(self):
        """Test HTTP 4xx errors are not considered transient."""
        assert is_transient_error(Exception("HTTP 400 Bad Request")) is False
        assert is_transient_error(Exception("HTTP 401 Unauthorized")) is False
        assert is_transient_error(Exception("HTTP 403 Forbidden")) is False
        assert is_transient_error(Exception("HTTP 404 Not Found")) is False
        assert is_transient_error(Exception("HTTP 429 Too Many Requests")) is False
    
    def test_openai_specific_errors(self):
        """Test OpenAI-specific error handling."""
        assert is_transient_error(Exception("openai 500 error")) is True
        assert is_transient_error(Exception("openai 503 service unavailable")) is True
        assert is_transient_error(Exception("openai timeout")) is True
        assert is_transient_error(Exception("openai 400 bad request")) is False
        assert is_transient_error(Exception("openai 401 unauthorized")) is False
    
    def test_anthropic_specific_errors(self):
        """Test Anthropic-specific error handling."""
        assert is_transient_error(Exception("anthropic 500 error")) is True
        assert is_transient_error(Exception("anthropic 503 error")) is True
        assert is_transient_error(Exception("anthropic 400 error")) is False
        assert is_transient_error(Exception("anthropic 401 error")) is False


class TestResilientClient:
    """Test resilient client functionality."""
    
    def test_successful_call_no_retries(self):
        """Test successful call without retries."""
        config = ResilienceConfig(timeout_s=1, max_retries=2)
        client = ResilientClient(config)
        
        def success_func():
            return "success"
        
        async def test():
            result = await client.call_with_resilience(success_func, "test_op")
            assert result == "success"
        
        asyncio.run(test())
        
        # Circuit should remain closed
        assert client.circuit_breaker.state == CircuitState.CLOSED
        assert client.circuit_breaker.success_count == 1
    
    def test_retry_on_transient_error(self):
        """Test retry behavior on transient errors."""
        config = ResilienceConfig(timeout_s=1, max_retries=2, backoff_base_ms=10)
        client = ResilientClient(config)
        
        call_count = 0
        
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Transient error")
            return "success"
        
        async def test():
            result = await client.call_with_resilience(flaky_func, "test_op")
            assert result == "success"
            assert call_count == 3  # Initial + 2 retries
        
        asyncio.run(test())
    
    def test_no_retry_on_non_transient_error(self):
        """Test no retry on non-transient errors."""
        config = ResilienceConfig(timeout_s=1, max_retries=2)
        client = ResilientClient(config)
        
        call_count = 0
        
        def non_transient_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("HTTP 400 Bad Request")
        
        async def test():
            with pytest.raises(ValueError):
                await client.call_with_resilience(non_transient_func, "test_op")
            assert call_count == 1  # No retries
        
        asyncio.run(test())
    
    def test_circuit_breaker_opens_and_fast_fails(self):
        """Test circuit breaker opens after consecutive failures."""
        config = ResilienceConfig(timeout_s=1, max_retries=0, circuit_fails=2)
        client = ResilientClient(config)
        
        def failing_func():
            raise ConnectionError("Always fails")
        
        async def test():
            # First two calls should fail and open circuit
            with pytest.raises(ConnectionError):
                await client.call_with_resilience(failing_func, "test_op")
            
            with pytest.raises(ConnectionError):
                await client.call_with_resilience(failing_func, "test_op")
            
            # Circuit should be open now
            assert client.circuit_breaker.state == CircuitState.OPEN
            
            # Next call should fast-fail with circuit breaker error
            with pytest.raises(CircuitBreakerError):
                await client.call_with_resilience(failing_func, "test_op")
        
        asyncio.run(test())
    
    def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker recovery through half-open state."""
        config = ResilienceConfig(timeout_s=1, max_retries=0, circuit_fails=2, circuit_reset_s=0.1)
        client = ResilientClient(config)
        
        call_count = 0
        
        def recovering_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Initial failures")
            return "recovered"
        
        async def test():
            # Open the circuit
            with pytest.raises(ConnectionError):
                await client.call_with_resilience(recovering_func, "test_op")
            with pytest.raises(ConnectionError):
                await client.call_with_resilience(recovering_func, "test_op")
            
            assert client.circuit_breaker.state == CircuitState.OPEN
            
            # Wait for reset timeout
            await asyncio.sleep(0.2)
            
            # Next call should succeed and close circuit
            result = await client.call_with_resilience(recovering_func, "test_op")
            assert result == "recovered"
            assert client.circuit_breaker.state == CircuitState.CLOSED
        
        asyncio.run(test())
    
    def test_timeout_handling(self):
        """Test timeout handling."""
        config = ResilienceConfig(timeout_s=0.1, max_retries=0)
        client = ResilientClient(config)
        
        async def slow_func():
            await asyncio.sleep(0.2)
            return "should not reach"
        
        async def test():
            with pytest.raises(asyncio.TimeoutError):
                await client.call_with_resilience(slow_func, "test_op")
        
        asyncio.run(test())
    
    def test_async_function_execution(self):
        """Test execution of async functions."""
        config = ResilienceConfig(timeout_s=1)
        client = ResilientClient(config)
        
        async def async_func():
            await asyncio.sleep(0.01)
            return "async_result"
        
        async def test():
            result = await client.call_with_resilience(async_func, "test_op")
            assert result == "async_result"
        
        asyncio.run(test())
    
    def test_get_circuit_state(self):
        """Test circuit state monitoring."""
        config = ResilienceConfig(circuit_fails=3)
        client = ResilientClient(config)
        
        state = client.get_circuit_state()
        
        assert state["state"] == "closed"
        assert state["failure_count"] == 0
        assert state["success_count"] == 0
        assert "config" in state
        assert state["config"]["circuit_fails"] == 3


class TestGlobalClient:
    """Test global resilient client management."""
    
    def test_get_global_client(self):
        """Test getting global resilient client."""
        reset_resilient_client()  # Start fresh
        
        client1 = get_resilient_client()
        client2 = get_resilient_client()
        
        # Should return same instance
        assert client1 is client2
    
    def test_reset_global_client(self):
        """Test resetting global resilient client."""
        client1 = get_resilient_client()
        reset_resilient_client()
        client2 = get_resilient_client()
        
        # Should return different instance after reset
        assert client1 is not client2


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""
    
    def test_flaky_service_recovery(self):
        """Test recovery from flaky service behavior."""
        config = ResilienceConfig(
            timeout_s=1, 
            max_retries=3, 
            backoff_base_ms=10,
            circuit_fails=5,
            circuit_reset_s=0.1
        )
        client = ResilientClient(config)
        
        call_count = 0
        
        def flaky_service():
            nonlocal call_count
            call_count += 1
            
            # Fail first few calls, then succeed
            if call_count in [1, 3, 5]:
                raise ConnectionError(f"Transient failure {call_count}")
            return f"success_{call_count}"
        
        async def test():
            # Should eventually succeed despite transient failures
            result = await client.call_with_resilience(flaky_service, "flaky_service")
            assert result == "success_2"
            
            # Reset count and try again
            nonlocal call_count
            call_count = 0  # Reset completely
            
            result = await client.call_with_resilience(flaky_service, "flaky_service")
            assert result == "success_2"  # Should be success_2 again
        
        asyncio.run(test())
    
    def test_cascading_failure_protection(self):
        """Test protection against cascading failures."""
        config = ResilienceConfig(
            timeout_s=0.1,
            max_retries=1,
            circuit_fails=3,
            circuit_reset_s=0.2
        )
        client = ResilientClient(config)
        
        def always_timeout():
            time.sleep(0.2)  # Always timeout
            return "should not reach"
        
        async def test():
            # Generate enough failures to open circuit
            for i in range(3):
                with pytest.raises(asyncio.TimeoutError):
                    await client.call_with_resilience(always_timeout, "timeout_service")
            
            # Circuit should be open now
            assert client.circuit_breaker.state == CircuitState.OPEN
            
            # Fast failures should happen immediately
            start_time = time.time()
            with pytest.raises(CircuitBreakerError):
                await client.call_with_resilience(always_timeout, "timeout_service")
            fast_fail_time = time.time() - start_time
            
            # Should fail much faster than timeout
            assert fast_fail_time < 0.05
        
        asyncio.run(test())
