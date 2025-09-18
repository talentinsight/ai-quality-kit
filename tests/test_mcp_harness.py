"""Comprehensive tests for MCP production harness."""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import asdict

from apps.orchestrator.mcp_harness import (
    MCPHarness, MCPSession, MCPStep, StepDecision, Channel, PolicyConfig,
    is_mcp_harness_available, get_mcp_harness_version
)
from apps.orchestrator.mcp_client import MCPClient, MCPTool, MCPResult
from apps.server.guardrails.interfaces import SignalResult, SignalLabel, GuardrailCategory


@pytest.fixture
def mock_mcp_client():
    """Mock MCP client for testing."""
    client = Mock(spec=MCPClient)
    client.endpoint = "ws://localhost:8080/mcp"
    client.connect = AsyncMock()
    client.list_tools = AsyncMock()
    client.call_tool = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def sample_tools():
    """Sample MCP tools for testing."""
    return [
        MCPTool(
            name="search_web",
            description="Search the web for information",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        ),
        MCPTool(
            name="calculate",
            description="Perform mathematical calculations",
            input_schema={
                "type": "object",
                "properties": {
                    "expression": {"type": "string"}
                },
                "required": ["expression"]
            }
        )
    ]


@pytest.fixture
def policy_config():
    """Sample policy configuration."""
    return PolicyConfig(
        allowlist=["search_web", "calculate"],
        no_network=False,
        dry_run=False,
        max_steps=5
    )


@pytest.fixture
def guardrails_config():
    """Sample guardrails configuration."""
    return {
        "mode": "mixed",
        "thresholds": {
            "toxicity": 0.3,
            "pii": 0.0,
            "jailbreak": 0.15
        }
    }


@pytest.fixture
def mock_dedup_service():
    """Mock deduplication service."""
    service = Mock()
    service.create_fingerprint = Mock()
    service.check_signal_reusable = Mock(return_value=None)
    service.store_preflight_signal = Mock()
    return service


