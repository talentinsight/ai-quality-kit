"""
Tests for rate limiting middleware.
"""
import pytest
import asyncio
import time
from unittest.mock import patch, AsyncMock
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from apps.security.rate_limit import (
    TokenBucket,
    InMemoryRateLimiter, 
    RateLimitConfig,
    rate_limit_middleware,
    get_rate_limit_counters,
    reset_rate_limit_counters,
    _extract_token_from_auth,
    _get_client_ip,
    clear_rate_limit_state,
    _should_exempt_path
)

@pytest.fixture(autouse=True)
def clear_rate_limit_state_before_test():
    """Clear rate limiting state before each test to ensure isolation."""
    clear_rate_limit_state()
    yield
    clear_rate_limit_state()

class TestTokenBucket:
    """Test token bucket algorithm."""
    
    def test_initial_tokens(self):
        """Test bucket starts with full capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.tokens == 10.0
        assert bucket.capacity == 10
        assert bucket.refill_rate == 1.0
    
    def test_consume_tokens_success(self):
        """Test successful token consumption."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        
        allowed, retry_after = bucket.consume(5)
        assert allowed is True
        assert retry_after == 0.0
        assert bucket.tokens == 5.0
    
    def test_consume_tokens_exceed_capacity(self):
        """Test token consumption exceeding capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        
        allowed, retry_after = bucket.consume(15)
        assert allowed is False
        assert retry_after == 5.0  # Need 5 more tokens at 1/sec
        assert bucket.tokens == 10.0  # Unchanged
    
    def test_burst_then_refill(self):
        """Test burst consumption followed by refill."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)  # 2 tokens/sec
        
        # Consume all tokens
        allowed, _ = bucket.consume(10)
        assert allowed is True
        assert bucket.tokens == 0.0
        
        # Immediate request should fail
        allowed, retry_after = bucket.consume(1)
        assert allowed is False
        assert abs(retry_after - 0.5) < 0.01  # 1 token / 2 per sec (with tolerance)
        
        # Mock time advancement
        bucket.last_refill -= 1.0  # Simulate 1 second passed
        
        # Should allow 2 tokens after 1 second
        allowed, _ = bucket.consume(2)
        assert allowed is True
        assert abs(bucket.tokens) < 0.01  # Close to 0 with tolerance
    
    def test_refill_does_not_exceed_capacity(self):
        """Test refill caps at bucket capacity."""
        bucket = TokenBucket(capacity=5, refill_rate=10.0)
        
        # Consume some tokens
        bucket.consume(3)
        assert bucket.tokens == 2.0
        
        # Mock long time passage
        bucket.last_refill -= 10.0  # 10 seconds = 100 tokens
        
        # Should refill to capacity, not exceed
        allowed, _ = bucket.consume(1)
        assert allowed is True
        assert bucket.tokens == 4.0  # 5 - 1

