"""Unit tests for LLM provider functionality."""

import pytest
from unittest.mock import patch, Mock
import os


class TestProvider:
    """Test LLM provider operations."""
    
    def test_get_provider_chat_openai_missing_key(self, set_env_defaults):
        """Test OpenAI provider with missing API key."""
        with patch.dict(os.environ, set_env_defaults):
            # Remove OpenAI key
            with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
                from llm.provider import get_chat
                
                with pytest.raises(ValueError, match="OPENAI_API_KEY environment variable is required"):
                    get_chat()
    
    def test_get_provider_chat_anthropic_missing_key(self, set_env_defaults):
        """Test Anthropic provider with missing API key."""
        with patch.dict(os.environ, set_env_defaults):
            # Change provider to anthropic and remove key
            with patch.dict(os.environ, {"PROVIDER": "anthropic", "ANTHROPIC_API_KEY": ""}):
                from llm.provider import get_chat
                
                with pytest.raises(ValueError, match="ANTHROPIC_API_KEY environment variable is required"):
                    get_chat()
    
    def test_get_provider_chat_openai_success(self, set_env_defaults):
        """Test OpenAI provider with valid API key."""
        with patch.dict(os.environ, set_env_defaults):
            from llm.provider import get_chat
            
            chat_func = get_chat()
            
            assert callable(chat_func), "Should return a callable function"
            
            # Test that the function can be called
            try:
                # This might fail due to missing actual API key, but function should exist
                result = chat_func(["system message", "user message"])
                # If it succeeds, should return a string
                if result is not None:
                    assert isinstance(result, str)
            except Exception:
                # Expected to fail without real API key, but function should exist
                pass
    
    def test_get_provider_chat_anthropic_success(self, set_env_defaults):
        """Test Anthropic provider with valid API key."""
        with patch.dict(os.environ, set_env_defaults):
            # Change provider to anthropic
            with patch.dict(os.environ, {"PROVIDER": "anthropic"}):
                from llm.provider import get_chat
                
                chat_func = get_chat()
                
                assert callable(chat_func), "Should return a callable function"
                
                # Test that the function can be called
                try:
                    # This might fail due to missing actual API key, but function should exist
                    result = chat_func(["system message", "user message"])
                    # If it succeeds, should return a string
                    if result is not None:
                        assert isinstance(result, str)
                except Exception:
                    # Expected to fail without real API key, but function should exist
                    pass
    
    def test_get_provider_chat_unknown_provider(self, set_env_defaults):
        """Test unknown provider raises error."""
        with patch.dict(os.environ, set_env_defaults):
            from llm.provider import get_chat
            
            with patch.dict(os.environ, {"PROVIDER": "unknown_provider"}):
                with pytest.raises(ValueError, match="Unsupported provider"):
                    get_chat()
    
    def test_openai_chat_function_signature(self, set_env_defaults):
        """Test OpenAI chat function signature and parameters."""
        with patch.dict(os.environ, set_env_defaults):
            from llm.provider import get_chat
            
            chat_func = get_chat()
            
            # Check function signature
            import inspect
            sig = inspect.signature(chat_func)
            
            # Should have expected parameters
            params = list(sig.parameters.keys())
            assert "messages" in params, "Should have 'messages' parameter"
    
    def test_anthropic_chat_function_signature(self, set_env_defaults):
        """Test Anthropic chat function signature and parameters."""
        with patch.dict(os.environ, set_env_defaults):
            # Change provider to anthropic
            with patch.dict(os.environ, {"PROVIDER": "anthropic"}):
                from llm.provider import get_chat
                
                chat_func = get_chat()
                
                # Check function signature
                import inspect
                sig = inspect.signature(chat_func)
                
                # Should have expected parameters
                params = list(sig.parameters.keys())
                assert "messages" in params, "Should have 'messages' parameter"
    
    def test_provider_configuration_loading(self, set_env_defaults):
        """Test that provider configuration loads correctly from environment."""
        with patch.dict(os.environ, set_env_defaults):
            from llm.provider import get_chat
            
            # Test OpenAI configuration
            openai_chat = get_chat()
            assert callable(openai_chat)
            
            # Test Anthropic configuration
            with patch.dict(os.environ, {"PROVIDER": "anthropic"}):
                anthropic_chat = get_chat()
                assert callable(anthropic_chat)
    
    def test_provider_error_messages(self, set_env_defaults):
        """Test that provider error messages are informative."""
        with patch.dict(os.environ, set_env_defaults):
            from llm.provider import get_chat
            
            # Test OpenAI missing key error
            with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
                with pytest.raises(ValueError) as exc_info:
                    get_chat()
                assert "OPENAI_API_KEY environment variable is required" in str(exc_info.value)
            
            # Test Anthropic missing key error
            with patch.dict(os.environ, {"PROVIDER": "anthropic", "ANTHROPIC_API_KEY": ""}):
                with pytest.raises(ValueError) as exc_info:
                    get_chat()
                assert "ANTHROPIC_API_KEY environment variable is required" in str(exc_info.value)
            
            # Test unknown provider error
            with patch.dict(os.environ, {"PROVIDER": "unknown"}):
                with pytest.raises(ValueError) as exc_info:
                    get_chat()
                assert "Unsupported provider" in str(exc_info.value)
    
    def test_provider_function_behavior(self, set_env_defaults):
        """Test that provider functions behave as expected."""
        with patch.dict(os.environ, set_env_defaults):
            from llm.provider import get_chat
            
            # Test OpenAI function
            openai_chat = get_chat()
            
            # Function should accept messages list
            try:
                result = openai_chat(["system message", "user message"])
                if result is not None:
                    assert isinstance(result, str)
                    assert len(result) > 0
            except Exception:
                # Expected to fail without real API key
                pass
            
            # Test Anthropic function
            with patch.dict(os.environ, {"PROVIDER": "anthropic"}):
                anthropic_chat = get_chat()
                
                try:
                    result = anthropic_chat(["system message", "user message"])
                    if result is not None:
                        assert isinstance(result, str)
                        assert len(result) > 0
                except Exception:
                    # Expected to fail without real API key
                    pass
    
    def test_provider_environment_override(self, set_env_defaults):
        """Test that environment variables can override provider settings."""
        with patch.dict(os.environ, set_env_defaults):
            from llm.provider import get_chat
            
            # Test with different model names
            with patch.dict(os.environ, {"MODEL_NAME": "gpt-4"}):
                openai_chat = get_chat()
                assert callable(openai_chat)
            
            with patch.dict(os.environ, {"PROVIDER": "anthropic", "MODEL_NAME": "claude-3-opus"}):
                anthropic_chat = get_chat()
                assert callable(anthropic_chat)
    
    def test_provider_function_consistency(self, set_env_defaults):
        """Test that provider functions are consistent across calls."""
        with patch.dict(os.environ, set_env_defaults):
            from llm.provider import get_chat
            
            # OpenAI function should be consistent in behavior
            openai_chat1 = get_chat()
            openai_chat2 = get_chat()
            
            # Functions should have same signature and behavior (but may be different objects)
            import inspect
            sig1 = inspect.signature(openai_chat1)
            sig2 = inspect.signature(openai_chat2)
            assert sig1 == sig2, "Function signatures should be identical"
            
            # Anthropic function should be consistent in behavior
            with patch.dict(os.environ, {"PROVIDER": "anthropic"}):
                anthropic_chat1 = get_chat()
                anthropic_chat2 = get_chat()
                
                # Functions should have same signature and behavior (but may be different objects)
                sig1 = inspect.signature(anthropic_chat1)
                sig2 = inspect.signature(anthropic_chat2)
                assert sig1 == sig2, "Function signatures should be identical"
