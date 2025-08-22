"""Configuration management for RAG service."""

import os
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class for RAG service."""
    
    def __init__(self):
        self.openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
        self.model_name: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
        self.anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet")
        self.provider: str = os.getenv("PROVIDER", "openai")
        self.rag_top_k: int = int(os.getenv("RAG_TOP_K", "4"))
        
    def validate(self) -> None:
        """Validate required configuration values."""
        if self.provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when using OpenAI provider")
        elif self.provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when using Anthropic provider")


# Global config instance
config = Config()

# Typed constants for direct access
MODEL_NAME: str = config.model_name
PROVIDER: str = config.provider
RAG_TOP_K: int = config.rag_top_k


def get_provider_chat():
    """Get chat function from llm provider module."""
    from llm.provider import get_chat
    return get_chat()
