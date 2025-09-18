"""
MCP (Model Context Protocol) client implementation.

This module provides a WebSocket-based client for communicating with MCP servers,
supporting tool discovery, tool calling, and proper error handling with timeouts and retries.
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Union, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    import websockets
    from .client_factory import BaseClient
else:
    # Runtime import to avoid circular dependency
    BaseClient = object

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """Represents an MCP tool."""
    name: str
    description: str
    input_schema: Optional[Dict] = None
    output_schema: Optional[Dict] = None


@dataclass
class MCPResult:
    """Represents an MCP tool call result."""
    raw: Any
    text: Optional[str] = None
    meta: Optional[Dict] = None
    error: Optional[str] = None


class MCPClient:
    """Client for MCP (Model Context Protocol) servers."""
    
    def __init__(self, endpoint: str, auth: Optional[Dict] = None, 
                 timeouts: Optional[Dict] = None, retry: Optional[Dict] = None):
        self.endpoint = endpoint
        self.auth = auth or {}
        self.timeouts = timeouts or {"connect_ms": 5000, "call_ms": 30000}
        self.retry = retry or {"retries": 2, "backoff_ms": 250}
        self._connection: Optional[Any] = None
        self._tools_cache = None
        self._request_id = 0
        
        logger.info(f"MCP client initialized for {endpoint}")
    
    async def connect(self):
        """Connect to MCP server via WebSocket."""
        try:
            try:
                import websockets  # type: ignore
            except ImportError:
                raise Exception("websockets library is required for MCP support. Install with: pip install websockets")
            
            # Add auth headers if provided
            extra_headers = {}
            if self.auth.get("bearer"):
                extra_headers["Authorization"] = f"Bearer {self._redact_for_log(self.auth['bearer'])}"
            if self.auth.get("headers"):
                # Redact sensitive headers for logging
                safe_headers = {k: self._redact_for_log(v) if self._is_sensitive_key(k) else v 
                              for k, v in self.auth["headers"].items()}
                extra_headers.update(self.auth["headers"])  # Use real headers for connection
                logger.debug(f"MCP auth headers: {safe_headers}")
            
            # Connect with timeout and retry
            connect_timeout = self.timeouts.get("connect_ms", 5000) / 1000
            
            for attempt in range(self.retry.get("retries", 2) + 1):
                try:
                    self._connection = await asyncio.wait_for(
                        websockets.connect(self.endpoint, extra_headers=extra_headers),
                        timeout=connect_timeout
                    )
                    logger.info(f"MCP connected to {self.endpoint}")
                    return
                    
                except Exception as e:
                    if attempt < self.retry.get("retries", 2):
                        backoff = self.retry.get("backoff_ms", 250) * (2 ** attempt) / 1000
                        logger.warning(f"MCP connection attempt {attempt + 1} failed, retrying in {backoff}s: {e}")
                        await asyncio.sleep(backoff)
                    else:
                        raise
            
        except Exception as e:
            logger.error(f"MCP connection failed to {self.endpoint}: {e}")
            raise
    
    async def list_tools(self) -> List[MCPTool]:
        """List available tools from MCP server."""
        if self._tools_cache:
            return self._tools_cache
            
        try:
            if not self._connection:
                await self.connect()
            
            # Send tools/list RPC
            request_id = self._get_next_id()
            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/list",
                "params": {}
            }
            
            assert self._connection is not None, "MCP connection not established"
            await self._connection.send(json.dumps(request))
            response = await self._receive_response(request_id)
            
            if "error" in response:
                raise Exception(f"MCP tools/list error: {response['error']}")
            
            tools = []
            for tool_data in response.get("result", {}).get("tools", []):
                tools.append(MCPTool(
                    name=tool_data["name"],
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("inputSchema"),
                    output_schema=tool_data.get("outputSchema")
                ))
            
            self._tools_cache = tools
            logger.info(f"MCP discovered {len(tools)} tools: {[t.name for t in tools]}")
            return tools
            
        except Exception as e:
            logger.error(f"MCP list_tools failed: {e}")
            raise
    
    async def call_tool(self, name: str, args: Dict) -> MCPResult:
        """Call an MCP tool."""
        try:
            if not self._connection:
                await self.connect()
            
            # Redact sensitive data in logs
            safe_args = self._redact_sensitive_data(args)
            logger.debug(f"MCP calling tool {name} with args: {safe_args}")
            
            # Send tools/call RPC
            request_id = self._get_next_id()
            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": name,
                    "arguments": args
                }
            }
            
            assert self._connection is not None, "MCP connection not established"
            await self._connection.send(json.dumps(request))
            response = await self._receive_response(request_id)
            
            if "error" in response:
                return MCPResult(
                    raw=response,
                    error=f"MCP tool error: {response['error']}"
                )
            
            result_data = response.get("result", {})
            
            # Extract text if available
            text = None
            if isinstance(result_data, dict):
                text = result_data.get("text") or result_data.get("content") or result_data.get("answer")
            elif isinstance(result_data, str):
                text = result_data
            
            # Extract meta information
            meta = {}
            if isinstance(result_data, dict):
                meta = result_data.get("meta", {}) or {}
                # Look for model info in common locations
                if "model" in result_data:
                    meta["model"] = result_data["model"]
            
            logger.debug(f"MCP tool {name} completed successfully")
            return MCPResult(
                raw=result_data,
                text=text,
                meta=meta
            )
            
        except Exception as e:
            logger.error(f"MCP call_tool failed for {name}: {e}")
            return MCPResult(
                raw={},
                error=str(e)
            )
    
    async def close(self):
        """Close MCP connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("MCP connection closed")
    
    async def _receive_response(self, request_id: str) -> Dict:
        """Receive and parse response for a specific request ID."""
        call_timeout = self.timeouts.get("call_ms", 30000) / 1000
        
        assert self._connection is not None, "MCP connection not established"
        response_text = await asyncio.wait_for(
            self._connection.recv(), 
            timeout=call_timeout
        )
        response = json.loads(response_text)
        
        # Verify response ID matches request
        if response.get("id") != request_id:
            raise Exception(f"Response ID mismatch: expected {request_id}, got {response.get('id')}")
        
        return response
    
    def _get_next_id(self) -> str:
        """Generate next request ID."""
        self._request_id += 1
        return f"req_{self._request_id}"
    
    def _redact_sensitive_data(self, data: Dict) -> Dict:
        """Redact sensitive data for logging."""
        redacted = {}
        for key, value in data.items():
            if self._is_sensitive_key(key):
                redacted[key] = self._redact_for_log(str(value))
            else:
                redacted[key] = value
        return redacted
    
    def _is_sensitive_key(self, key: str) -> bool:
        """Check if a key contains sensitive data."""
        return any(sensitive in key.lower() for sensitive in ["token", "key", "secret", "password", "auth", "bearer"])
    
    def _redact_for_log(self, value: str) -> str:
        """Redact a sensitive value for logging."""
        if len(value) <= 8:
            return "***"
        return f"{value[:3]}***{value[-2:]}"


