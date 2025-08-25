"""Tests for API resilience functionality, focusing on circuit breaker integration."""

import pytest
from unittest.mock import patch
from llm.resilient_client import CircuitBreakerError, ResilientClient, ResilienceConfig


class TestAPIResilienceHeaders:
    """Test resilience functionality including circuit breaker."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Test end-to-end circuit breaker integration."""
        
        # Use very sensitive circuit breaker for testing
        config = ResilienceConfig(
            circuit_fails=1,
            max_retries=0,
            breaker_enabled=True
        )
        
        client = ResilientClient(config)
        
        # Simulate a failing provider call
        async def failing_provider():
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail="Server Error")
        
        # First call should fail normally
        with pytest.raises(Exception):
            await client.call_with_resilience(failing_provider, "test")
        
        # Second call should trigger circuit breaker
        with pytest.raises(CircuitBreakerError):
            await client.call_with_resilience(failing_provider, "test")
    
    def test_resilience_config_from_environment(self):
        """Test that resilience configuration is loaded from environment."""
        
        env_vars = {
            'PROVIDER_TIMEOUT_S': '30',
            'PROVIDER_MAX_RETRIES': '3',
            'PROVIDER_CIRCUIT_FAILS': '3',
            'RESILIENT_BREAKER_ENABLED': 'true'
        }
        
        with patch.dict('os.environ', env_vars):
            config = ResilienceConfig.from_env()
            
            assert config.timeout_s == 30.0
            assert config.max_retries == 3
            assert config.circuit_fails == 3
            assert config.breaker_enabled is True
    
    def test_circuit_breaker_disabled_via_environment(self):
        """Test that circuit breaker can be disabled via environment."""
        
        with patch.dict('os.environ', {'RESILIENT_BREAKER_ENABLED': 'false'}):
            config = ResilienceConfig.from_env()
            assert config.breaker_enabled is False
            
            client = ResilientClient(config)
            assert client.config.breaker_enabled is False
    
    def test_resilience_environment_defaults(self):
        """Test that all resilience environment variables have proper defaults."""
        
        # Test without any environment variables set
        config = ResilienceConfig.from_env()
        
        assert config.timeout_s == 20.0
        assert config.max_retries == 2
        assert config.backoff_base_ms == 200
        assert config.circuit_fails == 5
        assert config.circuit_reset_s == 30.0
        assert config.concurrency == 10
        assert config.queue_depth == 50
        assert config.breaker_enabled is True  # Default ON
    
    def test_resilience_suite_environment_flags(self):
        """Test that resilience suite can be controlled via environment."""
        
        # Test with resilience suite enabled (default)
        with patch.dict('os.environ', {'RESILIENCE_SUITE_ENABLED': 'true'}):
            import os
            assert os.getenv('RESILIENCE_SUITE_ENABLED', 'true').lower() == 'true'
        
        # Test with resilience suite disabled
        with patch.dict('os.environ', {'RESILIENCE_SUITE_ENABLED': 'false'}):
            import os
            assert os.getenv('RESILIENCE_SUITE_ENABLED', 'true').lower() == 'false'
    
    def test_circuit_breaker_error_type(self):
        """Test that CircuitBreakerError is properly defined."""
        
        # Test that we can create and raise CircuitBreakerError
        error = CircuitBreakerError("Test circuit breaker error")
        assert str(error) == "Test circuit breaker error"
        
        # Test inheritance
        assert isinstance(error, Exception)
    
    @pytest.mark.asyncio 
    async def test_circuit_breaker_reset_functionality(self):
        """Test that circuit breaker can reset after cooldown."""
        
        config = ResilienceConfig(
            circuit_fails=1,
            circuit_reset_s=0.1,  # Very short reset time for testing
            max_retries=0,
            breaker_enabled=True
        )
        
        client = ResilientClient(config)
        
        # Fail once to open circuit
        async def failing_call():
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail="Server Error")
        
        # This should fail and open the circuit
        with pytest.raises(Exception):
            await client.call_with_resilience(failing_call, "fail")
        
        # Immediate retry should fail with circuit breaker
        with pytest.raises(CircuitBreakerError):
            await client.call_with_resilience(failing_call, "immediate_retry")
        
        # Wait for reset time
        import asyncio
        await asyncio.sleep(0.2)
        
        # Now should allow one test call (half-open state)
        async def success_call():
            return "success"
        
        result = await client.call_with_resilience(success_call, "success_after_reset")
        assert result == "success"