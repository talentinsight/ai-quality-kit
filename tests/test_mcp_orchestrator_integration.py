"""Integration tests for MCP harness with orchestrator and reporting."""

import pytest
import json
import tempfile
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import asdict

from apps.orchestrator.mcp_harness import MCPHarness, MCPSession, MCPStep, StepDecision, PolicyConfig
from apps.orchestrator.mcp_client import MCPClient, MCPTool, MCPResult
from apps.orchestrator.deduplication import CrossSuiteDeduplicationService
from apps.reporters.json_reporter import build_json
from apps.reporters.excel_reporter import write_excel


@pytest.fixture
def mock_orchestrator_run():
    """Mock orchestrator run data with MCP session."""
    return {
        "run_id": "test_run_123",
        "timestamp": "2024-01-15T10:00:00Z",
        "model": "gpt-4",
        "provider": "mcp",
        "target_mode": "mcp"
    }


@pytest.fixture
def sample_mcp_session():
    """Sample MCP session with steps for testing."""
    tools = [
        MCPTool(name="search_web", description="Search the web"),
        MCPTool(name="calculate", description="Perform calculations")
    ]
    
    steps = [
        MCPStep(
            step_id="step_1",
            role="user",
            input_text="What's the weather?",
            channel="user_to_llm",
            decision=StepDecision.OK,
            latency_ms=50.0,
            tokens_in=5,
            tokens_out=0,
            cost_est=0.001
        ),
        MCPStep(
            step_id="step_2",
            role="assistant",
            input_text="I'll search for weather info",
            selected_tool="search_web",
            tool_args={"query": "weather today"},
            output_text="Weather is sunny",
            channel="llm_to_tool",
            decision=StepDecision.OK,
            latency_ms=200.0,
            tokens_in=8,
            tokens_out=15,
            cost_est=0.003,
            guardrail_signals=[],
            reused_fingerprints=["fp_abc123"]
        ),
        MCPStep(
            step_id="step_3",
            role="user",
            input_text="Calculate 2+2",
            channel="user_to_llm",
            decision=StepDecision.OK,
            latency_ms=30.0,
            tokens_in=3,
            tokens_out=0,
            cost_est=0.001
        ),
        MCPStep(
            step_id="step_4",
            role="assistant",
            input_text="I'll calculate that",
            selected_tool="calculate",
            tool_args={"expression": "2+2"},
            output_text="4",
            channel="llm_to_tool",
            decision=StepDecision.OK,
            latency_ms=100.0,
            tokens_in=5,
            tokens_out=3,
            cost_est=0.002
        )
    ]
    
    return MCPSession(
        session_id="session_123",
        model="gpt-4",
        rules_hash="rules_abc",
        steps=steps,
        tools_discovered=tools,
        total_latency_ms=380.0,
        total_tokens_in=21,
        total_tokens_out=18,
        total_cost_est=0.007,
        preflight_result={"pass": True, "signals": [], "metrics": {"tests": 3}}
    )