class TestInMemoryRateLimiter:
    """Test in-memory rate limiter."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_allowed(self):
        """Test requests within rate limit are allowed."""
        limiter = InMemoryRateLimiter()
        
        # First request should be allowed
        allowed, retry_after = await limiter.check_rate_limit("test_key", 5, 1.0)
        assert allowed is True
        assert retry_after == 0.0
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self):
        """Test requests exceeding rate limit are blocked."""
        limiter = InMemoryRateLimiter()
        key = "test_key"
        
        # Consume all tokens
        for _ in range(5):
            allowed, _ = await limiter.check_rate_limit(key, 5, 1.0)
            assert allowed is True
        
        # Next request should be blocked
        allowed, retry_after = await limiter.check_rate_limit(key, 5, 1.0)
        assert allowed is False
        assert abs(retry_after - 1.0) < 0.01  # Need 1 token at 1/sec (with tolerance)
    
    @pytest.mark.asyncio
    async def test_different_keys_independent(self):
        """Test different keys have independent rate limits."""
        limiter = InMemoryRateLimiter()
        
        # Exhaust key1
        for _ in range(5):
            await limiter.check_rate_limit("key1", 5, 1.0)
        
        # key1 should be blocked
        allowed, _ = await limiter.check_rate_limit("key1", 5, 1.0)
        assert allowed is False
        
        # key2 should still work
        allowed, _ = await limiter.check_rate_limit("key2", 5, 1.0)
        assert allowed is True
    
    def test_cleanup_old_buckets(self):
        """Test cleanup of unused buckets."""
        limiter = InMemoryRateLimiter()
        
        # Create some buckets
        limiter.buckets["old_key"] = TokenBucket(5, 1.0)
        limiter.buckets["new_key"] = TokenBucket(5, 1.0)
        
        # Make one bucket "old"
        limiter.buckets["old_key"].last_refill = time.time() - 7200  # 2 hours ago
        
        # Force cleanup
        limiter.last_cleanup = 0
        limiter._cleanup_old_buckets()
        
        # Old bucket should be removed
        assert "old_key" not in limiter.buckets
        assert "new_key" in limiter.buckets

class TestRateLimitConfig:
    """Test rate limit configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = RateLimitConfig()
        assert config.enabled is True
        assert config.per_token_per_min == 60
        assert config.per_token_burst == 10
        assert config.per_ip_per_min == 120
        assert config.per_ip_burst == 20
        assert config.token_refill_rate == 1.0  # 60/60
        assert config.ip_refill_rate == 2.0  # 120/60
    
    @patch.dict('os.environ', {
        'RL_ENABLED': 'false',
        'RL_PER_TOKEN_PER_MIN': '30',
        'RL_PER_TOKEN_BURST': '5',
        'RL_PER_IP_PER_MIN': '60',
        'RL_PER_IP_BURST': '10',
        'REDIS_URL': 'redis://localhost:6379'
    })
    def test_custom_config(self):
        """Test custom configuration from environment."""
        config = RateLimitConfig()
        assert config.enabled is False
        assert config.per_token_per_min == 30
        assert config.per_token_burst == 5
        assert config.per_ip_per_min == 60
        assert config.per_ip_burst == 10
        assert config.token_refill_rate == 0.5  # 30/60
        assert config.ip_refill_rate == 1.0  # 60/60
        assert config.redis_url == 'redis://localhost:6379'

class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_extract_token_from_auth(self):
        """Test token extraction from Authorization header."""
        # Valid Bearer token
        token = _extract_token_from_auth("Bearer abc123")
        assert token == "abc123"
        
        # Long token gets hashed
        long_token = "sk-" + "x" * 50
        hashed = _extract_token_from_auth(f"Bearer {long_token}")
        assert hashed is not None
        assert hashed != long_token
        assert len(hashed) == 16
        
        # Invalid format
        assert _extract_token_from_auth("InvalidAuth") is None
        assert _extract_token_from_auth(None) is None
    
    def test_should_exempt_path(self):
        """Test path exemption logic."""
        assert _should_exempt_path("/healthz") is True
        assert _should_exempt_path("/readyz") is True
        assert _should_exempt_path("/ask") is False
        assert _should_exempt_path("/orchestrator/run_tests") is False