class TestMCPHarness:
    """Test MCP harness functionality."""

    @pytest.mark.asyncio
    async def test_start_session_success(self, mock_mcp_client, sample_tools, policy_config, guardrails_config):
        """Test successful session start with tool discovery."""
        mock_mcp_client.list_tools.return_value = sample_tools
        
        harness = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4",
            guardrails_config=guardrails_config,
            policy_config=policy_config
        )
        
        with patch.object(harness, '_run_preflight_checks', return_value={"pass": True}):
            session = await harness.start_session("test_session_1")
        
        assert session.session_id == "test_session_1"
        assert session.model == "gpt-4"
        assert len(session.tools_discovered) == 2
        assert session.tools_discovered[0].name == "search_web"
        assert session.preflight_result["pass"] is True
        
        mock_mcp_client.connect.assert_called_once()
        mock_mcp_client.list_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_step_tool_call_success(self, mock_mcp_client, sample_tools, policy_config):
        """Test successful tool execution step."""
        mock_mcp_client.list_tools.return_value = sample_tools
        mock_mcp_client.call_tool.return_value = MCPResult(
            raw={"answer": "The weather is sunny"},
            text="The weather is sunny",
            meta={"model": "gpt-4"}
        )
        
        harness = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4",
            policy_config=policy_config
        )
        
        session = MCPSession(
            session_id="test_session",
            model="gpt-4",
            rules_hash="test_hash",
            steps=[],
            tools_discovered=sample_tools
        )
        
        step = await harness.execute_step(
            session=session,
            role="assistant",
            input_text="What's the weather?",
            tool_name="search_web",
            tool_args={"query": "weather today"}
        )
        
        assert step.decision == StepDecision.OK
        assert step.selected_tool == "search_web"
        assert step.channel == Channel.LLM_TO_TOOL
        assert step.tokens_in > 0
        assert step.tokens_out > 0
        assert step.cost_est > 0
        assert step.latency_ms > 0
        
        mock_mcp_client.call_tool.assert_called_once_with("search_web", {"query": "weather today"})

    @pytest.mark.asyncio
    async def test_execute_step_schema_guard_violation(self, mock_mcp_client, sample_tools, policy_config):
        """Test step execution with schema validation failure."""
        mock_mcp_client.list_tools.return_value = sample_tools
        
        harness = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4",
            policy_config=policy_config
        )
        
        session = MCPSession(
            session_id="test_session",
            model="gpt-4",
            rules_hash="test_hash",
            steps=[],
            tools_discovered=sample_tools
        )
        
        # Missing required 'query' field
        with patch('jsonschema.validate', side_effect=Exception("Missing required field: query")):
            step = await harness.execute_step(
                session=session,
                role="assistant",
                input_text="Search something",
                tool_name="search_web",
                tool_args={"max_results": 10}  # Missing 'query'
            )
        
        assert step.decision == StepDecision.DENIED_SCHEMA
        assert "Schema validation failed" in step.error
        mock_mcp_client.call_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_step_policy_guard_allowlist(self, mock_mcp_client, sample_tools):
        """Test step execution blocked by policy allowlist."""
        mock_mcp_client.list_tools.return_value = sample_tools
        
        policy_config = PolicyConfig(
            allowlist=["calculate"],  # Only allow calculate, not search_web
            no_network=False,
            dry_run=False,
            max_steps=5
        )
        
        harness = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4",
            policy_config=policy_config
        )
        
        session = MCPSession(
            session_id="test_session",
            model="gpt-4",
            rules_hash="test_hash",
            steps=[],
            tools_discovered=sample_tools
        )
        
        step = await harness.execute_step(
            session=session,
            role="assistant",
            input_text="Search the web",
            tool_name="search_web",
            tool_args={"query": "test"}
        )
        
        assert step.decision == StepDecision.DENIED_POLICY
        assert "not in allowlist" in step.error
        mock_mcp_client.call_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_step_policy_guard_no_network(self, mock_mcp_client, sample_tools):
        """Test step execution blocked by no-network policy."""
        mock_mcp_client.list_tools.return_value = sample_tools
        
        policy_config = PolicyConfig(
            allowlist=["search_web"],
            no_network=True,  # Block network tools
            dry_run=False,
            max_steps=5
        )
        
        harness = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4",
            policy_config=policy_config
        )
        
        session = MCPSession(
            session_id="test_session",
            model="gpt-4",
            rules_hash="test_hash",
            steps=[],
            tools_discovered=sample_tools
        )
        
        step = await harness.execute_step(
            session=session,
            role="assistant",
            input_text="Search the web",
            tool_name="search_web",  # This is a network tool
            tool_args={"query": "test"}
        )
        
        assert step.decision == StepDecision.DENIED_POLICY
        assert "blocked by no-network policy" in step.error
        mock_mcp_client.call_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_step_dry_run_mode(self, mock_mcp_client, sample_tools):
        """Test step execution in dry-run mode."""
        mock_mcp_client.list_tools.return_value = sample_tools
        
        policy_config = PolicyConfig(
            allowlist=["search_web"],
            no_network=False,
            dry_run=True,  # Dry run mode
            max_steps=5
        )
        
        harness = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4",
            policy_config=policy_config
        )
        
        session = MCPSession(
            session_id="test_session",
            model="gpt-4",
            rules_hash="test_hash",
            steps=[],
            tools_discovered=sample_tools
        )
        
        step = await harness.execute_step(
            session=session,
            role="assistant",
            input_text="Search the web",
            tool_name="search_web",
            tool_args={"query": "test"}
        )
        
        assert step.decision == StepDecision.OK
        assert "[DRY RUN]" in step.output_text
        assert step.tokens_in > 0
        assert step.tokens_out == 5  # Simulated tokens
        mock_mcp_client.call_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_step_max_steps_exceeded(self, mock_mcp_client, sample_tools):
        """Test step execution blocked by max steps limit."""
        policy_config = PolicyConfig(max_steps=2)
        
        harness = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4",
            policy_config=policy_config
        )
        
        session = MCPSession(
            session_id="test_session",
            model="gpt-4",
            rules_hash="test_hash",
            steps=[Mock(), Mock()],  # Already at max steps
            tools_discovered=sample_tools
        )
        
        step = await harness.execute_step(
            session=session,
            role="user",
            input_text="Another step"
        )
        
        assert step.decision == StepDecision.DENIED_POLICY
        assert "Max steps exceeded" in step.error

    @pytest.mark.asyncio
    async def test_execute_step_with_guardrails_reuse(self, mock_mcp_client, sample_tools, mock_dedup_service):
        """Test step execution with guardrails signal reuse."""
        mock_mcp_client.list_tools.return_value = sample_tools
        mock_mcp_client.call_tool.return_value = MCPResult(
            raw={"answer": "Clean response"},
            text="Clean response"
        )
        
        # Mock reused signal
        reused_signal = SignalResult(
            id="toxicity.guard",
            category=GuardrailCategory.TOXICITY,
            score=0.1,
            label=SignalLabel.CLEAN,
            confidence=0.9,
            details={"reused": True}
        )
        mock_dedup_service.check_signal_reusable.return_value = reused_signal
        
        harness = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4",
            guardrails_config={"mode": "advisory"},
            dedup_service=mock_dedup_service
        )
        
        session = MCPSession(
            session_id="test_session",
            model="gpt-4",
            rules_hash="test_hash",
            steps=[],
            tools_discovered=sample_tools
        )
        
        step = await harness.execute_step(
            session=session,
            role="assistant",
            input_text="Generate response",
            tool_name="search_web",
            tool_args={"query": "test"}
        )
        
        assert step.decision == StepDecision.OK
        assert len(step.guardrail_signals) > 0
        assert len(step.reused_fingerprints) > 0

    @pytest.mark.asyncio
    async def test_close_session(self, mock_mcp_client, sample_tools):
        """Test session closure and cleanup."""
        harness = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4"
        )
        
        session = MCPSession(
            session_id="test_session",
            model="gpt-4",
            rules_hash="test_hash",
            steps=[Mock(), Mock()],  # 2 steps
            tools_discovered=sample_tools,
            total_latency_ms=1500.0,
            total_tokens_in=100,
            total_tokens_out=200,
            total_cost_est=0.05
        )
        
        await harness.close_session(session)
        
        mock_mcp_client.close.assert_called_once()

    def test_determine_channel(self, mock_mcp_client):
        """Test channel determination logic."""
        harness = MCPHarness(mock_mcp_client, "gpt-4")
        
        assert harness._determine_channel("user", None) == Channel.USER_TO_LLM
        assert harness._determine_channel("assistant", "search_web") == Channel.LLM_TO_TOOL
        assert harness._determine_channel("assistant", None) == Channel.TOOL_TO_LLM

    def test_redact_tool_args(self, mock_mcp_client):
        """Test tool arguments redaction for privacy."""
        harness = MCPHarness(mock_mcp_client, "gpt-4")
        
        args = {
            "query": "What is the weather?",
            "api_key": "secret123",
            "long_text": "a" * 150,
            "normal_field": "value"
        }
        
        redacted = harness._redact_tool_args(args)
        
        assert redacted["query"] == "What is the weather?"
        assert redacted["api_key"] == "***REDACTED***"
        assert len(redacted["long_text"]) < len(args["long_text"])
        assert "..." in redacted["long_text"]
        assert redacted["normal_field"] == "value"

    def test_is_sensitive_key(self, mock_mcp_client):
        """Test sensitive key detection."""
        harness = MCPHarness(mock_mcp_client, "gpt-4")
        
        assert harness._is_sensitive_key("api_key") is True
        assert harness._is_sensitive_key("bearer_token") is True
        assert harness._is_sensitive_key("password") is True
        assert harness._is_sensitive_key("secret") is True
        assert harness._is_sensitive_key("query") is False
        assert harness._is_sensitive_key("normal_field") is False

    def test_is_network_tool(self, mock_mcp_client):
        """Test network tool detection heuristics."""
        harness = MCPHarness(mock_mcp_client, "gpt-4")
        
        # Tool name indicators
        assert harness._is_network_tool("fetch_url", {}) is True
        assert harness._is_network_tool("web_search", {}) is True
        assert harness._is_network_tool("api_call", {}) is True
        assert harness._is_network_tool("calculate", {}) is False
        
        # Argument indicators
        assert harness._is_network_tool("tool", {"url": "http://example.com"}) is True
        assert harness._is_network_tool("tool", {"endpoint": "api.service.com"}) is True
        assert harness._is_network_tool("tool", {"query": "search term"}) is False

    def test_estimate_cost(self, mock_mcp_client):
        """Test cost estimation logic."""
        harness = MCPHarness(mock_mcp_client, "gpt-4")
        
        cost = harness._estimate_cost(1000, 500)  # 1K input, 500 output tokens
        
        expected = (1000 / 1000 * 0.001) + (500 / 1000 * 0.002)  # $0.001 + $0.001 = $0.002
        assert abs(cost - expected) < 0.0001

    @pytest.mark.asyncio
    async def test_run_preflight_checks_success(self, mock_mcp_client):
        """Test successful preflight checks."""
        harness = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4",
            guardrails_config={"mode": "advisory", "thresholds": {"toxicity": 0.3}}
        )
        
        session = MCPSession(
            session_id="test_session",
            model="gpt-4",
            rules_hash="test_hash",
            steps=[],
            tools_discovered=[]
        )
        
        # Mock the aggregator and its result
        mock_result = Mock()
        mock_result.pass_ = True
        mock_result.signals = []
        mock_result.metrics = {"tests": 1, "duration_ms": 100}
        
        with patch('apps.orchestrator.mcp_harness.GuardrailsAggregator') as mock_aggregator_class:
            mock_aggregator = Mock()
            mock_aggregator.run_preflight = AsyncMock(return_value=mock_result)
            mock_aggregator_class.return_value = mock_aggregator
            
            result = await harness._run_preflight_checks(session)
        
        assert result["pass"] is True
        assert "signals" in result
        assert "metrics" in result

    @pytest.mark.asyncio
    async def test_run_preflight_checks_failure(self, mock_mcp_client):
        """Test preflight checks with failure."""
        harness = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4",
            guardrails_config={"mode": "hard_gate", "thresholds": {"toxicity": 0.1}}
        )
        
        session = MCPSession(
            session_id="test_session",
            model="gpt-4",
            rules_hash="test_hash",
            steps=[],
            tools_discovered=[]
        )
        
        with patch('apps.orchestrator.mcp_harness.GuardrailsAggregator', side_effect=Exception("Preflight failed")):
            result = await harness._run_preflight_checks(session)
        
        assert result["pass"] is False
        assert "error" in result

    def test_create_rules_hash(self, mock_mcp_client):
        """Test rules hash creation for deduplication."""
        harness1 = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4",
            guardrails_config={"mode": "advisory"},
            policy_config=PolicyConfig(allowlist=["tool1"])
        )
        
        harness2 = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4",
            guardrails_config={"mode": "advisory"},
            policy_config=PolicyConfig(allowlist=["tool1"])
        )
        
        harness3 = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4",
            guardrails_config={"mode": "hard_gate"},  # Different config
            policy_config=PolicyConfig(allowlist=["tool1"])
        )
        
        # Same configuration should produce same hash
        assert harness1.rules_hash == harness2.rules_hash
        
        # Different configuration should produce different hash
        assert harness1.rules_hash != harness3.rules_hash


