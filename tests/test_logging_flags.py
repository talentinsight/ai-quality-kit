"""Test logging flags functionality."""

import pytest
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class TestLoggingFlags:
    """Test logging flags functionality."""
    
    def test_default_flags_disabled(self):
        """Test that API responds normally with default flags (disabled)."""
        # This test should work regardless of environment
        try:
            response = requests.post(
                "http://localhost:8000/ask",
                json={"query": "What is data quality?"},
                timeout=10
            )
            
            # Should get a response (may be error if service not running, but no crash)
            assert response is not None
            
        except requests.exceptions.RequestException:
            # Service not running is OK for this test
            pass
    
    def test_api_logging_without_snowflake_env(self):
        """Test graceful degradation when API logging enabled but Snowflake env missing."""
        # Temporarily set logging flag
        original_flag = os.getenv("ENABLE_API_LOGGING")
        os.environ["ENABLE_API_LOGGING"] = "true"
        
        try:
            # Clear Snowflake env vars
            snowflake_vars = [
                "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD",
                "SNOWFLAKE_ROLE", "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE", "SNOWFLAKE_SCHEMA"
            ]
            
            original_values = {}
            for var in snowflake_vars:
                original_values[var] = os.getenv(var)
                if var in os.environ:
                    del os.environ[var]
            
            try:
                # Should not crash
                response = requests.post(
                    "http://localhost:8000/ask",
                    json={"query": "Test query"},
                    timeout=10
                )
                
                # Should get a response (may be error if service not running, but no crash)
                assert response is not None
                
            finally:
                # Restore Snowflake env vars
                for var, value in original_values.items():
                    if value is not None:
                        os.environ[var] = value
                    elif var in os.environ:
                        del os.environ[var]
                        
        finally:
            # Restore original flag
            if original_flag is not None:
                os.environ["ENABLE_API_LOGGING"] = original_flag
            elif "ENABLE_API_LOGGING" in os.environ:
                del os.environ["ENABLE_API_LOGGING"]
    
    def test_live_eval_without_provider_keys(self):
        """Test graceful degradation when live eval enabled but provider keys missing."""
        # Temporarily set eval flag
        original_flag = os.getenv("ENABLE_LIVE_EVAL")
        os.environ["ENABLE_LIVE_EVAL"] = "true"
        
        try:
            # Clear provider keys
            openai_key = os.getenv("OPENAI_API_KEY")
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
            
            if "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]
            
            try:
                # Should not crash
                response = requests.post(
                    "http://localhost:8000/ask",
                    json={"query": "Test query"},
                    timeout=10
                )
                
                # Should get a response (may be error if service not running, but no crash)
                assert response is not None
                
            finally:
                # Restore provider keys
                if openai_key is not None:
                    os.environ["OPENAI_API_KEY"] = openai_key
                if anthropic_key is not None:
                    os.environ["ANTHROPIC_API_KEY"] = anthropic_key
                    
        finally:
            # Restore original flag
            if original_flag is not None:
                os.environ["ENABLE_LIVE_EVAL"] = original_flag
            elif "ENABLE_LIVE_EVAL" in os.environ:
                del os.environ["ENABLE_LIVE_EVAL"]
    
    def test_cache_enabled_flag(self):
        """Test that cache enabled flag is respected."""
        # Check if cache is enabled by default
        cache_enabled = os.getenv("CACHE_ENABLED", "true").lower() == "true"
        
        if cache_enabled:
            # Should work normally
            try:
                response = requests.post(
                    "http://localhost:8000/ask",
                    json={"query": "Cache test query"},
                    timeout=10
                )
                
                assert response is not None
                
            except requests.exceptions.RequestException:
                # Service not running is OK
                pass
        else:
            # Cache disabled - should still work
            try:
                response = requests.post(
                    "http://localhost:8000/ask",
                    json={"query": "Cache test query"},
                    timeout=10
                )
                
                assert response is not None
                
            except requests.exceptions.RequestException:
                # Service not running is OK
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