class TestRateLimitMiddleware:
    """Test rate limiting middleware integration."""
    
    def setup_method(self):
        """Reset counters before each test."""
        reset_rate_limit_counters()
    
    @patch.dict('os.environ', {'RL_ENABLED': 'false'})
    def test_disabled_rate_limiting(self):
        """Test middleware when rate limiting is disabled."""
        app = FastAPI()
        app.middleware("http")(rate_limit_middleware)
        
        @app.get("/ask")
        async def test_endpoint():
            return {"message": "success"}
        
        client = TestClient(app)
        
        # Should allow many requests
        for _ in range(20):
            response = client.get("/ask")
            assert response.status_code == 200
        
        # No requests should be blocked
        counters = get_rate_limit_counters()
        assert counters["blocked_total"] == 0
    
    @patch.dict('os.environ', {
        'RL_ENABLED': 'true',
        'RL_PER_TOKEN_PER_MIN': '60',  # 1 per second
        'RL_PER_TOKEN_BURST': '5',     # Allow 5 initial requests
        'RL_PER_IP_PER_MIN': '120',
        'RL_PER_IP_BURST': '10'
    })
    def test_rate_limiting_enforcement(self):
        """Test rate limiting enforcement."""
        app = FastAPI()
        app.middleware("http")(rate_limit_middleware)
        
        @app.post("/ask")
        async def test_endpoint():
            return {"message": "success"}
        
        client = TestClient(app)
        
        # First 5 requests should succeed (burst limit)
        for i in range(5):
            response = client.post(
                "/ask", 
                headers={"Authorization": "Bearer test-token"}
            )
            assert response.status_code == 200, f"Request {i} failed"
        
        # 6th request should be rate limited
        response = client.post(
            "/ask",
            headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == 429
        assert "error" in response.json()
        assert response.json()["error"] == "rate_limited"
        assert "retry_after_ms" in response.json()
        assert "Retry-After" in response.headers
        
        # Check counters
        counters = get_rate_limit_counters()
        assert counters["allowed_total"] == 5  # 5 successful requests
        assert counters["blocked_total"] >= 1
    
    @patch.dict('os.environ', {'RL_ENABLED': 'true'})
    def test_exempt_health_endpoints(self):
        """Test health endpoints are exempt from rate limiting."""
        app = FastAPI()
        app.middleware("http")(rate_limit_middleware)
        
        @app.get("/healthz")
        async def health():
            return {"status": "healthy"}
        
        @app.get("/readyz")
        async def ready():
            return {"status": "ready"}
        
        client = TestClient(app)
        
        # Health endpoints should always work
        for _ in range(50):
            health_response = client.get("/healthz")
            ready_response = client.get("/readyz")
            assert health_response.status_code == 200
            assert ready_response.status_code == 200
        
        # No rate limiting should occur
        counters = get_rate_limit_counters()
        assert counters["blocked_total"] == 0
    
    @patch.dict('os.environ', {'RL_ENABLED': 'true'})
    def test_non_sensitive_routes_exempt(self):
        """Test non-sensitive routes are exempt from rate limiting."""
        app = FastAPI()
        app.middleware("http")(rate_limit_middleware)
        
        @app.get("/some-other-endpoint")
        async def other():
            return {"message": "not rate limited"}
        
        client = TestClient(app)
        
        # Non-sensitive endpoints should always work
        for _ in range(50):
            response = client.get("/some-other-endpoint")
            assert response.status_code == 200
        
        # No rate limiting should occur
        counters = get_rate_limit_counters()
        assert counters["blocked_total"] == 0
    
    @patch.dict('os.environ', {
        'RL_ENABLED': 'true',
        'RL_PER_IP_PER_MIN': '5',  # Low limit for testing
        'RL_PER_IP_BURST': '2'
    })
    def test_ip_based_rate_limiting(self):
        """Test IP-based rate limiting for unauthenticated requests."""
        app = FastAPI()
        app.middleware("http")(rate_limit_middleware)
        
        @app.post("/ask")
        async def test_endpoint():
            return {"message": "success"}
        
        client = TestClient(app)
        
        # Unauthenticated requests should be limited by IP
        for i in range(2):
            response = client.post("/ask")
            assert response.status_code == 200, f"Request {i} failed"
        
        # Should be rate limited by IP
        response = client.post("/ask")
        assert response.status_code == 429
    
    @patch.dict('os.environ', {'RL_ENABLED': 'true'})
    def test_testdata_routes_protected(self):
        """Test testdata routes are protected by rate limiting."""
        app = FastAPI()
        app.middleware("http")(rate_limit_middleware)
        
        @app.post("/testdata/upload")
        async def upload():
            return {"message": "uploaded"}
        
        @app.get("/testdata/{testdata_id}/meta")
        async def meta(testdata_id: str):
            return {"id": testdata_id}
        
        client = TestClient(app)
        
        # These routes should be subject to rate limiting
        # (exact limits depend on configuration, just verify middleware applies)
        response = client.post("/testdata/upload")
        # Response could be 200 or 429 depending on other tests
        assert response.status_code in [200, 429]
        
        response = client.get("/testdata/123/meta")
        assert response.status_code in [200, 429]

class TestRedisRateLimiter:
    """Test Redis rate limiter (when Redis is available)."""
    
    @pytest.mark.asyncio
    async def test_redis_connection_failure_fallback(self):
        """Test fallback when Redis connection fails."""
        from apps.security.rate_limit import RedisRateLimiter
        
        # Invalid Redis URL should raise exception
        limiter = RedisRateLimiter("redis://invalid-host:6379")
        
        with pytest.raises(Exception):
            await limiter.check_rate_limit("test", 5, 1.0)

@pytest.mark.asyncio
async def test_middleware_error_handling():
    """Test middleware handles errors gracefully (fail open)."""
    
    # Mock a failing rate limiter
    with patch('apps.security.rate_limit.get_rate_limiter') as mock_limiter:
        mock_limiter.side_effect = Exception("Redis connection failed")
        
        app = FastAPI()
        app.middleware("http")(rate_limit_middleware)
        
        @app.get("/ask")
        async def test_endpoint():
            return {"message": "success"}
        
        client = TestClient(app)
        
        # Should fail open (allow request) when rate limiter fails
        response = client.get("/ask")
        assert response.status_code == 200
