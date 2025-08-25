"""
Rate limiting middleware with token bucket algorithm.
Supports Redis (preferred) and in-memory fallback storage.
"""
import os
import time
import json
import asyncio
from typing import Dict, Optional, Tuple, Union
from collections import defaultdict
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# Observability counters
_rate_limit_counters = {
    "allowed_total": 0,
    "blocked_total": 0
}

def get_rate_limit_counters() -> Dict[str, int]:
    """Get rate limit observability counters."""
    return _rate_limit_counters.copy()

def reset_rate_limit_counters():
    """Reset rate limit counters (for testing)."""
    global _rate_limit_counters
    _rate_limit_counters = {"allowed_total": 0, "blocked_total": 0}

class TokenBucket:
    """Token bucket for rate limiting with burst and refill."""
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.
        
        Args:
            capacity: Maximum tokens (burst limit)
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()
    
    def consume(self, tokens: int = 1) -> Tuple[bool, float]:
        """
        Try to consume tokens from bucket.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            (allowed, retry_after_seconds)
        """
        now = time.time()
        
        # Refill tokens based on elapsed time
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, 0.0
        else:
            # Calculate when enough tokens will be available
            needed_tokens = tokens - self.tokens
            retry_after = needed_tokens / self.refill_rate
            return False, retry_after

class InMemoryRateLimiter:
    """In-memory rate limiter using token buckets."""
    
    def __init__(self):
        self.buckets: Dict[str, TokenBucket] = {}
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
    
    def _cleanup_old_buckets(self):
        """Remove unused buckets to prevent memory leaks."""
        now = time.time()
        if now - self.last_cleanup < self.cleanup_interval:
            return
            
        # Remove buckets unused for more than 1 hour
        cutoff = now - 3600
        keys_to_remove = [
            key for key, bucket in self.buckets.items()
            if bucket.last_refill < cutoff
        ]
        
        for key in keys_to_remove:
            del self.buckets[key]
        
        self.last_cleanup = now
        
        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} unused rate limit buckets")
    
    def clear_all_buckets(self):
        """Clear all rate limit buckets. Used for testing."""
        self.buckets.clear()
    
    async def check_rate_limit(self, key: str, capacity: int, refill_rate: float) -> Tuple[bool, float]:
        """
        Check if request is within rate limit.
        
        Args:
            key: Unique identifier for the rate limit bucket
            capacity: Maximum burst capacity
            refill_rate: Tokens per second refill rate
            
        Returns:
            (allowed, retry_after_seconds)
        """
        self._cleanup_old_buckets()
        
        if key not in self.buckets:
            self.buckets[key] = TokenBucket(capacity, refill_rate)
        
        return self.buckets[key].consume(1)

