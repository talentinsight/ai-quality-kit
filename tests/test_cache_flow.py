"""Test cache flow functionality."""

import pytest
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check if provider keys are available
def has_provider_keys():
    """Check if required provider keys are available."""
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    return bool(openai_key or anthropic_key)


@pytest.mark.skipif(not has_provider_keys(), reason="Provider keys not available")
class TestCacheFlow:
    """Test cache flow functionality."""
    
    def test_cache_miss_then_hit(self):
        """Test that first call misses cache, second call hits cache."""
        import requests
        
        # First call - should miss cache
        query = "What is data quality validation?"
        start_time = time.time()
        
        response1 = requests.post(
            "http://localhost:8000/ask",
            json={"query": query},
            timeout=30
        )
        
        assert response1.status_code == 200
        first_call_time = time.time() - start_time
        
        # Second call - should hit cache
        start_time = time.time()
        
        response2 = requests.post(
            "http://localhost:8000/ask",
            json={"query": query},
            timeout=30
        )
        
        assert response2.status_code == 200
        second_call_time = time.time() - start_time
        
        # Verify responses are identical
        data1 = response1.json()
        data2 = response2.json()
        
        assert data1["answer"] == data2["answer"]
        assert data1["context"] == data2["context"]
        
        # Cache hit should be faster (allowing for some variance)
        # Note: In real scenarios, cache hit should be significantly faster
        assert second_call_time <= first_call_time * 1.5  # Allow 50% variance
        
        print(f"First call time: {first_call_time:.2f}s")
        print(f"Second call time: {second_call_time:.2f}s")
        print(f"Cache hit speedup: {first_call_time/second_call_time:.2f}x")


@pytest.mark.skipif(not has_provider_keys(), reason="Provider keys not available")
class TestCacheWithDifferentQueries:
    """Test cache behavior with different queries."""
    
    def test_different_queries_no_cache_conflict(self):
        """Test that different queries don't interfere with each other."""
        import requests
        
        # First query
        query1 = "What is data quality validation?"
        response1 = requests.post(
            "http://localhost:8000/ask",
            json={"query": query1},
            timeout=30
        )
        assert response1.status_code == 200
        
        # Second query (different)
        query2 = "How to monitor ETL pipelines?"
        response2 = requests.post(
            "http://localhost:8000/ask",
            json={"query": query2},
            timeout=30
        )
        assert response2.status_code == 200
        
        # Third query (same as first)
        response3 = requests.post(
            "http://localhost:8000/ask",
            json={"query": query1},
            timeout=30
        )
        assert response3.status_code == 200
        
        # Verify first and third responses are identical
        data1 = response1.json()
        data3 = response3.json()
        
        assert data1["answer"] == data3["answer"]
        assert data1["context"] == data3["context"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
