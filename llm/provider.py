"""LLM provider abstraction layer."""

import os
from typing import List, Callable, Optional
import openai
import anthropic
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_chat() -> Callable[[List[str]], str]:
    """
    Factory function that returns a chat callable based on the PROVIDER environment variable.
    
    Returns:
        Callable that takes a list of messages and returns a response string.
    """
    provider = os.getenv("PROVIDER", "openai").lower()
    
    if provider == "openai":
        return _get_openai_chat()
    elif provider == "anthropic":
        return _get_anthropic_chat()
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def _get_openai_chat() -> Callable[[List[str]], str]:
    """Get OpenAI chat function."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
    client = openai.OpenAI(api_key=api_key)
    
    def chat(messages: List[str]) -> str:
        """Call OpenAI API with messages."""
        formatted_messages = []
        for i, msg in enumerate(messages):
            role = "system" if i == 0 else "user"
            formatted_messages.append({"role": role, "content": msg})
        
        response = client.chat.completions.create(
            model=model_name,
            messages=formatted_messages,
            temperature=0.0,  # Deterministic as much as possible
            max_tokens=1000
        )
        return response.choices[0].message.content or ""
    
    return chat


def _get_anthropic_chat() -> Callable[[List[str]], str]:
    """Get Anthropic chat function."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")
    
    model_name = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet")
    client = Anthropic(api_key=api_key)
    
    def chat(messages: List[str]) -> str:
        """Call Anthropic API with messages."""
        system_prompt = messages[0] if messages else ""
        user_messages = messages[1:] if len(messages) > 1 else [""]
        
        # Combine user messages if multiple
        user_content = "\n\n".join(user_messages)
        
        response = client.messages.create(
            model=model_name,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
            temperature=0.0,  # Deterministic as much as possible
            max_tokens=1000
        )
        return response.content[0].text if response.content else ""
    
    return chat


# Extension examples (for documentation in README):

def _get_azure_openai_chat() -> Callable[[List[str]], str]:
    """
    Example extension for Azure OpenAI.
    
    Set environment variables:
    - AZURE_OPENAI_ENDPOINT
    - AZURE_OPENAI_API_KEY
    - AZURE_OPENAI_API_VERSION
    - AZURE_OPENAI_DEPLOYMENT_NAME
    """
    # from openai import AzureOpenAI
    # client = AzureOpenAI(
    #     api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    #     api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2023-12-01-preview"),
    #     azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    # )
    # deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    # ... implement similar to OpenAI but with deployment_name
    raise NotImplementedError("Azure OpenAI support - see comments for implementation pattern")


def _get_ollama_chat() -> Callable[[List[str]], str]:
    """
    Example extension for Ollama local models.
    
    Set environment variables:
    - OLLAMA_BASE_URL (default: http://localhost:11434)
    - OLLAMA_MODEL (e.g., llama2, codellama)
    """
    # import httpx
    # base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    # model = os.getenv("OLLAMA_MODEL", "llama2")
    # ... implement REST API calls to Ollama
    raise NotImplementedError("Ollama support - see comments for implementation pattern")


def _get_custom_rest_chat() -> Callable[[List[str]], str]:
    """
    Example extension for custom REST endpoint.
    
    Set environment variables:
    - CUSTOM_API_ENDPOINT
    - CUSTOM_API_KEY
    - CUSTOM_MODEL_NAME
    """
    # import httpx
    # endpoint = os.getenv("CUSTOM_API_ENDPOINT")
    # api_key = os.getenv("CUSTOM_API_KEY")
    # model = os.getenv("CUSTOM_MODEL_NAME")
    # ... implement REST API calls to custom endpoint
    raise NotImplementedError("Custom REST API support - see comments for implementation pattern")
