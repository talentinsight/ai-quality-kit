"""LLM provider abstraction layer."""

import os
import json
import asyncio
from typing import List, Callable, Optional
import openai
import anthropic
from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import HTTPException

from .resilient_client import get_resilient_client, CircuitBreakerError

# Load environment variables from .env file
load_dotenv()


def get_chat() -> Callable[[List[str]], str]:
    """
    Factory function that returns a chat callable based on the PROVIDER environment variable.
    
    Returns:
        Callable that takes a list of messages and returns a response string.
    """
    provider = os.getenv("PROVIDER", "openai").lower()
    return get_chat_for(provider)


def get_chat_for(provider: Optional[str] = None, model: Optional[str] = None) -> Callable[[List[str]], str]:
    """
    Factory function that returns a chat callable for specific provider/model.
    
    Args:
        provider: Provider name (openai, anthropic, gemini, custom_rest, mock)
        model: Model name (overrides environment default)
        
    Returns:
        Callable that takes a list of messages and returns a response string.
    """
    # Resolve provider from parameter or environment
    if provider is None:
        provider = os.getenv("PROVIDER", "openai").lower()
    else:
        provider = provider.lower()
    
    if provider == "openai":
        return _get_openai_chat(model)
    elif provider == "anthropic":
        return _get_anthropic_chat(model)
    elif provider == "gemini":
        return _get_gemini_chat(model)
    elif provider == "custom_rest":
        return _get_custom_rest_chat(model)
    elif provider == "mock":
        return _get_mock_chat(model)
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def _get_openai_chat(model_override: Optional[str] = None) -> Callable[[List[str]], str]:
    """Get OpenAI chat function."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI provider")
    
    model_name = model_override or os.getenv("MODEL_NAME", "gpt-4o-mini")
    client = openai.OpenAI(api_key=api_key)
    resilient_client = get_resilient_client()
    
    def chat(messages: List[str]) -> str:
        """Call OpenAI API with messages."""
        def _make_openai_call():
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
        
        # For now, just call the function directly without resilience
        # TODO: Make this properly async-compatible  
        return _make_openai_call()
    
    return chat


def _get_anthropic_chat(model_override: Optional[str] = None) -> Callable[[List[str]], str]:
    """Get Anthropic chat function."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required for Anthropic provider")
    
    model_name = model_override or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet")
    client = Anthropic(api_key=api_key)
    resilient_client = get_resilient_client()
    
    def chat(messages: List[str]) -> str:
        """Call Anthropic API with messages."""
        def _make_anthropic_call():
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
            # Handle different response types from Anthropic API
            if response.content and len(response.content) > 0:
                content_block = response.content[0]
                # Use getattr with default to safely access text attribute
                return getattr(content_block, 'text', str(content_block))
            return ""
        
        try:
            return asyncio.run(resilient_client.call_with_resilience(
                _make_anthropic_call, f"anthropic_{model_name}"
            ))
        except CircuitBreakerError:
            raise HTTPException(
                status_code=503, 
                detail="Service temporarily unavailable due to circuit breaker",
                headers={"X-Circuit-Open": "true"}
            )
    
    return chat


def _get_gemini_chat(model_override: Optional[str] = None) -> Callable[[List[str]], str]:
    """Get Google Gemini chat function."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required for Gemini provider")
    
    model_name = model_override or os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    
    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
    except ImportError:
        raise ValueError("google-generativeai package is required for Gemini provider")
    
    def chat(messages: List[str]) -> str:
        """Call Gemini API with messages."""
        # Combine all messages into a single prompt for Gemini
        combined_prompt = "\n\n".join(messages)
        
        response = model.generate_content(
            combined_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
                max_output_tokens=1000
            )
        )
        return response.text if response.text else ""
    
    return chat


def _get_custom_rest_chat(model_override: Optional[str] = None) -> Callable[[List[str]], str]:
    """Get custom REST API chat function."""
    base_url = os.getenv("CUSTOM_LLM_BASE_URL")
    if not base_url:
        raise ValueError("CUSTOM_LLM_BASE_URL environment variable is required for custom_rest provider")
    
    model_name = model_override or os.getenv("CUSTOM_MODEL_NAME", "custom-model")
    resilient_client = get_resilient_client()
    
    try:
        import httpx
    except ImportError:
        raise ValueError("httpx package is required for custom_rest provider")
    
    def chat(messages: List[str]) -> str:
        """Call custom REST API with messages."""
        def _make_custom_rest_call():
            # Format messages for generic REST API
            formatted_messages = []
            for i, msg in enumerate(messages):
                role = "system" if i == 0 else "user"
                formatted_messages.append({"role": role, "content": msg})
            
            payload = {
                "model": model_name,
                "messages": formatted_messages,
                "temperature": 0.0,
                "max_tokens": 1000
            }
            
            with httpx.Client() as client:
                response = client.post(
                    f"{base_url.rstrip('/')}/v1/chat/completions",
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                
                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # For now, just call the function directly without resilience
        # TODO: Make this properly async-compatible
        return _make_custom_rest_call()
    
    return chat


def _get_mock_chat(model_override: Optional[str] = None) -> Callable[[List[str]], str]:
    """Get mock chat function for testing."""
    model_name = model_override or "mock-model"
    
    def chat(messages: List[str]) -> str:
        """Mock chat function that returns deterministic responses."""
        if not messages:
            return "Mock response: No input provided"
        
        # Simple deterministic response based on input
        last_message = messages[-1].lower()
        
        # Safety-aware responses for testing (order matters - most specific first)
        if "ignore" in last_message or "forget" in last_message or "new instructions" in last_message:
            return "The context does not provide information to answer this question. I can only respond based on the provided context."
        elif "hello" in last_message or "hi" in last_message:
            return "Hello! This is a mock response from the AI assistant."
        elif "question" in last_message:
            return "Based on the context provided, I can give you a mock answer. The mock provider is working correctly."
        elif "?" in last_message:
            return "The context does not provide sufficient information to answer your question. Please check the provided context."
        elif "error" in last_message or "fail" in last_message:
            return "Mock error response: Something went wrong in the mock provider."
        else:
            return f"The context does not provide sufficient information to answer your request. Mock model {model_name} processed your message."
    
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


# Custom REST implementation is above in the main function
