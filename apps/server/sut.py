"""System Under Test (SUT) adapter for guardrails probing."""

import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class SUTAdapter(ABC):
    """Base adapter for System Under Test."""
    
    @abstractmethod
    async def ask(self, prompt: str) -> str:
        """Send a prompt to the SUT and get response."""
        pass


class MockSUTAdapter(SUTAdapter):
    """Mock SUT adapter for testing."""
    
    def __init__(self, response: str = "This is a test response."):
        self.response = response
    
    async def ask(self, prompt: str) -> str:
        """Return mock response."""
        return self.response


class OpenAISUTAdapter(SUTAdapter):
    """OpenAI API adapter."""
    
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo", endpoint: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint or "https://api.openai.com/v1"
        self._client = None
    
    def _get_client(self):
        """Get OpenAI client (lazy initialization)."""
        if self._client is None:
            try:
                import openai
                self._client = openai.AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.endpoint
                )
            except ImportError:
                raise ImportError("openai package required for OpenAI SUT adapter")
        return self._client
    
    async def ask(self, prompt: str) -> str:
        """Send prompt to OpenAI API."""
        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.7
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI SUT adapter failed: {e}")
            raise


class AnthropicSUTAdapter(SUTAdapter):
    """Anthropic API adapter."""
    
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        self.api_key = api_key
        self.model = model
        self._client = None
    
    def _get_client(self):
        """Get Anthropic client (lazy initialization)."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package required for Anthropic SUT adapter")
        return self._client
    
    async def ask(self, prompt: str) -> str:
        """Send prompt to Anthropic API."""
        try:
            client = self._get_client()
            response = await client.messages.create(
                model=self.model,
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text if response.content else ""
        except Exception as e:
            logger.error(f"Anthropic SUT adapter failed: {e}")
            raise


def create_sut_adapter(target_config: Dict[str, Any]) -> Optional[SUTAdapter]:
    """Create SUT adapter from target configuration."""
    try:
        provider = target_config.get("provider", "").lower()
        
        if provider == "openai":
            api_key = target_config.get("headers", {}).get("Authorization", "").replace("Bearer ", "")
            model = target_config.get("model", "gpt-3.5-turbo")
            endpoint = target_config.get("endpoint")
            return OpenAISUTAdapter(api_key, model, endpoint)
        
        elif provider == "anthropic":
            api_key = target_config.get("headers", {}).get("x-api-key", "")
            model = target_config.get("model", "claude-3-sonnet-20240229")
            return AnthropicSUTAdapter(api_key, model)
        
        elif provider == "mock" or not provider:
            # Default to mock for testing
            return MockSUTAdapter()
        
        else:
            logger.warning(f"Unsupported SUT provider: {provider}")
            return MockSUTAdapter()
    
    except Exception as e:
        logger.error(f"Failed to create SUT adapter: {e}")
        return MockSUTAdapter()