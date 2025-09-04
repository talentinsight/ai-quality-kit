"""Client factory for API and MCP modes with unified interface."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass

from llm.provider import get_chat_for

logger = logging.getLogger(__name__)


@dataclass
class DeterminismConfig:
    """Determinism configuration for LLM calls."""
    temperature: float = 0.0
    top_p: float = 1.0
    seed: int = 42


class BaseClient(ABC):
    """Base client interface for API and MCP modes."""
    
    def __init__(self, provider: str, model: str, determinism: Optional[DeterminismConfig] = None):
        self.provider = provider
        self.model = model
        self.determinism = determinism or DeterminismConfig()
    
    @abstractmethod
    async def generate(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """
        Generate response from messages.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional generation parameters
            
        Returns:
            Dict with 'text', 'prompt_tokens', 'completion_tokens'
        """
        pass


class ApiClient(BaseClient):
    """Client for API mode using existing provider abstraction."""
    
    def __init__(self, provider: str, model: str, determinism: Optional[DeterminismConfig] = None):
        super().__init__(provider, model, determinism)
        
        # Get chat function from existing provider system
        self.chat_fn = get_chat_for(
            provider=provider,
            model=model,
            deterministic=True,
            test_flag_override={
                "temperature": self.determinism.temperature,
                "top_p": self.determinism.top_p,
                "seed": self.determinism.seed
            }
        )
    
    async def generate(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """Generate response using existing provider system."""
        try:
            # Convert messages to string list format expected by existing system
            message_strings = []
            for msg in messages:
                if msg.get('role') == 'system':
                    message_strings.insert(0, msg['content'])  # System message first
                else:
                    message_strings.append(msg['content'])
            
            # Call existing chat function
            response_text = self.chat_fn(message_strings)
            
            # Return standardized response format
            return {
                'text': response_text,
                'prompt_tokens': sum(len(msg['content'].split()) for msg in messages),
                'completion_tokens': len(response_text.split())
            }
            
        except Exception as e:
            logger.error(f"API client error for {self.provider}/{self.model}: {e}")
            raise


class McpClient(BaseClient):
    """Client for MCP mode - currently a stub with TODO for real implementation."""
    
    def __init__(self, provider: str, model: str, mcp_endpoint: str, determinism: Optional[DeterminismConfig] = None):
        super().__init__(provider, model, determinism)
        self.mcp_endpoint = mcp_endpoint
        
        # TODO: Implement real MCP client when MCP infrastructure is ready
        logger.warning(f"MCP client is a stub - endpoint: {mcp_endpoint}")
    
    async def generate(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """Generate response via MCP - currently stubbed."""
        # TODO: Implement real MCP communication
        # For now, return a mock response to enable testing
        
        logger.info(f"MCP stub call to {self.mcp_endpoint} with {len(messages)} messages")
        
        # Extract user message for mock response
        user_message = ""
        for msg in messages:
            if msg.get('role') == 'user':
                user_message = msg['content']
                break
        
        # Generate a simple mock response based on the question
        mock_response = f"Mock MCP response for: {user_message[:50]}..."
        
        return {
            'text': mock_response,
            'prompt_tokens': sum(len(msg['content'].split()) for msg in messages),
            'completion_tokens': len(mock_response.split())
        }


def make_client(request) -> Union[ApiClient, McpClient]:
    """
    Create appropriate client based on request configuration.
    
    Args:
        request: OrchestratorRequest with target_mode and other config
        
    Returns:
        ApiClient or McpClient instance
        
    Raises:
        ValueError: If configuration is invalid
    """
    # Extract determinism config
    determinism = None
    if request.determinism:
        determinism = DeterminismConfig(
            temperature=request.determinism.get('temperature', 0.0),
            top_p=request.determinism.get('top_p', 1.0),
            seed=request.determinism.get('seed', 42)
        )
    
    if request.target_mode == "api":
        # Use server_url or api_base_url for API mode
        api_url = request.server_url or request.api_base_url
        if not api_url and request.provider not in ['openai', 'anthropic', 'gemini', 'mock']:
            logger.warning(f"No API URL provided for {request.provider}, using provider defaults")
        
        return ApiClient(
            provider=request.provider,
            model=request.model,
            determinism=determinism
        )
    
    elif request.target_mode == "mcp":
        # Use mcp_endpoint or mcp_server_url for MCP mode
        mcp_endpoint = request.mcp_endpoint or request.mcp_server_url
        if not mcp_endpoint:
            raise ValueError("MCP endpoint is required for MCP mode")
        
        return McpClient(
            provider=request.provider,
            model=request.model,
            mcp_endpoint=mcp_endpoint,
            determinism=determinism
        )
    
    else:
        raise ValueError(f"Unsupported target_mode: {request.target_mode}")
