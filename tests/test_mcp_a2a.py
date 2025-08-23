"""Tests for MCP and A2A functionality."""

import pytest
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def test_mcp_enabled_check():
    """Test MCP enabled/disabled functionality."""
    from apps.mcp.server import is_mcp_enabled
    
    with patch.dict(os.environ, {"MCP_ENABLED": "true"}):
        assert is_mcp_enabled() is True
    
    with patch.dict(os.environ, {"MCP_ENABLED": "false"}):
        assert is_mcp_enabled() is False
    
    # Test default
    with patch.dict(os.environ, {}, clear=True):
        assert is_mcp_enabled() is True


def test_ask_rag_mcp_tool():
    """Test ask_rag MCP tool."""
    from apps.mcp.server import ask_rag
    
    with patch.dict(os.environ, {"MCP_ENABLED": "true", "OFFLINE_MODE": "true"}):
        result = ask_rag("What is AI?", "mock", "mock-model")
        
        assert "answer" in result
        assert "context" in result
        assert "latency_ms" in result
        assert "provider" in result
        assert "model" in result
        assert "source" in result
        
        assert result["provider"] == "mock"
        assert result["model"] == "mock-model"
        assert result["source"] == "mcp_mock"


def test_ask_rag_mcp_disabled():
    """Test ask_rag when MCP is disabled."""
    from apps.mcp.server import ask_rag
    
    with patch.dict(os.environ, {"MCP_ENABLED": "false"}):
        result = ask_rag("What is AI?")
        
        assert "error" in result
        assert result["error"] == "MCP is disabled"
        assert result["source"] == "disabled"


def test_eval_rag_mcp_tool():
    """Test eval_rag MCP tool."""
    from apps.mcp.server import eval_rag
    
    with patch.dict(os.environ, {"MCP_ENABLED": "true"}):
        result = eval_rag("What is AI?", "AI is artificial intelligence")
        
        assert "faithfulness" in result
        assert "context_recall" in result
        assert "notes" in result
        
        assert isinstance(result["faithfulness"], float)
        assert isinstance(result["context_recall"], float)
        assert 0.0 <= result["faithfulness"] <= 1.0
        assert 0.0 <= result["context_recall"] <= 1.0


def test_eval_rag_without_answer():
    """Test eval_rag without providing answer (should generate one)."""
    from apps.mcp.server import eval_rag
    
    with patch.dict(os.environ, {"MCP_ENABLED": "true", "OFFLINE_MODE": "true"}):
        with patch('apps.mcp.server.ask_rag') as mock_ask_rag:
            mock_ask_rag.return_value = {
                "answer": "Generated answer",
                "context": ["context"],
                "provider": "mock",
                "model": "mock"
            }
            
            result = eval_rag("What is AI?")
            
            assert "faithfulness" in result
            assert "context_recall" in result
            mock_ask_rag.assert_called_once()


def test_list_tests_mcp_tool():
    """Test list_tests MCP tool."""
    from apps.mcp.server import list_tests
    
    with patch.dict(os.environ, {"MCP_ENABLED": "true"}):
        result = list_tests()
        
        assert "suites" in result
        assert "total_suites" in result
        
        assert len(result["suites"]) > 0
        assert result["total_suites"] == len(result["suites"])
        
        # Check suite structure
        for suite in result["suites"]:
            assert "name" in suite
            assert "description" in suite
            assert "test_count" in suite


def test_run_tests_mcp_tool():
    """Test run_tests MCP tool."""
    from apps.mcp.server import run_tests
    
    with patch.dict(os.environ, {"MCP_ENABLED": "true"}):
        config = {
            "suites": ["rag_quality", "performance"],
            "provider": "mock",
            "model": "mock-model"
        }
        
        result = run_tests(config)
        
        assert "run_id" in result
        assert "summary" in result
        assert "counts" in result
        
        assert result["run_id"] is not None
        assert "overall" in result["summary"]


def test_mcp_tools_registry():
    """Test MCP tools registry structure."""
    from apps.mcp.server import MCP_TOOLS
    
    expected_tools = ["ask_rag", "eval_rag", "list_tests", "run_tests"]
    
    for tool_name in expected_tools:
        assert tool_name in MCP_TOOLS
        
        tool_def = MCP_TOOLS[tool_name]
        assert "function" in tool_def
        assert "description" in tool_def
        assert "parameters" in tool_def
        
        # Verify function is callable
        assert callable(tool_def["function"])


def test_a2a_enabled_check():
    """Test A2A enabled/disabled functionality."""
    from apps.a2a.api import is_a2a_enabled
    
    with patch.dict(os.environ, {"A2A_ENABLED": "true"}):
        assert is_a2a_enabled() is True
    
    with patch.dict(os.environ, {"A2A_ENABLED": "false"}):
        assert is_a2a_enabled() is False
    
    # Test default
    with patch.dict(os.environ, {}, clear=True):
        assert is_a2a_enabled() is True


@pytest.mark.asyncio
async def test_a2a_manifest_endpoint():
    """Test A2A manifest endpoint."""
    from apps.a2a.api import get_manifest
    
    with patch.dict(os.environ, {"A2A_ENABLED": "true"}):
        manifest = await get_manifest()
        
        assert "agent" in manifest
        assert "version" in manifest
        assert "skills" in manifest
        assert "capabilities" in manifest
        assert "endpoints" in manifest
        
        assert manifest["agent"] == "quality-agent"
        assert len(manifest["skills"]) > 0
        
        # Check skill structure
        for skill in manifest["skills"]:
            assert "name" in skill
            assert "description" in skill
            assert "parameters" in skill
            assert "returns" in skill