class RedisRateLimiter:
    """Redis-based rate limiter using token bucket algorithm."""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis = None
    
    async def _get_redis(self):
        """Get Redis connection (lazy initialization)."""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                # Test connection
                await self._redis.ping()
                logger.info("Connected to Redis for rate limiting")
            except ImportError:
                logger.error("Redis library not installed. Install with: pip install redis")
                raise
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
        return self._redis
    
    async def check_rate_limit(self, key: str, capacity: int, refill_rate: float) -> Tuple[bool, float]:
        """
        Check if request is within rate limit using Redis.
        
        Args:
            key: Unique identifier for the rate limit bucket
            capacity: Maximum burst capacity  
            refill_rate: Tokens per second refill rate
            
        Returns:
            (allowed, retry_after_seconds)
        """
        redis = await self._get_redis()
        
        # Use Lua script for atomic token bucket operation
        lua_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local tokens_to_consume = tonumber(ARGV[4])
        
        -- Get current bucket state
        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket[1]) or capacity
        local last_refill = tonumber(bucket[2]) or now
        
        -- Refill tokens based on elapsed time
        local elapsed = now - last_refill
        tokens = math.min(capacity, tokens + elapsed * refill_rate)
        
        local allowed = 0
        local retry_after = 0
        
        if tokens >= tokens_to_consume then
            -- Allow request
            tokens = tokens - tokens_to_consume
            allowed = 1
        else
            -- Deny request, calculate retry after
            local needed_tokens = tokens_to_consume - tokens
            retry_after = needed_tokens / refill_rate
        end
        
        -- Update bucket state
        redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, 3600)  -- Expire after 1 hour
        
        return {allowed, retry_after}
        """
        
        now = time.time()
        result = await redis.eval(lua_script, 1, key, capacity, refill_rate, now, 1)
        
        allowed = bool(result[0])
        retry_after = float(result[1])
        
        return allowed, retry_after

class RateLimitConfig:
    """Rate limiting configuration from environment variables."""
    
    def __init__(self):
        self.enabled = os.getenv("RL_ENABLED", "true").lower() == "true"
        self.per_token_per_min = int(os.getenv("RL_PER_TOKEN_PER_MIN", "60"))
        self.per_token_burst = int(os.getenv("RL_PER_TOKEN_BURST", "10"))
        self.per_ip_per_min = int(os.getenv("RL_PER_IP_PER_MIN", "120"))
        self.per_ip_burst = int(os.getenv("RL_PER_IP_BURST", "20"))
        self.redis_url = os.getenv("REDIS_URL")
        
        # Convert per-minute to per-second rates
        self.token_refill_rate = self.per_token_per_min / 60.0
        self.ip_refill_rate = self.per_ip_per_min / 60.0

# Global rate limiter instance
_rate_limiter: Optional[Union[RedisRateLimiter, InMemoryRateLimiter]] = None
_config: Optional[RateLimitConfig] = None

async def get_rate_limiter() -> Union[RedisRateLimiter, InMemoryRateLimiter]:
    """Get rate limiter instance (lazy initialization)."""
    global _rate_limiter, _config
    
    if _config is None:
        _config = RateLimitConfig()
    
    if _rate_limiter is None:
        if _config.redis_url:
            try:
                _rate_limiter = RedisRateLimiter(_config.redis_url)
                logger.info("Using Redis rate limiter")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis rate limiter, falling back to in-memory: {e}")
                _rate_limiter = InMemoryRateLimiter()
        else:
            _rate_limiter = InMemoryRateLimiter()
            logger.info("Using in-memory rate limiter")
    
    return _rate_limiter

def clear_rate_limit_state():
    """Clear all rate limiting state. Used for testing."""
    global _rate_limiter, _config, _rate_limit_counters
    
    if _rate_limiter and hasattr(_rate_limiter, 'clear_all_buckets'):
        _rate_limiter.clear_all_buckets()
    
    # Reset counters
    _rate_limit_counters["allowed_total"] = 0
    _rate_limit_counters["blocked_total"] = 0
    
    # Force reconfiguration on next middleware call
    _config = None
    _rate_limiter = None

def _extract_token_from_auth(authorization: Optional[str]) -> Optional[str]:
    """Extract token from Authorization header."""
    if not authorization:
        return None
    
    if authorization.startswith("Bearer "):
        token = authorization[7:]
        # Hash long tokens for privacy, keep short tokens for dev mode
        if len(token) > 32:
            import hashlib
            return hashlib.sha256(token.encode()).hexdigest()[:16]
        return token
    
    return None

def _get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    # Check X-Forwarded-For header first (for proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()
    
    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fall back to direct connection IP
    if hasattr(request, "client") and request.client:
        return request.client.host
    
    return "unknown"

def _should_exempt_path(path: str) -> bool:
    """Check if path should be exempt from rate limiting."""
    exempt_paths = ["/healthz", "/readyz"]
    return path in exempt_paths

async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware for FastAPI.
    
    Applies rate limits to sensitive endpoints based on token and IP.
    """
    global _config, _rate_limit_counters
    
    if _config is None:
        _config = RateLimitConfig()
    
    # Skip if rate limiting is disabled
    if not _config.enabled:
        return await call_next(request)
    
    # Skip exempt paths
    if _should_exempt_path(request.url.path):
        return await call_next(request)
    
    # Only apply to sensitive routes
    sensitive_routes = ["/ask", "/orchestrator/run_tests"]
    is_testdata_route = request.url.path.startswith("/testdata/")
    
    if not any(request.url.path.startswith(route) for route in sensitive_routes) and not is_testdata_route:
        return await call_next(request)
    
    try:
        rate_limiter = await get_rate_limiter()
        
        # Extract identifiers
        token = _extract_token_from_auth(request.headers.get("Authorization"))
        client_ip = _get_client_ip(request)
        
        # Check token-based rate limit
        if token:
            token_key = f"rl:tok:{token}:{request.url.path}"
            token_allowed, token_retry_after = await rate_limiter.check_rate_limit(
                token_key, _config.per_token_burst, _config.token_refill_rate
            )
            
            if not token_allowed:
                _rate_limit_counters["blocked_total"] += 1
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limited",
                        "retry_after_ms": int(token_retry_after * 1000)
                    },
                    headers={
                        "Retry-After": str(int(token_retry_after) + 1),
                        "X-RateLimit-Remaining": "0"
                    }
                )
        
        # Check IP-based rate limit
        ip_key = f"rl:ip:{client_ip}:{request.url.path}"
        ip_allowed, ip_retry_after = await rate_limiter.check_rate_limit(
            ip_key, _config.per_ip_burst, _config.ip_refill_rate
        )
        
        if not ip_allowed:
            _rate_limit_counters["blocked_total"] += 1
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited", 
                    "retry_after_ms": int(ip_retry_after * 1000)
                },
                headers={
                    "Retry-After": str(int(ip_retry_after) + 1),
                    "X-RateLimit-Remaining": "0"
                }
            )
        
        # Request allowed
        _rate_limit_counters["allowed_total"] += 1
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        if hasattr(response, "headers"):
            response.headers["X-RateLimit-Remaining"] = str(_config.per_token_burst - 1)
        
        return response
        
    except Exception as e:
        logger.error(f"Rate limiting error: {e}")
        # Fail open - allow request if rate limiting fails
        return await call_next(request)
