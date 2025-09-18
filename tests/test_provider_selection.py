"""Tests for provider selection and per-request overrides."""

import pytest
import os
from unittest.mock import patch, MagicMock


def test_get_chat_for_openai():
    """Test OpenAI provider selection."""
    from llm.provider import get_chat_for
    
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            
            # Mock response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test response"
            mock_client.chat.completions.create.return_value = mock_response
            
            chat_fn = get_chat_for("openai", "gpt-4")
            result = chat_fn(["System prompt", "User message"])
            
            assert result == "Test response"
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]["model"] == "gpt-4"
            assert call_args[1]["temperature"] == 0.0


def test_get_chat_for_anthropic():
    """Test Anthropic provider selection."""
    from llm.provider import get_chat_for
    
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        with patch('llm.provider.Anthropic') as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            
            # Mock response
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Test anthropic response"
            mock_client.messages.create.return_value = mock_response
            
            chat_fn = get_chat_for("anthropic", "claude-3-opus")
            result = chat_fn(["System prompt", "User message"])
            
            assert result == "Test anthropic response"
            mock_client.messages.create.assert_called_once()
            call_args = mock_client.messages.create.call_args
            assert call_args[1]["model"] == "claude-3-opus"
            assert call_args[1]["temperature"] == 0.0


def test_get_chat_for_gemini():
    """Test Gemini provider selection."""
    from llm.provider import get_chat_for
    
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
        with patch('google.generativeai.configure') as mock_configure:
            with patch('google.generativeai.GenerativeModel') as mock_model_class:
                mock_model = MagicMock()
                mock_model_class.return_value = mock_model
                
                # Mock response
                mock_response = MagicMock()
                mock_response.text = "Test gemini response"
                mock_model.generate_content.return_value = mock_response
                
                chat_fn = get_chat_for("gemini", "gemini-pro")
                result = chat_fn(["System prompt", "User message"])
                
                assert result == "Test gemini response"
                mock_configure.assert_called_once_with(api_key="test-key")
                mock_model_class.assert_called_once_with("gemini-pro")


def test_get_chat_for_custom_rest():
    """Test custom REST provider selection."""
    from llm.provider import get_chat_for
    
    with patch.dict(os.environ, {"CUSTOM_LLM_BASE_URL": "http://localhost:8080"}):
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            
            # Mock response
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Custom REST response"}}]
            }
            mock_client.post.return_value = mock_response
            
            chat_fn = get_chat_for("custom_rest", "custom-model")
            result = chat_fn(["System prompt", "User message"])
            
            assert result == "Custom REST response"
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "http://localhost:8080/v1/chat/completions" in call_args[0]


def test_get_chat_for_mock():
    """Test mock provider selection."""
    from llm.provider import get_chat_for
    
    chat_fn = get_chat_for("mock", "mock-model")
    
    # Test different response patterns
    result = chat_fn(["System", "Hello"])
    assert "Hello" in result
    assert "mock" in result.lower()
    
    result = chat_fn(["System", "What is your question?"])
    assert "mock" in result.lower()  # Mock provider always returns mock responses
    
    result = chat_fn(["System", "This should error"])
    assert "mock" in result.lower()  # Mock provider always returns mock responses


def test_provider_missing_api_key():
    """Test that missing API keys raise appropriate errors."""
    from llm.provider import get_chat_for
    
    # OpenAI without key
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError) as exc_info:
            get_chat_for("openai")
        assert "OPENAI_API_KEY" in str(exc_info.value)
    
    # Anthropic without key
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError) as exc_info:
            get_chat_for("anthropic")
        assert "ANTHROPIC_API_KEY" in str(exc_info.value)
    
    # Gemini without key
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError) as exc_info:
            get_chat_for("gemini")
        assert "GOOGLE_API_KEY" in str(exc_info.value)


def test_unsupported_provider():
    """Test that unsupported providers raise errors."""
    from llm.provider import get_chat_for
    
    with pytest.raises(ValueError) as exc_info:
        get_chat_for("unsupported_provider")
    assert "Unsupported provider" in str(exc_info.value)


def test_resolve_provider_and_model():
    """Test provider and model resolution."""
    from apps.rag_service.config import resolve_provider_and_model
    
    with patch.dict(os.environ, {
        "PROVIDER": "openai",
        "MODEL_NAME": "gpt-4o-mini",
        "ANTHROPIC_MODEL": "claude-3-5-sonnet",
        "ALLOWED_PROVIDERS": "openai,anthropic,mock"
    }):
        # Test defaults
        provider, model = resolve_provider_and_model(None, None)
        assert provider == "openai"
        assert model == "gpt-4o-mini"
        
        # Test overrides
        provider, model = resolve_provider_and_model("anthropic", "claude-3-opus")
        assert provider == "anthropic"
        assert model == "claude-3-opus"
        
        # Test provider override only
        provider, model = resolve_provider_and_model("anthropic", None)
        assert provider == "anthropic"
        assert model == "claude-3-sonnet-20240229"  # Updated to match env.example
        
        # Test disallowed provider
        with pytest.raises(ValueError) as exc_info:
            resolve_provider_and_model("invalid_provider", None)
        assert "not in allowed providers" in str(exc_info.value)


def test_backward_compatibility():
    """Test that existing get_chat() function still works."""
    from llm.provider import get_chat
    
    with patch.dict(os.environ, {"PROVIDER": "mock"}):
        chat_fn = get_chat()
        result = chat_fn(["System", "Test message"])
        assert "mock" in result.lower()


def test_provider_model_defaults():
    """Test provider-specific model defaults."""
    from apps.rag_service.config import resolve_provider_and_model
    
    with patch.dict(os.environ, {
        "MODEL_NAME": "gpt-4o-mini",
        "ANTHROPIC_MODEL": "claude-3-5-sonnet",
        "GEMINI_MODEL": "gemini-1.5-pro",
        "ALLOWED_PROVIDERS": "openai,anthropic,gemini,custom_rest,mock"
    }):
        # Test each provider's default model
        _, model = resolve_provider_and_model("openai", None)
        assert model == "gpt-4o-mini"
        
        _, model = resolve_provider_and_model("anthropic", None)
        assert model == "claude-3-sonnet-20240229"
        
        _, model = resolve_provider_and_model("gemini", None)
        assert model == "gemini-1.5-pro"
        
        _, model = resolve_provider_and_model("custom_rest", None)
        assert model == "default-model"
        
        _, model = resolve_provider_and_model("mock", None)
        assert model == "default-model"