class TestMCPHarnessHealthChecks:
    """Test MCP harness health check functions."""

    def test_is_mcp_harness_available_with_websockets(self):
        """Test availability check when websockets is available."""
        with patch('builtins.__import__', return_value=Mock()):
            assert is_mcp_harness_available() is True

    def test_is_mcp_harness_available_without_websockets(self):
        """Test availability check when websockets is not available."""
        with patch('builtins.__import__', side_effect=ImportError("No module named 'websockets'")):
            assert is_mcp_harness_available() is False

    def test_get_mcp_harness_version(self):
        """Test version retrieval."""
        version = get_mcp_harness_version()
        assert version == "1.0.0"


class TestMCPDataStructures:
    """Test MCP data structures and serialization."""

    def test_mcp_step_serialization(self):
        """Test MCPStep can be serialized to dict."""
        step = MCPStep(
            step_id="step_1",
            role="assistant",
            input_text="Test input",
            selected_tool="search_web",
            tool_args={"query": "test"},
            output_text="Test output",
            decision=StepDecision.OK,
            channel=Channel.LLM_TO_TOOL,
            latency_ms=150.5,
            tokens_in=10,
            tokens_out=20,
            cost_est=0.001
        )
        
        step_dict = asdict(step)
        
        assert step_dict["step_id"] == "step_1"
        assert step_dict["role"] == "assistant"
        assert step_dict["decision"] == "ok"
        assert step_dict["channel"] == "llm_to_tool"
        assert step_dict["latency_ms"] == 150.5

    def test_mcp_session_serialization(self):
        """Test MCPSession can be serialized to dict."""
        session = MCPSession(
            session_id="session_1",
            model="gpt-4",
            rules_hash="abc123",
            steps=[],
            tools_discovered=[],
            total_latency_ms=500.0,
            total_tokens_in=50,
            total_tokens_out=100,
            total_cost_est=0.01
        )
        
        session_dict = asdict(session)
        
        assert session_dict["session_id"] == "session_1"
        assert session_dict["model"] == "gpt-4"
        assert session_dict["total_latency_ms"] == 500.0

    def test_policy_config_defaults(self):
        """Test PolicyConfig default values."""
        config = PolicyConfig()
        
        assert config.allowlist == []
        assert config.no_network is False
        assert config.dry_run is False
        assert config.max_steps == 10


