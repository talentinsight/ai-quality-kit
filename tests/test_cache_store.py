"""Unit tests for cache store functionality."""

import pytest
from unittest.mock import patch, Mock
from datetime import datetime, timedelta
import time
import os


@pytest.mark.snowflake  
class TestCacheStore:
    """Test cache store operations."""
    
    def test_is_cache_enabled(self, set_env_defaults):
        """Test cache enabled flag."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.cache.cache_store import is_cache_enabled
            
            # Default should be False
            assert is_cache_enabled() is False
            
            # Test with cache enabled
            with patch.dict(os.environ, {"CACHE_ENABLED": "true"}):
                assert is_cache_enabled() is True
    
    def test_get_cache_ttl(self, set_env_defaults):
        """Test cache TTL retrieval."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.cache.cache_store import get_cache_ttl
            
            # Default TTL should be reasonable
            ttl = get_cache_ttl()
            assert isinstance(ttl, int)
            assert ttl > 0
    
    def test_get_context_version(self, set_env_defaults):
        """Test context version generation."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.cache.cache_store import get_context_version
            
            version = get_context_version()
            assert isinstance(version, str)
            assert len(version) > 0
    
    def test_get_cached_hit(self, fake_snowflake_cursor, set_env_defaults):
        """Test cache hit scenario."""
        # Enable cache for this test
        env_with_cache = {**set_env_defaults, "CACHE_ENABLED": "true"}
        
        with patch.dict(os.environ, env_with_cache):
            from apps.cache.cache_store import get_cached
    
            # Mock cursor to return a fresh cache entry
            future_time = datetime.now() + timedelta(hours=1)
            fake_snowflake_cursor.fetchone.return_value = (
                "cached answer",
                ["context1", "context2"],
                datetime.now(),
                future_time
            )
    
            result = get_cached("test_hash", "test_version")
    
            assert result is not None
            assert result["answer"] == "cached answer"
            assert result["context"] == ["context1", "context2"]
            assert result["source"] == "cache"
    
    def test_get_cached_miss_expired(self, fake_snowflake_cursor, set_env_defaults):
        """Test cache miss due to expiration."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.cache.cache_store import get_cached
            
            # Mock cursor to return an expired cache entry
            past_time = datetime.now() - timedelta(hours=1)
            fake_snowflake_cursor.fetchone.return_value = (
                "expired answer",
                ["old_context"],
                datetime.now(),
                past_time
            )
            
            result = get_cached("test_hash", "test_version")
            
            assert result is None
    
    def test_get_cached_miss_no_result(self, fake_snowflake_cursor, set_env_defaults):
        """Test cache miss when no result found."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.cache.cache_store import get_cached
            
            # Mock cursor to return no result
            fake_snowflake_cursor.fetchone.return_value = None
            
            result = get_cached("test_hash", "test_version")
            
            assert result is None
    
    def test_set_cache_insert(self, fake_snowflake_cursor, set_env_defaults):
        """Test cache insertion."""
        # Enable cache for this test
        env_with_cache = {**set_env_defaults, "CACHE_ENABLED": "true"}
        
        with patch.dict(os.environ, env_with_cache):
            from apps.cache.cache_store import set_cache
            
            # Mock cursor to simulate successful insert
            fake_snowflake_cursor.rowcount = 1
            
            set_cache("test_hash", "test_version", "test_answer", ["context1"], 3600)
            
            # Verify execute was called
            fake_snowflake_cursor.execute.assert_called()
    
    def test_set_cache_update(self, fake_snowflake_cursor, set_env_defaults):
        """Test cache update when entry exists."""
        # Enable cache for this test
        env_with_cache = {**set_env_defaults, "CACHE_ENABLED": "true"}
        
        with patch.dict(os.environ, env_with_cache):
            from apps.cache.cache_store import set_cache
            
            # Mock cursor to simulate successful update
            fake_snowflake_cursor.rowcount = 1
            
            set_cache("test_hash", "test_version", "updated_answer", ["new_context"], 3600)
            
            # Verify execute was called
            fake_snowflake_cursor.execute.assert_called()
    
    def test_clear_expired_cache(self, fake_snowflake_cursor, set_env_defaults):
        """Test clearing expired cache entries."""
        # Enable cache for this test
        env_with_cache = {**set_env_defaults, "CACHE_ENABLED": "true"}
        
        with patch.dict(os.environ, env_with_cache):
            from apps.cache.cache_store import clear_expired_cache
            
            clear_expired_cache()
            
            # Verify execute was called
            fake_snowflake_cursor.execute.assert_called()
    
    def test_cache_context_parsing(self, fake_snowflake_cursor, set_env_defaults):
        """Test parsing of context from cache."""
        # Enable cache for this test
        env_with_cache = {**set_env_defaults, "CACHE_ENABLED": "true"}
        
        with patch.dict(os.environ, env_with_cache):
            from apps.cache.cache_store import get_cached
            
            # Mock cursor to return context as string (Snowflake format)
            future_time = datetime.now() + timedelta(hours=1)
            fake_snowflake_cursor.fetchone.return_value = (
                "cached answer",
                '["context1", "context2"]',  # String format
                datetime.now(),
                future_time
            )
            
            result = get_cached("test_hash", "test_version")
            
            assert result is not None
            assert isinstance(result["context"], list)
            assert result["context"] == ["context1", "context2"]
    
    def test_cache_error_handling(self, fake_snowflake_cursor, set_env_defaults):
        """Test error handling in cache operations."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.cache.cache_store import get_cached
            
            # Mock cursor to raise exception
            fake_snowflake_cursor.execute.side_effect = Exception("Database error")
            
            # Should handle errors gracefully
            result = get_cached("test_hash", "test_version")
            
            # Should return None on error
            assert result is None
    
    def test_cache_ttl_calculation(self, fake_snowflake_cursor, set_env_defaults):
        """Test TTL calculation for cache entries."""
        # Enable cache for this test
        env_with_cache = {**set_env_defaults, "CACHE_ENABLED": "true"}
        
        with patch.dict(os.environ, env_with_cache):
            from apps.cache.cache_store import set_cache
            
            # Mock cursor
            fake_snowflake_cursor.rowcount = 1
            
            # Set cache with 1 hour TTL
            ttl_seconds = 3600
            set_cache("test_hash", "test_version", "test_answer", ["context"], ttl_seconds)
            
            # Verify execute was called with proper TTL
            fake_snowflake_cursor.execute.assert_called()
            
            # The SQL should contain the TTL calculation
            call_args = fake_snowflake_cursor.execute.call_args
            sql = call_args[0][0] if call_args[0] else ""
            assert "EXPIRES_AT" in sql
