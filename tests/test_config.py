"""Unit tests for configuration module."""

import pytest
import os
from unittest.mock import patch


class TestConfig:
    """Test configuration loading and validation."""
    
    def test_default_config_loading(self, set_env_defaults):
        """Test that default configuration loads correctly."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.rag_service.config import Config
            
            config = Config()
            
            assert config.provider == "openai"
            assert config.model_name == "gpt-4o-mini"
            assert config.rag_top_k == 3  # Set by fixture
            # Note: enable_api_logging, enable_live_eval, cache_enabled are not in Config class
            assert config.openai_api_key == "test-key"
            assert config.anthropic_api_key == "test-key"
    
    def test_config_override(self, set_env_defaults):
        """Test that environment variables override defaults."""
        env_overrides = {
            **set_env_defaults,
            "PROVIDER": "anthropic",
            "MODEL_NAME": "claude-3-sonnet",
            "RAG_TOP_K": "5"
        }
        
        with patch.dict(os.environ, env_overrides):
            from apps.rag_service.config import Config
            
            config = Config()
            
            assert config.provider == "anthropic"
            assert config.model_name == "claude-3-sonnet"
            assert config.rag_top_k == 5
    
    def test_config_validation(self, set_env_defaults):
        """Test configuration validation."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.rag_service.config import Config
            
            config = Config()
            
            # Should not raise exception with valid config
            config.validate()
    
    def test_invalid_rag_top_k(self, set_env_defaults):
        """Test that invalid RAG_TOP_K raises error."""
        env_invalid = {
            **set_env_defaults,
            "RAG_TOP_K": "invalid"
        }
        
        with patch.dict(os.environ, env_invalid):
            from apps.rag_service.config import Config
            
            with pytest.raises(ValueError):
                config = Config()
    
    def test_missing_required_keys(self, set_env_defaults):
        """Test that missing required API keys are handled gracefully."""
        env_missing = {
            **set_env_defaults,
            "OPENAI_API_KEY": "",
            "ANTHROPIC_API_KEY": ""
        }
        
        with patch.dict(os.environ, env_missing):
            from apps.rag_service.config import Config
            
            config = Config()
            
            # Should not crash, but should have empty keys
            assert config.openai_api_key == ""
            assert config.anthropic_api_key == ""
    
    def test_provider_chat_function(self, set_env_defaults):
        """Test get_provider_chat function."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.rag_service.config import get_provider_chat
            
            # Test that function exists and is callable
            chat_func = get_provider_chat()
            assert callable(chat_func)
    
    def test_global_config_constants(self, set_env_defaults):
        """Test global config constants."""
        with patch.dict(os.environ, set_env_defaults):
            # Need to reload the module after patching environment
            import importlib
            import apps.rag_service.config
            
            # Reload to pick up new environment variables
            importlib.reload(apps.rag_service.config)
            
            from apps.rag_service.config import MODEL_NAME, PROVIDER, RAG_TOP_K
            
            assert MODEL_NAME == "gpt-4o-mini"
            assert PROVIDER == "openai"
            assert RAG_TOP_K == 3
    
    def test_config_instance_creation(self, set_env_defaults):
        """Test Config instance creation and attributes."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.rag_service.config import Config
            
            config = Config()
            
            # Check all expected attributes exist
            assert hasattr(config, 'openai_api_key')
            assert hasattr(config, 'anthropic_api_key')
            assert hasattr(config, 'model_name')
            assert hasattr(config, 'anthropic_model')
            assert hasattr(config, 'provider')
            assert hasattr(config, 'rag_top_k')
            assert hasattr(config, 'validate')
    
    def test_config_validation_openai_missing_key(self, set_env_defaults):
        """Test validation when OpenAI provider is selected but key is missing."""
        env_openai_missing = {
            **set_env_defaults,
            "PROVIDER": "openai",
            "OPENAI_API_KEY": ""
        }
        
        with patch.dict(os.environ, env_openai_missing):
            from apps.rag_service.config import Config
            
            config = Config()
            
            with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
                config.validate()
    
    def test_config_validation_anthropic_missing_key(self, set_env_defaults):
        """Test validation when Anthropic provider is selected but key is missing."""
        env_anthropic_missing = {
            **set_env_defaults,
            "PROVIDER": "anthropic",
            "ANTHROPIC_API_KEY": ""
        }
        
        with patch.dict(os.environ, env_anthropic_missing):
            from apps.rag_service.config import Config
            
            config = Config()
            
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is required"):
                config.validate()
    
    def test_config_validation_unknown_provider(self, set_env_defaults):
        """Test validation with unknown provider."""
        env_unknown = {
            **set_env_defaults,
            "PROVIDER": "unknown"
        }
        
        with patch.dict(os.environ, env_unknown):
            from apps.rag_service.config import Config
            
            config = Config()
            
            # Should not raise error for unknown provider
            config.validate()