class TestMCPIntegrationScenarios:
    """Test realistic MCP integration scenarios."""

    @pytest.mark.asyncio
    async def test_multi_step_conversation_scenario(self, mock_mcp_client, sample_tools):
        """Test a realistic multi-step conversation with tool calls."""
        mock_mcp_client.list_tools.return_value = sample_tools
        
        # Mock different tool responses
        def mock_call_tool(tool_name, args):
            if tool_name == "search_web":
                return MCPResult(
                    raw={"results": ["Weather is sunny"]},
                    text="Weather is sunny today"
                )
            elif tool_name == "calculate":
                return MCPResult(
                    raw={"result": 42},
                    text="The answer is 42"
                )
            return MCPResult(raw={}, error="Unknown tool")
        
        mock_mcp_client.call_tool.side_effect = mock_call_tool
        
        harness = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4",
            policy_config=PolicyConfig(allowlist=["search_web", "calculate"])
        )
        
        # Start session
        with patch.object(harness, '_run_preflight_checks', return_value={"pass": True}):
            session = await harness.start_session("multi_step_test")
        
        # Step 1: User asks about weather
        step1 = await harness.execute_step(
            session=session,
            role="user",
            input_text="What's the weather like today?"
        )
        session.steps.append(step1)
        
        # Step 2: Assistant calls search tool
        step2 = await harness.execute_step(
            session=session,
            role="assistant",
            input_text="I'll search for weather information",
            tool_name="search_web",
            tool_args={"query": "weather today"}
        )
        session.steps.append(step2)
        
        # Step 3: User asks for calculation
        step3 = await harness.execute_step(
            session=session,
            role="user",
            input_text="What's 6 times 7?"
        )
        session.steps.append(step3)
        
        # Step 4: Assistant calls calculate tool
        step4 = await harness.execute_step(
            session=session,
            role="assistant",
            input_text="I'll calculate that for you",
            tool_name="calculate",
            tool_args={"expression": "6 * 7"}
        )
        session.steps.append(step4)
        
        # Verify session state
        assert len(session.steps) == 4
        assert step1.decision == StepDecision.OK
        assert step2.decision == StepDecision.OK
        assert step2.selected_tool == "search_web"
        assert step3.decision == StepDecision.OK
        assert step4.decision == StepDecision.OK
        assert step4.selected_tool == "calculate"
        
        # Verify metrics accumulation
        assert session.total_latency_ms > 0
        assert session.total_tokens_in > 0
        assert session.total_tokens_out > 0
        assert session.total_cost_est > 0
        
        # Close session
        await harness.close_session(session)

    @pytest.mark.asyncio
    async def test_guardrails_enforcement_scenario(self, mock_mcp_client, sample_tools):
        """Test guardrails enforcement during MCP session."""
        mock_mcp_client.list_tools.return_value = sample_tools
        mock_mcp_client.call_tool.return_value = MCPResult(
            raw={"answer": "Toxic response with bad words"},
            text="Toxic response with bad words"
        )
        
        # Mock preflight failure
        def mock_preflight_fail(session):
            return {"pass": False, "error": "Toxicity threshold exceeded"}
        
        harness = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4",
            guardrails_config={"mode": "hard_gate", "thresholds": {"toxicity": 0.1}}
        )
        
        with patch.object(harness, '_run_preflight_checks', side_effect=mock_preflight_fail):
            session = await harness.start_session("guardrails_test")
        
        # Preflight should have failed
        assert session.preflight_result["pass"] is False
        
        # Step execution should still work (preflight is advisory for session start)
        step = await harness.execute_step(
            session=session,
            role="assistant",
            input_text="Generate response",
            tool_name="search_web",
            tool_args={"query": "test"}
        )
        
        # Step should succeed (per-step guardrails are separate)
        assert step.decision == StepDecision.OK
        
        await harness.close_session(session)

    @pytest.mark.asyncio
    async def test_error_handling_scenario(self, mock_mcp_client, sample_tools):
        """Test error handling in various failure scenarios."""
        mock_mcp_client.list_tools.return_value = sample_tools
        
        harness = MCPHarness(
            mcp_client=mock_mcp_client,
            model="gpt-4"
        )
        
        session = MCPSession(
            session_id="error_test",
            model="gpt-4",
            rules_hash="test_hash",
            steps=[],
            tools_discovered=sample_tools
        )
        
        # Test tool call failure
        mock_mcp_client.call_tool.return_value = MCPResult(
            raw={},
            error="Tool execution failed"
        )
        
        step = await harness.execute_step(
            session=session,
            role="assistant",
            input_text="Call failing tool",
            tool_name="search_web",
            tool_args={"query": "test"}
        )
        
        assert step.decision == StepDecision.ERROR
        assert "Tool execution failed" in step.error
        
        # Test exception during execution
        mock_mcp_client.call_tool.side_effect = Exception("Network error")
        
        step2 = await harness.execute_step(
            session=session,
            role="assistant",
            input_text="Call tool with exception",
            tool_name="search_web",
            tool_args={"query": "test"}
        )
        
        assert step2.decision == StepDecision.ERROR
        assert "Network error" in step2.error