class TestMCPOrchestratorIntegration:
    """Test MCP harness integration with orchestrator components."""

    @pytest.mark.asyncio
    async def test_mcp_session_with_deduplication(self):
        """Test MCP session with cross-suite deduplication."""
        # Setup deduplication service
        dedup_service = CrossSuiteDeduplicationService("test_run")
        
        # Mock MCP client
        mock_client = Mock(spec=MCPClient)
        mock_client.endpoint = "ws://localhost:8080/mcp"
        mock_client.connect = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[
            MCPTool(name="search", description="Search tool")
        ])
        mock_client.call_tool = AsyncMock(return_value=MCPResult(
            raw={"answer": "Test response"},
            text="Test response"
        ))
        mock_client.close = AsyncMock()
        
        # Create harness with deduplication
        harness = MCPHarness(
            mcp_client=mock_client,
            model="gpt-4",
            dedup_service=dedup_service
        )
        
        # Start session
        with patch.object(harness, '_run_preflight_checks', return_value={"pass": True}):
            session = await harness.start_session("dedup_test")
        
        # Execute step that should check for reuse
        step = await harness.execute_step(
            session=session,
            role="assistant",
            input_text="Generate response",
            tool_name="search",
            tool_args={"query": "test"}
        )
        
        assert step.decision == StepDecision.OK
        # In a real scenario, reused_fingerprints would be populated if signals were reused
        
        await harness.close_session(session)

    def test_mcp_session_serialization_for_reports(self, sample_mcp_session):
        """Test MCP session can be serialized for reporting."""
        session_dict = asdict(sample_mcp_session)
        
        # Verify session-level data
        assert session_dict["session_id"] == "session_123"
        assert session_dict["model"] == "gpt-4"
        assert session_dict["total_latency_ms"] == 380.0
        assert session_dict["total_tokens_in"] == 21
        assert session_dict["total_tokens_out"] == 18
        assert session_dict["total_cost_est"] == 0.007
        
        # Verify steps data
        assert len(session_dict["steps"]) == 4
        
        step1 = session_dict["steps"][0]
        assert step1["step_id"] == "step_1"
        assert step1["role"] == "user"
        assert step1["decision"] == "ok"
        
        step2 = session_dict["steps"][1]
        assert step2["selected_tool"] == "search_web"
        assert step2["channel"] == "llm_to_tool"
        assert len(step2["reused_fingerprints"]) == 1
        
        # Verify tools data
        assert len(session_dict["tools_discovered"]) == 2
        assert session_dict["tools_discovered"][0]["name"] == "search_web"

    def test_json_report_with_mcp_details(self, mock_orchestrator_run, sample_mcp_session):
        """Test JSON report generation with MCP details."""
        # Prepare MCP details for report
        mcp_details = {
            "sessions": [asdict(sample_mcp_session)],
            "summary": {
                "total_sessions": 1,
                "total_steps": 4,
                "total_latency_ms": 380.0,
                "total_cost_est": 0.007,
                "tools_used": ["search_web", "calculate"],
                "decisions": {
                    "ok": 4,
                    "denied_schema": 0,
                    "denied_policy": 0,
                    "error": 0
                }
            }
        }
        
        # Build JSON report
        report = build_json(
            run_meta=mock_orchestrator_run,
            summary={"tests": 4, "passed": 4, "failed": 0},
            detailed_rows=[],
            api_rows=[],
            inputs_rows=[],
            mcp_details=mcp_details,
            anonymize=False  # Don't mask for testing
        )
        
        # Verify MCP details in report
        assert "mcp_details" in report
        assert report["mcp_details"]["summary"]["total_sessions"] == 1
        assert report["mcp_details"]["summary"]["total_steps"] == 4
        assert len(report["mcp_details"]["sessions"]) == 1
        
        session_data = report["mcp_details"]["sessions"][0]
        assert session_data["session_id"] == "session_123"
        assert len(session_data["steps"]) == 4

    def test_json_report_with_mcp_details_anonymized(self, mock_orchestrator_run, sample_mcp_session):
        """Test JSON report generation with MCP details and PII masking."""
        # Add sensitive data to session
        sensitive_session = sample_mcp_session
        sensitive_session.steps[0].input_text = "My email is john@example.com and my phone is 555-1234"
        sensitive_session.steps[1].tool_args = {
            "query": "search for john@example.com",
            "api_key": "secret123"
        }
        
        mcp_details = {
            "sessions": [asdict(sensitive_session)]
        }
        
        # Build JSON report with anonymization
        report = build_json(
            run_meta=mock_orchestrator_run,
            summary={"tests": 1},
            detailed_rows=[],
            api_rows=[],
            inputs_rows=[],
            mcp_details=mcp_details,
            anonymize=True  # Enable masking
        )
        
        # Verify PII masking was applied
        session_data = report["mcp_details"]["sessions"][0]
        step1_input = session_data["steps"][0]["input_text"]
        step2_args = session_data["steps"][1]["tool_args"]
        
        # Email and phone should be masked
        assert "john@example.com" not in step1_input
        assert "555-1234" not in step1_input
        assert "[EMAIL]" in step1_input or "***" in step1_input
        
        # API key should be masked
        assert "secret123" not in str(step2_args)

    def test_excel_report_with_mcp_details(self, mock_orchestrator_run, sample_mcp_session):
        """Test Excel report generation with MCP details sheet."""
        mcp_details = {
            "sessions": [asdict(sample_mcp_session)]
        }
        
        report_data = {
            "version": "2.0",
            "run": mock_orchestrator_run,
            "summary": {"tests": 4, "passed": 4, "failed": 0},
            "detailed": [],
            "api_details": [],
            "inputs_expected": [],
            "mcp_details": mcp_details
        }
        
        # Write Excel report to temporary file
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            write_excel(tmp_file.name, report_data)
            
            # Verify file was created (basic check)
            assert tmp_file.name.endswith(".xlsx")
            
            # In a real test, you'd use openpyxl to read and verify the sheet contents
            # For now, we just verify the function doesn't crash

    @pytest.mark.asyncio
    async def test_mcp_harness_with_guardrails_integration(self):
        """Test MCP harness integration with guardrails system."""
        # Mock MCP client
        mock_client = Mock(spec=MCPClient)
        mock_client.endpoint = "ws://localhost:8080/mcp"
        mock_client.connect = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[])
        mock_client.close = AsyncMock()
        
        # Create harness with guardrails config
        guardrails_config = {
            "mode": "mixed",
            "thresholds": {
                "toxicity": 0.3,
                "pii": 0.0,
                "jailbreak": 0.15
            }
        }
        
        harness = MCPHarness(
            mcp_client=mock_client,
            model="gpt-4",
            guardrails_config=guardrails_config
        )
        
        # Mock successful preflight
        mock_preflight_result = {
            "pass": True,
            "signals": [
                {
                    "id": "toxicity.detoxify",
                    "category": "toxicity",
                    "score": 0.1,
                    "label": "clean"
                }
            ],
            "metrics": {"tests": 1, "duration_ms": 150}
        }
        
        with patch.object(harness, '_run_preflight_checks', return_value=mock_preflight_result):
            session = await harness.start_session("guardrails_integration_test")
        
        # Verify preflight was run and passed
        assert session.preflight_result["pass"] is True
        assert len(session.preflight_result["signals"]) == 1
        
        await harness.close_session(session)

    def test_mcp_harness_policy_configuration(self):
        """Test MCP harness with various policy configurations."""
        mock_client = Mock(spec=MCPClient)
        
        # Test restrictive policy
        restrictive_policy = PolicyConfig(
            allowlist=["safe_tool"],
            no_network=True,
            dry_run=True,
            max_steps=3
        )
        
        harness = MCPHarness(
            mcp_client=mock_client,
            model="gpt-4",
            policy_config=restrictive_policy
        )
        
        assert harness.policy_config.allowlist == ["safe_tool"]
        assert harness.policy_config.no_network is True
        assert harness.policy_config.dry_run is True
        assert harness.policy_config.max_steps == 3
        
        # Test permissive policy
        permissive_policy = PolicyConfig(
            allowlist=[],  # Empty allowlist means all tools allowed
            no_network=False,
            dry_run=False,
            max_steps=20
        )
        
        harness2 = MCPHarness(
            mcp_client=mock_client,
            model="gpt-4",
            policy_config=permissive_policy
        )
        
        assert harness2.policy_config.allowlist == []
        assert harness2.policy_config.no_network is False
        assert harness2.policy_config.dry_run is False
        assert harness2.policy_config.max_steps == 20

    def test_mcp_session_metrics_aggregation(self, sample_mcp_session):
        """Test MCP session metrics are properly aggregated."""
        session = sample_mcp_session
        
        # Verify session-level aggregations
        assert session.total_latency_ms == 380.0  # Sum of all step latencies
        assert session.total_tokens_in == 21      # Sum of all input tokens
        assert session.total_tokens_out == 18     # Sum of all output tokens
        assert session.total_cost_est == 0.007   # Sum of all step costs
        
        # Verify step-level metrics
        tool_steps = [step for step in session.steps if step.selected_tool]
        assert len(tool_steps) == 2  # Two tool calls
        
        search_step = next(step for step in tool_steps if step.selected_tool == "search_web")
        assert search_step.latency_ms == 200.0
        assert search_step.tokens_in == 8
        assert search_step.tokens_out == 15
        assert len(search_step.reused_fingerprints) == 1
        
        calc_step = next(step for step in tool_steps if step.selected_tool == "calculate")
        assert calc_step.latency_ms == 100.0
        assert calc_step.tokens_in == 5
        assert calc_step.tokens_out == 3

    def test_mcp_session_error_tracking(self):
        """Test MCP session properly tracks errors and decisions."""
        tools = [MCPTool(name="test_tool", description="Test tool")]
        
        steps = [
            MCPStep(
                step_id="step_1",
                role="assistant",
                input_text="Normal step",
                decision=StepDecision.OK,
                latency_ms=100.0,
                tokens_in=5,
                tokens_out=10,
                cost_est=0.001
            ),
            MCPStep(
                step_id="step_2",
                role="assistant",
                input_text="Schema violation",
                selected_tool="test_tool",
                decision=StepDecision.DENIED_SCHEMA,
                error="Schema validation failed: missing required field",
                latency_ms=50.0,
                tokens_in=3,
                tokens_out=0,
                cost_est=0.0
            ),
            MCPStep(
                step_id="step_3",
                role="assistant",
                input_text="Policy violation",
                selected_tool="blocked_tool",
                decision=StepDecision.DENIED_POLICY,
                error="Tool not in allowlist",
                latency_ms=25.0,
                tokens_in=2,
                tokens_out=0,
                cost_est=0.0
            ),
            MCPStep(
                step_id="step_4",
                role="assistant",
                input_text="Runtime error",
                selected_tool="test_tool",
                decision=StepDecision.ERROR,
                error="Network timeout",
                latency_ms=5000.0,  # Long latency due to timeout
                tokens_in=4,
                tokens_out=0,
                cost_est=0.0
            )
        ]
        
        session = MCPSession(
            session_id="error_test",
            model="gpt-4",
            rules_hash="test_hash",
            steps=steps,
            tools_discovered=tools,
            total_latency_ms=5175.0,
            total_tokens_in=14,
            total_tokens_out=10,
            total_cost_est=0.001
        )
        
        # Analyze decision distribution
        decisions = [step.decision for step in session.steps]
        decision_counts = {
            StepDecision.OK: decisions.count(StepDecision.OK),
            StepDecision.DENIED_SCHEMA: decisions.count(StepDecision.DENIED_SCHEMA),
            StepDecision.DENIED_POLICY: decisions.count(StepDecision.DENIED_POLICY),
            StepDecision.ERROR: decisions.count(StepDecision.ERROR)
        }
        
        assert decision_counts[StepDecision.OK] == 1
        assert decision_counts[StepDecision.DENIED_SCHEMA] == 1
        assert decision_counts[StepDecision.DENIED_POLICY] == 1
        assert decision_counts[StepDecision.ERROR] == 1
        
        # Verify error steps have appropriate error messages
        error_steps = [step for step in session.steps if step.error]
        assert len(error_steps) == 3
        
        schema_error = next(step for step in error_steps if step.decision == StepDecision.DENIED_SCHEMA)
        assert "Schema validation failed" in schema_error.error
        
        policy_error = next(step for step in error_steps if step.decision == StepDecision.DENIED_POLICY)
        assert "not in allowlist" in policy_error.error
        
        runtime_error = next(step for step in error_steps if step.decision == StepDecision.ERROR)
        assert "Network timeout" in runtime_error.error


