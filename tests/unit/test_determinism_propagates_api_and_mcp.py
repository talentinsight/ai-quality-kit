"""Unit tests for determinism propagation in API and MCP clients."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from apps.orchestrator.client_factory import (
    make_client, ApiClient, McpClient, DeterminismConfig
)
from apps.orchestrator.run_tests import OrchestratorRequest


class TestDeterminismPropagation:
    """Test determinism configuration propagation."""
    
    def test_determinism_config_creation(self):
        """Test DeterminismConfig creation with defaults."""
        config = DeterminismConfig()
        
        assert config.temperature == 0.0
        assert config.top_p == 1.0
        assert config.seed == 42
    
    def test_determinism_config_custom_values(self):
        """Test DeterminismConfig with custom values."""
        config = DeterminismConfig(temperature=0.5, top_p=0.9, seed=123)
        
        assert config.temperature == 0.5
        assert config.top_p == 0.9
        assert config.seed == 123
    
    def test_api_client_determinism_propagation(self):
        """Test that API client receives determinism configuration."""
        # Create request with determinism config
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            determinism={
                "temperature": 0.2,
                "top_p": 0.8,
                "seed": 999
            }
        )
        
        # Mock the get_chat_for function
        with patch('apps.orchestrator.client_factory.get_chat_for') as mock_get_chat:
            mock_chat_fn = Mock()
            mock_get_chat.return_value = mock_chat_fn
            
            # Create client
            client = make_client(request)
            
            # Verify client type and determinism config
            assert isinstance(client, ApiClient)
            assert client.determinism.temperature == 0.2
            assert client.determinism.top_p == 0.8
            assert client.determinism.seed == 999
            
            # Verify get_chat_for was called with correct parameters
            mock_get_chat.assert_called_once_with(
                provider="mock",
                model="mock-model",
                deterministic=True,
                test_flag_override={
                    "temperature": 0.2,
                    "top_p": 0.8,
                    "seed": 999
                }
            )
    
    def test_api_client_default_determinism(self):
        """Test API client with default determinism values."""
        # Create request without determinism config
        request = OrchestratorRequest(
            target_mode="api",
            provider="openai",
            model="gpt-4",
            suites=["rag_quality"]
        )
        
        with patch('apps.orchestrator.client_factory.get_chat_for') as mock_get_chat:
            mock_chat_fn = Mock()
            mock_get_chat.return_value = mock_chat_fn
            
            # Create client
            client = make_client(request)
            
            # Verify default determinism values
            assert client.determinism.temperature == 0.0
            assert client.determinism.top_p == 1.0
            assert client.determinism.seed == 42
            
            # Verify get_chat_for was called with defaults
            mock_get_chat.assert_called_once_with(
                provider="openai",
                model="gpt-4",
                deterministic=True,
                test_flag_override={
                    "temperature": 0.0,
                    "top_p": 1.0,
                    "seed": 42
                }
            )
    
    @pytest.mark.asyncio
    async def test_api_client_generate_with_determinism(self):
        """Test API client generate method with determinism."""
        # Create request with determinism
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            determinism={"temperature": 0.1, "top_p": 0.95, "seed": 555}
        )
        
        with patch('apps.orchestrator.client_factory.get_chat_for') as mock_get_chat:
            # Mock chat function
            mock_chat_fn = Mock(return_value="Deterministic response")
            mock_get_chat.return_value = mock_chat_fn
            
            # Create and use client
            client = make_client(request)
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 2+2?"}
            ]
            
            result = await client.generate(messages)
            
            # Verify response
            assert result["text"] == "Deterministic response"
            assert "prompt_tokens" in result
            assert "completion_tokens" in result
            
            # Verify chat function was called
            mock_chat_fn.assert_called_once()
    
    def test_mcp_client_determinism_propagation(self):
        """Test that MCP client receives determinism configuration."""
        # Create request with determinism config
        request = OrchestratorRequest(
            target_mode="mcp",
            mcp_server_url="http://localhost:3000",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            determinism={
                "temperature": 0.3,
                "top_p": 0.7,
                "seed": 777
            }
        )
        
        # Create client
        client = make_client(request)
        
        # Verify client type and determinism config
        assert isinstance(client, McpClient)
        assert client.determinism.temperature == 0.3
        assert client.determinism.top_p == 0.7
        assert client.determinism.seed == 777
        assert client.mcp_endpoint == "http://localhost:3000"
    
    @pytest.mark.asyncio
    async def test_mcp_client_generate_stub(self):
        """Test MCP client generate method (stub implementation)."""
        # Create request
        request = OrchestratorRequest(
            target_mode="mcp",
            mcp_server_url="http://localhost:3000",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            determinism={"temperature": 0.0, "top_p": 1.0, "seed": 42}
        )
        
        # Create client
        client = make_client(request)
        
        messages = [
            {"role": "user", "content": "Test question for MCP"}
        ]
        
        # Call generate (should use stub implementation)
        result = await client.generate(messages)
        
        # Verify stub response
        assert "text" in result
        assert "Mock MCP response" in result["text"]
        assert "Test question for MCP" in result["text"]
        assert "prompt_tokens" in result
        assert "completion_tokens" in result
    
    def test_invalid_target_mode_error(self):
        """Test error handling for invalid target mode."""
        # Create a valid request first, then modify target_mode directly
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"]
        )
        
        # Bypass Pydantic validation by setting the attribute directly
        request.target_mode = "invalid"
        
        with pytest.raises(ValueError, match="Unsupported target_mode"):
            make_client(request)
    
    def test_missing_mcp_endpoint_error(self):
        """Test error handling for missing MCP endpoint."""
        request = OrchestratorRequest(
            target_mode="mcp",
            # Missing mcp_server_url and mcp_endpoint
            provider="mock",
            model="mock-model",
            suites=["rag_quality"]
        )
        
        with pytest.raises(ValueError, match="MCP endpoint is required"):
            make_client(request)
    
    def test_mcp_endpoint_fallback(self):
        """Test MCP endpoint fallback from mcp_endpoint field."""
        request = OrchestratorRequest(
            target_mode="mcp",
            mcp_endpoint="http://localhost:4000",  # Use mcp_endpoint instead of mcp_server_url
            provider="mock",
            model="mock-model",
            suites=["rag_quality"]
        )
        
        client = make_client(request)
        
        assert isinstance(client, McpClient)
        assert client.mcp_endpoint == "http://localhost:4000"
    
    def test_api_url_fallback(self):
        """Test API URL fallback from server_url field."""
        request = OrchestratorRequest(
            target_mode="api",
            server_url="http://localhost:8080",  # Use server_url instead of api_base_url
            provider="custom_rest",
            model="custom-model",
            suites=["rag_quality"]
        )
        
        with patch('apps.orchestrator.client_factory.get_chat_for') as mock_get_chat:
            mock_chat_fn = Mock()
            mock_get_chat.return_value = mock_chat_fn
            
            client = make_client(request)
            
            assert isinstance(client, ApiClient)
            # The URL handling is done by the underlying provider system
            # We just verify the client was created successfully