class MCPClientAdapter(BaseClient):  # type: ignore
    """Adapter to make MCPClient compatible with existing BaseClient interface."""
    
    def __init__(self, mcp_client: MCPClient, model: str, tool_config: Dict, extraction_config: Dict):
        # Initialize BaseClient if available, otherwise just set attributes
        if hasattr(BaseClient, '__init__') and BaseClient != object:
            super().__init__("mcp", model)
        else:
            self.provider = "mcp"
            self.model = model
            self.determinism = None
        
        # MCP-specific attributes
        self.mcp_client = mcp_client
        self.tool_config = tool_config
        self.extraction_config = extraction_config
    
    async def generate(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """Generate response via MCP using configured tool and argument mapping."""
        try:
            # Build tool arguments based on configuration
            args = {}
            
            # Apply static args first
            if self.tool_config.get("static_args"):
                args.update(self.tool_config["static_args"])
            
            # Map message content to tool arguments
            arg_mapping = self.tool_config["arg_mapping"]
            
            for msg in messages:
                role = msg.get('role')
                content = msg.get('content', '')
                
                if role == 'system' and arg_mapping.get('system_key'):
                    args[arg_mapping['system_key']] = content
                elif role == 'user' and arg_mapping.get('question_key'):
                    args[arg_mapping['question_key']] = content
            
            # Add contexts if provided in kwargs and configured
            if 'contexts' in kwargs and arg_mapping.get('contexts_key'):
                args[arg_mapping['contexts_key']] = kwargs['contexts']
            
            # Add top_k if provided and configured
            if 'top_k' in kwargs and arg_mapping.get('topk_key'):
                args[arg_mapping['topk_key']] = kwargs['top_k']
            
            # Call the MCP tool
            result = await self.mcp_client.call_tool(self.tool_config["name"], args)
            
            if result.error:
                raise Exception(result.error)
            
            # Extract answer based on output_type configuration
            answer_text = result.text
            output_type = self.extraction_config.get("output_type", "json")
            
            if output_type == "json" and self.extraction_config.get("output_jsonpath") and result.raw:
                try:
                    answer_text = self._extract_jsonpath(result.raw, self.extraction_config["output_jsonpath"])
                except Exception as e:
                    logger.warning(f"JSONPath extraction failed, using fallback: {e}")
                    answer_text = result.text or str(result.raw)
            elif output_type == "text":
                # For text output, use the raw text response or stringify the result
                answer_text = result.text or str(result.raw)
            
            # Extract contexts if configured
            contexts = []
            if self.extraction_config.get("contexts_jsonpath") and result.raw:
                try:
                    contexts = self._extract_jsonpath(result.raw, self.extraction_config["contexts_jsonpath"])
                    if not isinstance(contexts, list):
                        contexts = [contexts] if contexts else []
                except Exception as e:
                    logger.warning(f"Contexts JSONPath extraction failed: {e}")
            
            return {
                'text': answer_text or str(result.raw),
                'prompt_tokens': len(str(args).split()),
                'completion_tokens': len((answer_text or "").split()),
                'meta': result.meta,
                'contexts': contexts,
                'raw_result': result.raw
            }
            
        except Exception as e:
            logger.error(f"MCP generate failed: {e}")
            raise
    
    def _extract_jsonpath(self, data: Any, jsonpath: str) -> Any:
        """Extract data using JSONPath expression."""
        # Simple JSONPath implementation for basic cases
        # For production, consider using a proper JSONPath library
        
        if jsonpath.startswith("$."):
            path = jsonpath[2:]  # Remove "$."
            
            current = data
            for part in path.split('.'):
                if '[*]' in part:
                    # Handle array extraction like "contexts[*].text"
                    field = part.replace('[*]', '')
                    if field and isinstance(current, dict):
                        current = current.get(field, [])
                    if isinstance(current, list):
                        # Extract from all items in array
                        if '.' in path[path.index(part) + len(part) + 1:]:
                            # More path after array
                            remaining_path = path[path.index(part) + len(part) + 1:]
                            result = []
                            for item in current:
                                try:
                                    result.append(self._extract_jsonpath(item, f"$.{remaining_path}"))
                                except:
                                    pass
                            return result
                        else:
                            return current
                else:
                    if isinstance(current, dict):
                        current = current.get(part)
                    else:
                        return None
            
            return current
        
        return data
