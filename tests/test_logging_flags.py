"""Test logging flags functionality."""

import pytest
import os
from unittest.mock import Mock, patch
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class TestLoggingFlags:
    """Test logging flags functionality."""
    
    def test_default_flags_disabled(self, client, set_env_defaults, mock_openai_client):
        """Test that API responds normally with default flags (disabled)."""
        with patch.dict(os.environ, set_env_defaults):
            # Mock OpenAI response
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Data quality is important for reliable analytics."
            mock_openai_client.chat.completions.create.return_value = mock_response
            
            response = client.post(
                "/ask",
                json={"query": "What is data quality?"}
            )
            
            # Should get a successful response
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert "context" in data
    
    @pytest.mark.snowflake
    def test_api_logging_without_snowflake_env(self, client, set_env_defaults, mock_openai_client):
        """Test graceful degradation when API logging enabled but Snowflake env missing."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_openai_client.chat.completions.create.return_value = mock_response
        
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
                # Should not crash - use our mocked client
                response = client.post(
                    "/ask",
                    json={"query": "Test query"}
                )
                
                # Should get a successful response
                assert response.status_code == 200
                
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
    
    def test_live_eval_without_provider_keys(self, client, set_env_defaults):
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
                # Should not crash - use our mocked client
                response = client.post(
                    "/ask",
                    json={"query": "Test query"}
                )
                
                # Should get a successful response
                assert response.status_code == 200
                
            finally:
                # Restore provider keys
                if openai_key:
                    os.environ["OPENAI_API_KEY"] = openai_key
                if anthropic_key:
                    os.environ["ANTHROPIC_API_KEY"] = anthropic_key
                        
        finally:
            # Restore original flag
            if original_flag is not None:
                os.environ["ENABLE_LIVE_EVAL"] = original_flag
            elif "ENABLE_LIVE_EVAL" in os.environ:
                del os.environ["ENABLE_LIVE_EVAL"]
    
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
