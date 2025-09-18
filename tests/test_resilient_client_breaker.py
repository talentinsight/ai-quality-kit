"""Tests for resilient client circuit breaker functionality."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from llm.resilient_client import ResilientClient, ResilienceConfig, CircuitBreakerError


class TestResilientClientBreaker:
    """Test circuit breaker functionality in resilient client."""
    
    def test_breaker_enabled_by_default(self):
        """Test that circuit breaker is enabled by default."""
        config = ResilienceConfig.from_env()
        assert config.breaker_enabled is True
        
        client = ResilientClient()
        assert client.config.breaker_enabled is True
    
    def test_breaker_can_be_disabled(self):
        """Test that circuit breaker can be disabled via environment."""
        with patch.dict('os.environ', {'RESILIENT_BREAKER_ENABLED': 'false'}):
            config = ResilienceConfig.from_env()
            assert config.breaker_enabled is False
            
            client = ResilientClient(config)
            assert client.config.breaker_enabled is False
    
    @pytest.mark.asyncio
    async def test_4xx_no_retry(self):
        """Test that 4xx errors are not retried."""
        config = ResilienceConfig(max_retries=3, breaker_enabled=True)
        client = ResilientClient(config)
        
        call_count = 0
        async def failing_call():
            nonlocal call_count
            call_count += 1
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Bad Request")
        
        with pytest.raises(Exception):
            await client.call_with_resilience(failing_call, "test_4xx")
        
        # Should only be called once (no retries for 4xx)
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_429_no_retry(self):
        """Test that 429 errors are not retried."""
        config = ResilienceConfig(max_retries=3, breaker_enabled=True)
        client = ResilientClient(config)
        
        call_count = 0
        async def failing_call():
            nonlocal call_count
            call_count += 1
            from fastapi import HTTPException
            raise HTTPException(status_code=429, detail="Rate Limited")
        
        with pytest.raises(Exception):
            await client.call_with_resilience(failing_call, "test_429")
        
        # Should only be called once (no retries for 429)
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_5xx_with_bounded_retry(self):
        """Test that 5xx errors are retried with bounds."""
        config = ResilienceConfig(max_retries=2, backoff_base_ms=10, breaker_enabled=True)
        client = ResilientClient(config)
        
        call_count = 0
        async def failing_call():
            nonlocal call_count
            call_count += 1
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail="Internal Server Error")
        
        with pytest.raises(Exception):
            await client.call_with_resilience(failing_call, "test_5xx")
        
        # Should be called max_retries + 1 times (initial + retries)
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_timeout_with_bounded_retry(self):
        """Test that timeouts are retried with bounds."""
        config = ResilienceConfig(max_retries=2, timeout_s=0.1, backoff_base_ms=10, breaker_enabled=True)
        client = ResilientClient(config)
        
        call_count = 0
        async def slow_call():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.2)  # Longer than timeout
            return "success"
        
        with pytest.raises(Exception):
            await client.call_with_resilience(slow_call, "test_timeout")
        
        # Should be called max_retries + 1 times
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self):
        """Test that circuit breaker opens after configured failures."""
        config = ResilienceConfig(circuit_fails=2, max_retries=0, breaker_enabled=True)
        client = ResilientClient(config)
        
        async def failing_call():
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail="Server Error")
        
        # First failure
        with pytest.raises(Exception):
            await client.call_with_resilience(failing_call, "test_1")
        
        # Second failure - should open circuit
        with pytest.raises(Exception):
            await client.call_with_resilience(failing_call, "test_2")
        
        # Third call should fail fast due to open circuit
        with pytest.raises(CircuitBreakerError):
            await client.call_with_resilience(failing_call, "test_3")
    
    @pytest.mark.asyncio
    async def test_circuit_half_open_recovery(self):
        """Test circuit breaker half-open to closed transition."""
        config = ResilienceConfig(circuit_fails=1, circuit_reset_s=0.1, max_retries=0, breaker_enabled=True)
        client = ResilientClient(config)
        
        # Fail once to open circuit
        async def failing_call():
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail="Server Error")
        
        with pytest.raises(Exception):
            await client.call_with_resilience(failing_call, "fail")
        
        # Wait for reset time
        await asyncio.sleep(0.2)
        
        # Should now allow one test call (half-open)
        success_count = 0
        async def success_call():
            nonlocal success_count
            success_count += 1
            return "success"
        
        result = await client.call_with_resilience(success_call, "success")
        assert result == "success"
        assert success_count == 1
    
    @pytest.mark.asyncio
    async def test_breaker_disabled_bypass(self):
        """Test that circuit breaker can be bypassed when disabled."""
        config = ResilienceConfig(circuit_fails=1, max_retries=0, breaker_enabled=False)
        client = ResilientClient(config)
        
        # Even with multiple failures, circuit should not trip when disabled
        async def failing_call():
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail="Server Error")
        
        # Multiple failures should not trigger circuit breaker when disabled
        for i in range(5):
            with pytest.raises(Exception):
                await client.call_with_resilience(failing_call, f"test_{i}")
        
        # Circuit should still allow calls (no CircuitBreakerError)
        with pytest.raises(Exception) as exc_info:
            await client.call_with_resilience(failing_call, "final_test")
        
        # Should get original exception, not CircuitBreakerError
        assert not isinstance(exc_info.value, CircuitBreakerError)
    
    def test_environment_variable_defaults(self):
        """Test that all environment variables have proper defaults."""
        config = ResilienceConfig.from_env()
        
        assert config.timeout_s == 20.0
        assert config.max_retries == 2
        assert config.backoff_base_ms == 200
        assert config.circuit_fails == 5
        assert config.circuit_reset_s == 30.0
        assert config.concurrency == 10
        assert config.queue_depth == 50
        assert config.breaker_enabled is True
    
    def test_environment_variable_override(self):
        """Test that environment variables can override defaults."""
        env_vars = {
            'PROVIDER_TIMEOUT_S': '15',
            'PROVIDER_MAX_RETRIES': '3',
            'PROVIDER_BACKOFF_BASE_MS': '100',
            'PROVIDER_CIRCUIT_FAILS': '3',
            'PROVIDER_CIRCUIT_RESET_S': '60',
            'PROVIDER_CONCURRENCY': '5',
            'PROVIDER_QUEUE_DEPTH': '25',
            'RESILIENT_BREAKER_ENABLED': 'false'
        }
        
        with patch.dict('os.environ', env_vars):
            config = ResilienceConfig.from_env()
            
            assert config.timeout_s == 15.0
            assert config.max_retries == 3
            assert config.backoff_base_ms == 100
            assert config.circuit_fails == 3
            assert config.circuit_reset_s == 60.0
            assert config.concurrency == 5
            assert config.queue_depth == 25
            assert config.breaker_enabled is False