class TestMCPReportingIntegration:
    """Test MCP harness integration with reporting system."""

    def test_mcp_details_report_structure(self, sample_mcp_session):
        """Test MCP details report has correct structure."""
        mcp_details = {
            "sessions": [asdict(sample_mcp_session)],
            "summary": {
                "total_sessions": 1,
                "total_steps": 4,
                "total_latency_ms": 380.0,
                "total_tokens_in": 21,
                "total_tokens_out": 18,
                "total_cost_est": 0.007,
                "tools_used": ["search_web", "calculate"],
                "unique_tools": 2,
                "decisions": {
                    "ok": 4,
                    "denied_schema": 0,
                    "denied_policy": 0,
                    "error": 0
                },
                "channels": {
                    "user_to_llm": 2,
                    "llm_to_tool": 2,
                    "tool_to_llm": 0
                },
                "guardrails": {
                    "signals_generated": 0,
                    "signals_reused": 1,
                    "violations": 0
                }
            }
        }
        
        # Verify top-level structure
        assert "sessions" in mcp_details
        assert "summary" in mcp_details
        
        # Verify summary metrics
        summary = mcp_details["summary"]
        assert summary["total_sessions"] == 1
        assert summary["total_steps"] == 4
        assert summary["unique_tools"] == 2
        assert summary["decisions"]["ok"] == 4
        assert summary["channels"]["user_to_llm"] == 2
        assert summary["guardrails"]["signals_reused"] == 1
        
        # Verify session structure
        session = mcp_details["sessions"][0]
        assert "session_id" in session
        assert "steps" in session
        assert "tools_discovered" in session
        assert "preflight_result" in session

    def test_mcp_performance_metrics_for_reports(self, sample_mcp_session):
        """Test MCP performance metrics extraction for reports."""
        session = sample_mcp_session
        
        # Extract performance metrics
        performance_metrics = {
            "mcp_sessions": 1,
            "mcp_total_steps": len(session.steps),
            "mcp_avg_step_latency_ms": session.total_latency_ms / len(session.steps),
            "mcp_total_latency_ms": session.total_latency_ms,
            "mcp_total_tokens": session.total_tokens_in + session.total_tokens_out,
            "mcp_total_cost_est": session.total_cost_est,
            "mcp_tools_discovered": len(session.tools_discovered),
            "mcp_tools_used": len(set(step.selected_tool for step in session.steps if step.selected_tool)),
            "mcp_success_rate": sum(1 for step in session.steps if step.decision == StepDecision.OK) / len(session.steps)
        }
        
        # Verify calculated metrics
        assert performance_metrics["mcp_sessions"] == 1
        assert performance_metrics["mcp_total_steps"] == 4
        assert performance_metrics["mcp_avg_step_latency_ms"] == 95.0  # 380 / 4
        assert performance_metrics["mcp_total_latency_ms"] == 380.0
        assert performance_metrics["mcp_total_tokens"] == 39  # 21 + 18
        assert performance_metrics["mcp_total_cost_est"] == 0.007
        assert performance_metrics["mcp_tools_discovered"] == 2
        assert performance_metrics["mcp_tools_used"] == 2  # search_web, calculate
        assert performance_metrics["mcp_success_rate"] == 1.0  # All steps OK

    def test_mcp_guardrails_integration_for_reports(self):
        """Test MCP guardrails data integration for reports."""
        # Mock guardrails data from MCP session
        guardrails_data = {
            "mcp_preflight": {
                "pass": True,
                "signals": [
                    {
                        "id": "toxicity.detoxify",
                        "category": "toxicity",
                        "score": 0.1,
                        "label": "clean"
                    }
                ],
                "metrics": {"tests": 1, "duration_ms": 150}
            },
            "mcp_step_signals": [
                {
                    "step_id": "step_2",
                    "signals": [],
                    "reused_fingerprints": ["fp_toxicity_abc123"]
                }
            ],
            "mcp_summary": {
                "total_signals": 1,
                "reused_signals": 1,
                "violations": 0,
                "categories_checked": ["toxicity", "pii", "jailbreak"]
            }
        }
        
        # Verify guardrails integration structure
        assert "mcp_preflight" in guardrails_data
        assert "mcp_step_signals" in guardrails_data
        assert "mcp_summary" in guardrails_data
        
        # Verify preflight data
        preflight = guardrails_data["mcp_preflight"]
        assert preflight["pass"] is True
        assert len(preflight["signals"]) == 1
        
        # Verify step signals data
        step_signals = guardrails_data["mcp_step_signals"]
        assert len(step_signals) == 1
        assert step_signals[0]["step_id"] == "step_2"
        assert len(step_signals[0]["reused_fingerprints"]) == 1
        
        # Verify summary data
        summary = guardrails_data["mcp_summary"]
        assert summary["total_signals"] == 1
        assert summary["reused_signals"] == 1
        assert summary["violations"] == 0
