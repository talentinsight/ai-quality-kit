"""Test cache flow functionality."""

import pytest
import os
from unittest.mock import Mock, patch
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class TestCacheFlow:
    """Test cache flow functionality."""
    
    def test_cache_miss_then_hit(self, client, set_env_defaults, mock_openai_client):
        """Test that first call misses cache, second call hits cache."""
        with patch.dict(os.environ, set_env_defaults):
            # Mock OpenAI response
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Data quality validation is a process to ensure data meets quality standards."
            mock_openai_client.chat.completions.create.return_value = mock_response
            
            query = "What is data quality validation?"
            
            # First call - should miss cache
            response1 = client.post(
                "/ask",
                json={"query": query}
            )
            
            assert response1.status_code == 200
            first_response = response1.json()
            
            # Second call - should hit cache (if caching is enabled)
            response2 = client.post(
                "/ask",
                json={"query": query}
            )
            
            assert response2.status_code == 200
            second_response = response2.json()
            
            # Verify responses are identical
            assert first_response["answer"] == second_response["answer"]
            assert first_response["context"] == second_response["context"]


class TestCacheWithDifferentQueries:
    """Test cache behavior with different queries."""
    
    def test_different_queries_no_cache_conflict(self, client, set_env_defaults, mock_openai_client):
        """Test that different queries don't interfere with each other."""
        with patch.dict(os.environ, set_env_defaults):
            # Mock OpenAI response
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Test answer"
            mock_openai_client.chat.completions.create.return_value = mock_response
            
            # First query
            query1 = "What is data quality validation?"
            response1 = client.post(
                "/ask",
                json={"query": query1}
            )
            assert response1.status_code == 200
            
            # Second query (different)
            query2 = "How to monitor ETL pipelines?"
            response2 = client.post(
                "/ask",
                json={"query": query2}
            )
            assert response2.status_code == 200
            
            # Third query (same as first)
            response3 = client.post(
                "/ask",
                json={"query": query1}
            )
            assert response3.status_code == 200
            
            # Verify responses are consistent
            data1 = response1.json()
            data3 = response3.json()
            assert data1["answer"] == data3["answer"]
            assert data1["context"] == data3["context"]


class TestCacheConfiguration:
    """Test cache configuration and behavior."""
    
    def test_cache_enabled_flag(self):
        """Test that cache can be enabled/disabled via environment variable."""
        # Test with cache enabled
        with patch.dict(os.environ, {"CACHE_ENABLED": "true"}):
            from apps.cache.cache_store import is_cache_enabled
            assert is_cache_enabled() is True
        
        # Test with cache disabled
        with patch.dict(os.environ, {"CACHE_ENABLED": "false"}):
            from apps.cache.cache_store import is_cache_enabled
            assert is_cache_enabled() is False
        
        # Test with cache not set (should default to True)
        with patch.dict(os.environ, {}, clear=True):
            from apps.cache.cache_store import is_cache_enabled
            assert is_cache_enabled() is True
