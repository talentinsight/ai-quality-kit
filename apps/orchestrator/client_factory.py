"""Client factory for API and MCP modes with unified interface."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .mcp_client import MCPClientAdapter
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


def make_client(request) -> Union[ApiClient, McpClient, 'MCPClientAdapter']:
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
        # Check for structured target configuration first, then fallback to legacy fields
        if request.target and request.target.get("mode") == "mcp" and request.target.get("mcp"):
            mcp_config = request.target["mcp"]
            endpoint = mcp_config["endpoint"]
            
            # Import MCP client classes
            from .mcp_client import MCPClient, MCPClientAdapter
            
            # Create MCP client
            mcp_client = MCPClient(
                endpoint=endpoint,
                auth=mcp_config.get("auth"),
                timeouts=mcp_config.get("timeouts"),
                retry=mcp_config.get("retry")
            )
            
            # Create adapter with tool and extraction config
            return MCPClientAdapter(
                mcp_client=mcp_client,
                model=request.model,
                tool_config=mcp_config["tool"],
                extraction_config=mcp_config["extraction"]
            )
        else:
            # Fallback to legacy MCP configuration
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


def make_baseline_client(preset: str, model: str, decoding_config: dict, target_mode: str = "api") -> Union[BaseClient, 'MCPClientAdapter']:
    """
    Create a baseline client for Compare Mode with specific vendor/model configuration.
    
    Args:
        preset: Vendor preset (e.g., "openai", "anthropic", "gemini", "mcp")
        model: Model name (e.g., "gpt-4o-mini", "claude-3-5-sonnet")
        decoding_config: Decoding parameters (temperature, top_p, max_tokens)
        target_mode: Client type - "api" for vendor APIs, "mcp" for MCP servers
        
    Returns:
        BaseClient instance (ApiClient or MCPClientAdapter) configured for baseline comparison
        
    Raises:
        ValueError: If preset is not supported
    """
    # Validate supported presets
    supported_presets = {'openai', 'anthropic', 'gemini', 'mock', 'mcp'}
    if preset not in supported_presets:
        raise ValueError(f"Unsupported baseline preset: {preset}. Supported: {supported_presets}")
    
    # Create determinism config from decoding parameters
    determinism = DeterminismConfig(
        temperature=decoding_config.get('temperature', 0.0),
        top_p=decoding_config.get('top_p', 1.0),
        seed=decoding_config.get('seed', 42)
    )
    
    # Create appropriate client based on target mode
    if target_mode == "mcp" or preset == "mcp":
        # For MCP baseline, use MCP client with deterministic settings
        from .mcp_client import MCPClient, MCPClientAdapter
        
        # Create a baseline MCP client with default configuration
        mcp_client = MCPClient(
            endpoint="mcp://baseline",  # Placeholder MCP URL for baseline
            timeouts={"connect_ms": 5000, "call_ms": 30000},
            retry={"retries": 2, "backoff_ms": 250}
        )
        
        # Create adapter with default tool configuration for baseline
        tool_config = {
            "name": "generate",
            "arg_mapping": {
                "question_key": "question",
                "system_key": "system",
                "contexts_key": "contexts"
            },
            "shape": "messages",
            "static_args": {}
        }
        
        extraction_config = {
            "output_jsonpath": "$.answer",
            "contexts_jsonpath": "$.contexts[*].text"
        }
        
        return MCPClientAdapter(
            mcp_client=mcp_client,
            model=model,
            tool_config=tool_config,
            extraction_config=extraction_config
        )
    else:
        # Create API client (baseline uses vendor presets, not custom endpoints)
        return ApiClient(
            provider=preset,
            model=model,
            determinism=determinism
        )
