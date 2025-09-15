"""
Unit tests for MCP client functionality.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from apps.orchestrator.mcp_client import MCPClient, MCPClientAdapter, MCPTool, MCPResult


class TestMCPClient:
    """Test cases for MCPClient."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = MCPClient(
            endpoint="wss://test.example.com/mcp",
            auth={"bearer": "test-token"},
            timeouts={"connect_ms": 1000, "call_ms": 5000},
            retry={"retries": 1, "backoff_ms": 100}
        )
    
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful MCP connection."""
        with patch('websockets.connect') as mock_connect:
            mock_ws = AsyncMock()
            
            # Create an async function that returns mock_ws
            async def mock_connect_func(*args, **kwargs):
                return mock_ws
            
            mock_connect.side_effect = mock_connect_func
            
            await self.client.connect()
            
            assert self.client._connection == mock_ws
            mock_connect.assert_called_once()
            
            # Verify auth headers were passed
            call_args = mock_connect.call_args
            extra_headers = call_args[1]['extra_headers']
            assert 'Authorization' in extra_headers
    
    @pytest.mark.asyncio
    async def test_connect_with_retry(self):
        """Test MCP connection with retry on failure."""
        with patch('websockets.connect') as mock_connect:
            # First attempt fails, second succeeds
            mock_ws = AsyncMock()
            # Create async function for successful connection
            async def mock_connect_success(*args, **kwargs):
                return mock_ws
            
            mock_connect.side_effect = [
                Exception("Connection failed"), 
                mock_connect_success(*[], **{})
            ]
            
            with patch('asyncio.sleep') as mock_sleep:
                await self.client.connect()
            
            assert self.client._connection == mock_ws
            assert mock_connect.call_count == 2
            mock_sleep.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_timeout(self):
        """Test MCP connection timeout."""
        with patch('websockets.connect') as mock_connect:
            mock_connect.side_effect = asyncio.TimeoutError("Connection timeout")
            
            with pytest.raises(asyncio.TimeoutError):
                await self.client.connect()
    
    @pytest.mark.asyncio
    async def test_list_tools_success(self):
        """Test successful tool listing."""
        mock_ws = AsyncMock()
        self.client._connection = mock_ws
        
        # Mock response
        response = {
            "jsonrpc": "2.0",
            "id": "req_1",
            "result": {
                "tools": [
                    {
                        "name": "generate",
                        "description": "Generate text response",
                        "inputSchema": {"type": "object"},
                        "outputSchema": {"type": "object"}
                    },
                    {
                        "name": "search",
                        "description": "Search documents"
                    }
                ]
            }
        }
        
        mock_ws.recv.return_value = json.dumps(response)
        
        tools = await self.client.list_tools()
        
        assert len(tools) == 2
        assert tools[0].name == "generate"
        assert tools[0].description == "Generate text response"
        assert tools[1].name == "search"
        
        # Verify request was sent
        mock_ws.send.assert_called_once()
        sent_data = json.loads(mock_ws.send.call_args[0][0])
        assert sent_data["method"] == "tools/list"
    
    @pytest.mark.asyncio
    async def test_list_tools_error(self):
        """Test tool listing with server error."""
        mock_ws = AsyncMock()
        self.client._connection = mock_ws
        
        # Mock error response
        response = {
            "jsonrpc": "2.0",
            "id": "req_1",
            "error": {"code": -1, "message": "Server error"}
        }
        
        mock_ws.recv.return_value = json.dumps(response)
        
        with pytest.raises(Exception, match="MCP tools/list error"):
            await self.client.list_tools()
    
    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        """Test successful tool call."""
        mock_ws = AsyncMock()
        self.client._connection = mock_ws
        
        # Mock response
        response = {
            "jsonrpc": "2.0",
            "id": "req_1",
            "result": {
                "answer": "This is the response",
                "contexts": [{"text": "Context 1"}, {"text": "Context 2"}],
                "meta": {"model": "gpt-4o"}
            }
        }
        
        mock_ws.recv.return_value = json.dumps(response)
        
        result = await self.client.call_tool("generate", {"question": "Test question"})
        
        assert isinstance(result, MCPResult)
        assert result.text == "This is the response"
        assert result.meta is not None
        assert result.meta["model"] == "gpt-4o"
        assert result.error is None
        
        # Verify request was sent correctly
        mock_ws.send.assert_called_once()
        sent_data = json.loads(mock_ws.send.call_args[0][0])
        assert sent_data["method"] == "tools/call"
        assert sent_data["params"]["name"] == "generate"
        assert sent_data["params"]["arguments"]["question"] == "Test question"
    
    @pytest.mark.asyncio
    async def test_call_tool_error(self):
        """Test tool call with server error."""
        mock_ws = AsyncMock()
        self.client._connection = mock_ws
        
        # Mock error response
        response = {
            "jsonrpc": "2.0",
            "id": "req_1",
            "error": {"code": -1, "message": "Tool not found"}
        }
        
        mock_ws.recv.return_value = json.dumps(response)
        
        result = await self.client.call_tool("unknown", {})
        
        assert isinstance(result, MCPResult)
        assert result.error is not None
        assert "Tool not found" in result.error
    
    @pytest.mark.asyncio
    async def test_close_connection(self):
        """Test closing MCP connection."""
        mock_ws = AsyncMock()
        self.client._connection = mock_ws
        
        await self.client.close()
        
        mock_ws.close.assert_called_once()
        assert self.client._connection is None
    
    def test_redact_sensitive_data(self):
        """Test sensitive data redaction."""
        data = {
            "question": "What is AI?",
            "api_key": "secret-key-123",
            "bearer_token": "bearer-token-456",
            "normal_field": "normal-value"
        }
        
        redacted = self.client._redact_sensitive_data(data)
        
        assert redacted["question"] == "What is AI?"
        assert redacted["normal_field"] == "normal-value"
        assert redacted["api_key"] == "sec***23"
        assert redacted["bearer_token"] == "bea***56"


class TestMCPClientAdapter:
    """Test cases for MCPClientAdapter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_mcp_client = Mock(spec=MCPClient)
        self.tool_config = {
            "name": "generate",
            "arg_mapping": {
                "question_key": "question",
                "system_key": "system",
                "contexts_key": "contexts"
            },
            "shape": "messages",
            "static_args": {"format": "text"}
        }
        self.extraction_config = {
            "output_type": "json",
            "output_jsonpath": "$.answer",
            "contexts_jsonpath": "$.contexts[*].text"
        }
        
        self.adapter = MCPClientAdapter(
            mcp_client=self.mock_mcp_client,
            model="test-model",
            tool_config=self.tool_config,
            extraction_config=self.extraction_config
        )
    
    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test successful generation via MCP adapter."""
        # Mock MCP client response
        mcp_result = MCPResult(
            raw={
                "answer": "This is the answer",
                "contexts": [{"text": "Context 1"}, {"text": "Context 2"}],
                "meta": {"model": "gpt-4o"}
            },
            text="This is the answer",
            meta={"model": "gpt-4o"}
        )
        
        self.mock_mcp_client.call_tool = AsyncMock(return_value=mcp_result)
        
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "What is AI?"}
        ]
        
        result = await self.adapter.generate(messages, contexts=["Extra context"])
        
        assert result["text"] == "This is the answer"
        assert result["meta"]["model"] == "gpt-4o"
        assert len(result["contexts"]) == 2
        assert result["contexts"][0]["text"] == "Context 1"
        
        # Verify tool was called with correct arguments
        self.mock_mcp_client.call_tool.assert_called_once()
        call_args = self.mock_mcp_client.call_tool.call_args[0]
        assert call_args[0] == "generate"  # tool name
        
        tool_args = call_args[1]
        assert tool_args["question"] == "What is AI?"
        assert tool_args["system"] == "You are helpful"
        assert tool_args["contexts"] == ["Extra context"]
        assert tool_args["format"] == "text"  # static arg
    
    @pytest.mark.asyncio
    async def test_generate_with_jsonpath_extraction(self):
        """Test generation with JSONPath extraction."""
        # Mock MCP client response with nested structure
        mcp_result = MCPResult(
            raw={
                "response": {
                    "answer": "Extracted answer"
                },
                "retrieval": {
                    "contexts": [
                        {"text": "Context A", "score": 0.9},
                        {"text": "Context B", "score": 0.8}
                    ]
                }
            }
        )
        
        self.mock_mcp_client.call_tool = AsyncMock(return_value=mcp_result)
        
        # Update extraction config for nested structure
        self.adapter.extraction_config = {
            "output_jsonpath": "$.response.answer",
            "contexts_jsonpath": "$.retrieval.contexts[*].text"
        }
        
        messages = [{"role": "user", "content": "Test question"}]
        result = await self.adapter.generate(messages)
        
        assert result["text"] == "Extracted answer"
        assert len(result["contexts"]) == 2
        assert result["contexts"][0]["text"] == "Context A"
        assert result["contexts"][1]["text"] == "Context B"
    
    @pytest.mark.asyncio
    async def test_generate_error_handling(self):
        """Test error handling in adapter."""
        # Mock MCP client error
        mcp_result = MCPResult(
            raw={},
            error="Connection failed"
        )
        
        self.mock_mcp_client.call_tool = AsyncMock(return_value=mcp_result)
        
        messages = [{"role": "user", "content": "Test"}]
        
        with pytest.raises(Exception, match="Connection failed"):
            await self.adapter.generate(messages)
    
    def test_jsonpath_extraction_simple(self):
        """Test simple JSONPath extraction."""
        data = {"answer": "Simple answer"}
        result = self.adapter._extract_jsonpath(data, "$.answer")
        assert result == "Simple answer"
    
    def test_jsonpath_extraction_array(self):
        """Test JSONPath extraction from arrays."""
        data = {
            "contexts": [
                {"text": "Context 1"},
                {"text": "Context 2"}
            ]
        }
        result = self.adapter._extract_jsonpath(data, "$.contexts[*].text")
        assert len(result) == 2
        assert result[0]["text"] == "Context 1"
        assert result[1]["text"] == "Context 2"
    
    def test_jsonpath_extraction_nested(self):
        """Test nested JSONPath extraction."""
        data = {
            "response": {
                "data": {
                    "answer": "Nested answer"
                }
            }
        }
        result = self.adapter._extract_jsonpath(data, "$.response.data.answer")
        assert result == "Nested answer"
    
    @pytest.mark.asyncio
    async def test_generate_with_text_output_type(self):
        """Test MCPClientAdapter generate with text output type."""
        # Mock MCP client
        mock_mcp_client = AsyncMock()
        mock_result = MCPResult(
            raw="Plain text response",
            text="Plain text response"
        )
        mock_mcp_client.call_tool.return_value = mock_result
        
        # Create adapter with text output type
        tool_config = {
            "name": "generate",
            "shape": "messages",
            "arg_mapping": {
                "question_key": "question"
            }
        }
        extraction_config = {
            "output_type": "text"  # No JSONPath needed for text
        }
        
        adapter = MCPClientAdapter(mock_mcp_client, "test-model", tool_config, extraction_config)
        
        # Test generate
        messages = [{"role": "user", "content": "Hello"}]
        response = await adapter.generate(messages)
        
        # Verify response uses text directly
        assert response["text"] == "Plain text response"
        assert response["contexts"] == []
    
    @pytest.mark.asyncio
    async def test_generate_with_json_output_type_fallback(self):
        """Test MCPClientAdapter generate with JSON output type but JSONPath extraction fails."""
        # Mock MCP client
        mock_mcp_client = AsyncMock()
        mock_result = MCPResult(
            raw={"data": "response"},  # Different structure than expected
            text="Fallback text"
        )
        mock_mcp_client.call_tool.return_value = mock_result
        
        # Create adapter with JSON output type
        tool_config = {
            "name": "generate",
            "shape": "messages",
            "arg_mapping": {
                "question_key": "question"
            }
        }
        extraction_config = {
            "output_type": "json",
            "output_jsonpath": "$.answer"  # This path doesn't exist in the response
        }
        
        adapter = MCPClientAdapter(mock_mcp_client, "test-model", tool_config, extraction_config)
        
        # Test generate
        messages = [{"role": "user", "content": "Hello"}]
        response = await adapter.generate(messages)
        
        # Verify response falls back to raw JSON string when JSONPath fails
        assert response["text"] == "{'data': 'response'}"


@pytest.mark.asyncio
async def test_mcp_client_integration():
    """Integration test for MCP client with mock WebSocket."""
    
    # Mock WebSocket connection
    mock_ws = AsyncMock()
    
    with patch('websockets.connect') as mock_connect:
        # Create async function that returns mock_ws
        async def mock_connect_func(*args, **kwargs):
            return mock_ws
        
        mock_connect.side_effect = mock_connect_func
        
        client = MCPClient("wss://test.example.com/mcp")
        
        # Test connection
        await client.connect()
        assert client._connection == mock_ws
        
        # Mock tools/list response
        tools_response = {
            "jsonrpc": "2.0",
            "id": "req_1",
            "result": {
                "tools": [{"name": "generate", "description": "Generate text"}]
            }
        }
        mock_ws.recv.return_value = json.dumps(tools_response)
        
        # Test tool listing
        tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "generate"
        
        # Mock tools/call response
        call_response = {
            "jsonrpc": "2.0",
            "id": "req_2",
            "result": {"answer": "Generated response"}
        }
        mock_ws.recv.return_value = json.dumps(call_response)
        
        # Test tool calling
        result = await client.call_tool("generate", {"question": "Test"})
        assert result.text == "Generated response"
        
        # Test cleanup
        await client.close()
        mock_ws.close.assert_called_once()


def test_mcp_tool_dataclass():
    """Test MCPTool dataclass functionality."""
    tool = MCPTool(
        name="test_tool",
        description="A test tool",
        input_schema={"type": "object", "properties": {"input": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"output": {"type": "string"}}}
    )
    
    assert tool.name == "test_tool"
    assert tool.description == "A test tool"
    assert tool.input_schema is not None
    assert tool.input_schema["type"] == "object"
    assert tool.output_schema is not None
    assert tool.output_schema["type"] == "object"


def test_mcp_result_dataclass():
    """Test MCPResult dataclass functionality."""
    result = MCPResult(
        raw={"answer": "test", "meta": {"model": "gpt-4"}},
        text="test",
        meta={"model": "gpt-4"}
    )
    
    assert result.raw["answer"] == "test"
    assert result.text == "test"
    assert result.meta is not None
    assert result.meta["model"] == "gpt-4"
    assert result.error is None
    
    # Test error result
    error_result = MCPResult(raw={}, error="Something went wrong")
    assert error_result.error == "Something went wrong"
    assert error_result.text is None
