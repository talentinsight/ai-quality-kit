"""Configuration management for RAG service."""

import os
from dotenv import load_dotenv
from typing import Optional, Set, Tuple

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class for RAG service."""
    
    def __init__(self):
        self.openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
        self.google_api_key: Optional[str] = os.getenv("GOOGLE_API_KEY")
        self.model_name: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
        self.anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet")
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        self.provider: str = os.getenv("PROVIDER", "openai")
        self.rag_top_k: int = int(os.getenv("RAG_TOP_K", "4"))
        self.allowed_providers: Set[str] = set(
            provider.strip() for provider in 
            os.getenv("ALLOWED_PROVIDERS", "openai,anthropic,gemini,custom_rest,mock").split(",")
        )
        
    def validate(self) -> None:
        """Validate required configuration values."""
        if self.provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when using OpenAI provider")
        elif self.provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when using Anthropic provider")
        elif self.provider == "gemini" and not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when using Gemini provider")


# Global config instance
config = Config()

# Typed constants for direct access
MODEL_NAME: str = config.model_name
PROVIDER: str = config.provider
RAG_TOP_K: int = config.rag_top_k
ALLOWED_PROVIDERS: Set[str] = config.allowed_providers


def resolve_provider_and_model(override_provider: Optional[str], override_model: Optional[str]) -> Tuple[str, str]:
    """
    Resolve provider and model from overrides or environment defaults.
    
    Args:
        override_provider: Provider override from request
        override_model: Model override from request
        
    Returns:
        Tuple of (provider, model)
        
    Raises:
        ValueError: If provider not in allowed list
    """
    # Resolve provider
    provider = override_provider or config.provider
    
    # Validate provider is allowed
    if provider not in config.allowed_providers:
        raise ValueError(f"Provider '{provider}' not in allowed providers: {', '.join(config.allowed_providers)}")
    
    # Resolve model based on provider
    if override_model:
        model = override_model
    elif provider == "openai":
        model = config.model_name
    elif provider == "anthropic":
        model = config.anthropic_model
    elif provider == "gemini":
        model = config.gemini_model
    else:
        # For custom_rest and mock, use override or generic default
        model = override_model or "default-model"
    
    return provider, model


def get_provider_chat():
    """Get chat function from llm provider module."""
    from llm.provider import get_chat
    return get_chat()