@pytest.mark.asyncio
async def test_a2a_manifest_disabled():
    """Test A2A manifest when disabled."""
    from apps.a2a.api import get_manifest
    from fastapi import HTTPException
    
    with patch.dict(os.environ, {"A2A_ENABLED": "false"}):
        with pytest.raises(HTTPException) as exc_info:
            await get_manifest()
        
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_a2a_act_ask_rag():
    """Test A2A act endpoint with ask_rag skill."""
    from apps.a2a.api import _execute_ask_rag
    
    args = {
        "query": "What is AI?",
        "provider": "mock",
        "model": "mock-model"
    }
    
    with patch('apps.a2a.api.ask_rag') as mock_ask_rag:
        mock_ask_rag.return_value = {
            "answer": "AI is artificial intelligence",
            "context": ["context"],
            "provider": "mock",
            "model": "mock-model"
        }
        
        result = await _execute_ask_rag(args)
        
        assert result["answer"] == "AI is artificial intelligence"
        mock_ask_rag.assert_called_once_with("What is AI?", "mock", "mock-model")


@pytest.mark.asyncio
async def test_a2a_act_missing_query():
    """Test A2A act with missing required parameter."""
    from apps.a2a.api import _execute_ask_rag
    from fastapi import HTTPException
    
    args = {"provider": "mock"}  # Missing query
    
    with pytest.raises(HTTPException) as exc_info:
        await _execute_ask_rag(args)
    
    assert exc_info.value.status_code == 400
    assert "query parameter is required" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_a2a_act_eval_rag():
    """Test A2A act endpoint with eval_rag skill."""
    from apps.a2a.api import _execute_eval_rag
    
    args = {
        "query": "What is AI?",
        "answer": "AI is artificial intelligence"
    }
    
    with patch('apps.a2a.api.eval_rag') as mock_eval_rag:
        mock_eval_rag.return_value = {
            "faithfulness": 0.8,
            "context_recall": 0.7,
            "notes": "Good answer"
        }
        
        result = await _execute_eval_rag(args)
        
        assert result["faithfulness"] == 0.8
        assert result["context_recall"] == 0.7
        mock_eval_rag.assert_called_once_with("What is AI?", "AI is artificial intelligence", None, None)


@pytest.mark.asyncio
async def test_a2a_act_run_tests():
    """Test A2A act endpoint with run_tests skill."""
    from apps.a2a.api import _execute_run_tests
    
    args = {
        "config": {
            "suites": ["rag_quality"],
            "provider": "mock"
        }
    }
    
    with patch('apps.a2a.api.run_tests') as mock_run_tests:
        mock_run_tests.return_value = {
            "run_id": "test_run_123",
            "summary": {"overall": {"pass_rate": 0.8}},
            "counts": {"total_tests": 5}
        }
        
        result = await _execute_run_tests(args)
        
        assert result["run_id"] == "test_run_123"
        mock_run_tests.assert_called_once_with(args["config"])


@pytest.mark.asyncio
async def test_a2a_act_list_tests():
    """Test A2A act endpoint with list_tests skill."""
    from apps.a2a.api import _execute_list_tests
    
    args = {}
    
    with patch('apps.a2a.api.list_tests') as mock_list_tests:
        mock_list_tests.return_value = {
            "suites": [{"name": "rag_quality", "test_count": 8}],
            "total_suites": 1
        }
        
        result = await _execute_list_tests(args)
        
        assert result["total_suites"] == 1
        mock_list_tests.assert_called_once()


def test_mcp_error_handling():
    """Test MCP error handling."""
    from apps.mcp.server import ask_rag
    
    with patch.dict(os.environ, {"MCP_ENABLED": "true", "OFFLINE_MODE": "false"}):
        with patch('apps.mcp.server.resolve_provider_and_model', side_effect=Exception("Test error")):
            result = ask_rag("What is AI?")
            
            assert "error" in result
            assert result["source"] == "error"
            assert "Test error" in result["error"]


@pytest.mark.asyncio
async def test_a2a_error_handling():
    """Test A2A error handling."""
    from apps.a2a.api import _execute_ask_rag
    from fastapi import HTTPException
    
    args = {"query": "What is AI?"}
    
    with patch('apps.a2a.api.ask_rag', side_effect=Exception("Test error")):
        with pytest.raises(HTTPException) as exc_info:
            await _execute_ask_rag(args)
        
        assert exc_info.value.status_code == 500
        assert "Skill execution failed" in str(exc_info.value.detail)


def test_mcp_server_start():
    """Test MCP server start functionality."""
    from apps.mcp.server import start_mcp_server
    
    # Should not crash when called
    with patch.dict(os.environ, {"MCP_ENABLED": "true"}):
        start_mcp_server()  # Should print message but not crash
    
    with patch.dict(os.environ, {"MCP_ENABLED": "false"}):
        start_mcp_server()  # Should print disabled message


def test_mcp_offline_mode():
    """Test MCP offline mode behavior."""
    from apps.mcp.server import ask_rag
    
    with patch.dict(os.environ, {"MCP_ENABLED": "true", "OFFLINE_MODE": "true"}):
        result = ask_rag("Test query", "mock", "mock-model")
        
        assert result["source"] == "mcp_mock"
        assert "Mock MCP response" in result["answer"]
        assert result["provider"] == "mock"
        assert result["model"] == "mock-model"
